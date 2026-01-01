#!/usr/bin/env python3
"""
walletrandomizer.py

Generates random BIP39 wallets, derives addresses for specified BIP types (bip44/bip49/bip84/bip86),
and fetches their final balances using a local Fulcrum Electrum server (via scripthash).
"""

import sys
import signal
import argparse
import os
import json
import uuid
import socket
import hashlib
import time
import logging
import threading
import ipaddress
import itertools
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from logging.handlers import RotatingFileHandler
from datetime import datetime

#START PROFILING
#import cProfile, pstats, io
#profiler = cProfile.Profile()
#profiler.enable()
    
###############################################################################
# GLOBAL STOP FLAG FOR CTRL+C
###############################################################################
_stop_requested = False


def handle_sigint(signum, frame):
    """
    Signal handler for CTRL+C (SIGINT).
    Sets a global flag so we can finish the current wallet
    and then break out gracefully with a partial summary.
    """
    global _stop_requested
    _stop_requested = True


###############################################################################
# UNIFIED IMPORT CHECK
###############################################################################
def _check_dependencies():
    """
    Checks that all required libraries (mnemonic, bip_utils, base58, python-dotenv, tqdm) are installed.
    Exits with an error message if any are missing.

    This is done once at startup to ensure all required modules are present.
    """
    dependencies = [
        ("mnemonic", "mnemonic"),
        ("bip_utils", "bip_utils"),
        ("base58", "base58"),
        ("tqdm", "tqdm"),
    ]
    for mod, install_name in dependencies:
        try:
            __import__(mod)
        except ImportError:
            msg = (
                f"\nERROR: The '{mod}' library is missing.\n"
                f"Please install it by running:\n\n"
                f"    pip install {install_name}\n"
            )
            logger.error(msg)
            sys.exit(1)


###############################################################################
# MNEMONIC / ADDRESS GENERATION
###############################################################################
def generate_random_mnemonic(word_count: int, language: str) -> str:
    """
    Generates a random BIP39 mnemonic in the specified language.

    Args:
        word_count (int): Either 12 or 24 for the mnemonic length.
        language (str): The mnemonic language (e.g. 'english', 'french').

    Returns:
        str: The generated mnemonic.
    """
    from mnemonic import Mnemonic

    if word_count not in (12, 24):
        raise ValueError("\nERROR: Word count must be 12 or 24.")

    # For 12 words, strength=128 bits; for 24 words, strength=256 bits
    strength = 128 if word_count == 12 else 256
    mnemo = Mnemonic(language)
    return mnemo.generate(strength=strength)


def derive_addresses(
    bip_type: str, seed_phrase: str, max_addrs: int, language: str
) -> dict:
    """
    Derives addresses from a given BIP39 seed phrase using bip44, bip49, bip84, or bip86.

    Args:
        bip_type (str): The BIP derivation type ('bip44', 'bip49', 'bip84', 'bip86').
        seed_phrase (str): The BIP39 mnemonic seed phrase.
        max_addrs (int): Number of addresses to derive.
        language (str): Mnemonic language.

    Returns:
        dict: A dictionary with keys:
              - 'account_xprv'
              - 'account_xpub'
              - 'addresses': list of derived addresses
    """
    from mnemonic import Mnemonic
    from bip_utils import (
        Bip39SeedGenerator,
        Bip44,
        Bip49,
        Bip84,
        Bip86,
        Bip44Coins,
        Bip49Coins,
        Bip84Coins,
        Bip86Coins,
        Bip44Changes,
    )

    mnemo = Mnemonic(language)
    if not mnemo.check(seed_phrase):
        raise ValueError(
            f"\nERROR: Invalid BIP39 seed phrase for language '{language}'."
        )

    # Convert mnemonic to seed bytes
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()

    bip_type_lower = bip_type.lower()
    if bip_type_lower == "bip44":
        bip_obj = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    elif bip_type_lower == "bip49":
        bip_obj = Bip49.FromSeed(seed_bytes, Bip49Coins.BITCOIN)
    elif bip_type_lower == "bip84":
        bip_obj = Bip84.FromSeed(seed_bytes, Bip84Coins.BITCOIN)
    elif bip_type_lower == "bip86":
        bip_obj = Bip86.FromSeed(seed_bytes, Bip86Coins.BITCOIN)
    else:
        raise ValueError(f"\nERROR: Unsupported BIP type: {bip_type}")

    # Derive the account node (m/purpose'/coin'/account')
    account_node = bip_obj.Purpose().Coin().Account(0)
    account_xprv = account_node.PrivateKey().ToExtended()
    account_xpub = account_node.PublicKey().ToExtended()

    # We derive external addresses (chain=0) for indices [0..max_addrs-1]
    addresses = []
    for i in range(max_addrs):
        child = account_node.Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
        addr = child.PublicKey().ToAddress()
        addresses.append(addr)

    return {
        "account_xprv": account_xprv,
        "account_xpub": account_xpub,
        "addresses": addresses,
    }


###############################################################################
# SCRIPT/HASH UTILS (for scripthash-based queries)
###############################################################################
def address_to_scriptPubKey(address: str) -> bytes:
    """
    Convert a BTC base58/bech32 address to its scriptPubKey in bytes.
    Supports P2PKH, P2SH, P2WPKH, P2WSH, P2TR.

    Args:
        address (str): A valid mainnet Bitcoin address.

    Returns:
        bytes: The scriptPubKey.
    """
    from base58 import b58decode
    from bip_utils.bech32 import SegwitBech32Decoder

    address = address.strip()
    # Distinguish bech32 addresses by "bc1" prefix
    if address.lower().startswith("bc1"):
        hrp = "bc"
        wit_ver, wit_data = SegwitBech32Decoder.Decode(hrp, address)
        # v0, 20-byte => P2WPKH
        if wit_ver == 0 and len(wit_data) == 20:
            return b"\x00\x14" + wit_data
        # v0, 32-byte => P2WSH
        elif wit_ver == 0 and len(wit_data) == 32:
            return b"\x00\x20" + wit_data
        # v1, 32-byte => Taproot (BIP86)
        elif wit_ver == 1 and len(wit_data) == 32:
            return b"\x51\x20" + wit_data
        else:
            raise ValueError(
                f"\nERROR: Unsupported bech32 witnessVer={wit_ver}, len={len(wit_data)} for address: {address}"
            )
    else:
        # Legacy (base58) addresses: 1... => version=0, 3... => version=5
        raw = b58decode(address)
        if len(raw) < 5:
            raise ValueError(
                f"\nERROR: Invalid base58 decode length for {address}"
            )

        version = raw[0]
        payload = raw[1:-4]
        if version == 0:
            # P2PKH => OP_DUP OP_HASH160 <20-byte> OP_EQUALVERIFY OP_CHECKSIG
            return b"\x76\xa9\x14" + payload + b"\x88\xac"
        elif version == 5:
            # P2SH => OP_HASH160 <20-byte> OP_EQUAL
            return b"\xa9\x14" + payload + b"\x87"
        else:
            raise ValueError(
                f"\nERROR: Unsupported base58 version byte: {version}"
            )


def script_to_scripthash(script: bytes) -> str:
    """
    scripthash = sha256(scriptPubKey)[::-1].hex()

    Args:
        script (bytes): The scriptPubKey.

    Returns:
        str: The scripthash in hex form.
    """
    sha = hashlib.sha256(script).digest()
    return sha[::-1].hex()


def address_to_scripthash(address: str) -> str:
    """
    Convert address -> scriptPubKey -> scripthash.

    Args:
        address (str): A valid BTC address.

    Returns:
        str: The scripthash in hex.
    """
    spk = address_to_scriptPubKey(address)
    return script_to_scripthash(spk)


def export_wallet_json(
    wallet_index: int,
    wallet_obj: dict,
    mnemonic: str,
    language: str,
    word_count: int,
    output_dir: str = ".",
) -> None:
    """
    Exports the wallet data to a JSON file if the wallet has a balance greater than 0.

    The JSON structure is as follows:

        {
          "mnemonic": "<mnemonic>",
          "language": "<language>",
          "word_count": "<word_count>",
          "wallet": {
            "bip_types": [
              {
                "type": "<bip_type>",
                "xpriv": "<xpriv>",
                "xpub": "<xpub>",
                "addresses": [
                  { "address": "<address>", "balance": "<balance>" },
                  ...
                ]
              },
              ...
            ]
          }
        }

    Args:
        wallet_index (int): The wallet number (e.g. 1, 2, ...).
        wallet_obj (dict): Dictionary containing the wallet data. It should have a key "bip_types",
                           which is a list of dictionaries. Each dictionary has an "addresses" key,
                           which is a list of objects with "address" and "balance".
        mnemonic (str): The BIP39 mnemonic used for this wallet.
        language (str): The mnemonic language.
        word_count (int): The number of words in the mnemonic (12 or 24).
        output_dir (str): The directory where the JSON file should be saved (default: current directory).
    """
    # Calculate the wallet's total balance by summing all address balances.
    total_balance = 0.0
    for bip in wallet_obj.get("bip_types", []):
        for addr_entry in bip.get("addresses", []):
            try:
                total_balance += float(addr_entry.get("balance", "0.0"))
            except ValueError:
                continue

    # Only export if balance > 0
    if total_balance <= 0:
        return

    # Build the JSON structure
    wallet_json = {
        "mnemonic": mnemonic,
        "language": language,
        "word_count": str(word_count),
        "wallet": wallet_obj,
    }

    # Generate a random filename using a UUID
    filename = f"{uuid.uuid4()}.json"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(wallet_json, f, indent=2)
        logger.info(
            f"\nExported wallet {wallet_index} to JSON file: {filepath}"
        )
    except Exception as e:
        logger.warning(
            f"\nWARNING: Exporting wallet {wallet_index} to JSON failed: {e}"
        )


###############################################################################
# FULCRUM ELECTRUM PROTOCOL QUERY - SINGLE TCP SESSION
###############################################################################
class FulcrumClient:
    """
    A small class for a single persistent TCP connection to Fulcrum.

    We reuse one connection for multiple addresses, avoiding repeated
    TCP overhead. Each query calls `get_balance()`, which:
      1. Converts address -> scripthash
      2. Sends a JSON-RPC line for 'blockchain.scripthash.get_balance'
      3. Reads one line of JSON response
      4. Returns a dict with final_balance in satoshis
    """

    def __init__(self, host: str, port: int, timeout=5):
        """
        Initializes and connects to Fulcrum.

        Args:
            host (str): Fulcrum server host.
            port (int): Fulcrum server port.
            timeout (float, optional): Socket timeout. Defaults to 5.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.req_id = 0
        self._connect()

    def _connect(self):
        """Create the TCP socket and file-like reader for line-based JSON responses."""
        try:
            self.sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )

            # Turn the raw socket into a file-like object for easier line-based reading
            self.f = self.sock.makefile("r")
        except Exception as e:
            logger.error(f"\nERROR: Failed to connect to Fulcrum: {e}")
            sys.exit(1)

    def close(self):
        """Close the TCP connection and file stream gracefully."""
        try:
            self.f.close()
        except Exception as e:
            logger.warning(f"\nWARNING: Failed to close file stream: {e}")

        try:
            self.sock.close()
        except Exception as e:
            logger.warning(f"\nWARNING: Failed to close socket: {e}")

    def get_balance(self, address: str) -> dict | None:
        """
        Query 'blockchain.scripthash.get_balance' for a specific address,
        computing the scripthash from the address.

        Args:
            address (str): Mainnet BTC address.

        Returns:
            dict | None:
                A dict {"final_balance": int} on success, or None on error.
        """
        self.req_id += 1
        shash = address_to_scripthash(address)

        req_obj = {
            "id": self.req_id,
            "method": "blockchain.scripthash.get_balance",
            "params": [shash],
        }
        line_out = json.dumps(req_obj) + "\n"
        # Send the JSON request line
        self.sock.sendall(line_out.encode("utf-8"))

        # Read exactly one line of JSON response
        line_in = self.f.readline()
        if not line_in:
            logger.warning(
                f"\nWARNING: No response from Fulcrum for {address}"
            )
            return None

        try:
            resp = json.loads(line_in)
        except json.JSONDecodeError as e:
            logger.warning(
                f"\nWARNING: JSON parsing failed for {address}: {e}"
            )
            return None

        if "error" in resp:
            logger.warning(
                f"\nWARNING: Fulcrum error for {address}: {resp['error']}"
            )
            return None

        result = resp.get("result", {})
        confirmed = result.get("confirmed", 0)
        unconfirmed = result.get("unconfirmed", 0)
        final_bal = confirmed + unconfirmed
        return {"final_balance": final_bal}


###############################################################################
# CONCURRENCY UTILS
###############################################################################
_thread_local = threading.local()

# Keep track of all thread-local clients so we can close them at the end
_all_clients = set()
_clients_lock = threading.Lock()


def _worker_get_balances(addresses: list[str]) -> dict[str, dict|None]:
    """
    Worker function that fetches balances for a chunk of addresses in a single thread.
    """
    if not hasattr(_thread_local, "client"):
        # Each worker thread will have its own FulcrumClient
        new_client = FulcrumClient(FULCRUM_HOST, FULCRUM_PORT, timeout=5)
        _thread_local.client = new_client
        with _clients_lock:
            _all_clients.add(new_client)

    results = {}
    for addr in addresses:
        balance_data = _thread_local.client.get_balance(addr)
        results[addr] = balance_data
    return results


def parallel_fetch_balances_chunked(
    executor: ThreadPoolExecutor,
    addresses: list[str],
    chunk_size: int = 40
) -> dict[str, dict | None]:
    """
    Fetch balances for many addresses concurrently, but in batch chunks.
    This reduces overhead by creating fewer futures (one per chunk),
    instead of one future per address.

    Args:
        executor: ThreadPoolExecutor to run tasks.
        addresses: All addresses to fetch.
        chunk_size: Number of addresses to handle per future.

    Returns:
        dict[address -> balance data]
    """
    all_results = {}
    future_map = {}

    # Slice addresses into sublists of length 'chunk_size'
    for i in range(0, len(addresses), chunk_size):
        chunk = addresses[i:i + chunk_size]
        future = executor.submit(_worker_get_balances, chunk)
        future_map[future] = chunk

    # Collect results
    for fut in as_completed(future_map):
        chunk = future_map[fut]
        try:
            partial_result = fut.result()
            all_results.update(partial_result)
        except Exception as e:
            logger.warning(f"Failed to fetch balances for chunk {chunk}: {e}")

    return all_results


def close_all_threadlocal_clients():
    """Close all FulcrumClients that were created in worker threads."""
    with _clients_lock:
        for client in _all_clients:
            client.close()
        _all_clients.clear()


def _derive_in_process(
    bip_type: str, mnemonic: str, num_addresses: int, language: str
) -> tuple[str, dict]:
    derivation_info = derive_addresses(
        bip_type, mnemonic, num_addresses, language
    )
    return bip_type, derivation_info


###############################################################################
# MAIN SCRIPT
###############################################################################
def main():
    """
    Main function for generating wallets, deriving addresses, and fetching balances.

    Steps:
      1) Parse command-line arguments
      2) Possibly enable verbose console output (-v/--verbose)
      3) Possibly create a log file (-L/--logfile)
      4) Create a single FulcrumClient session
      5) For each wallet, generate a mnemonic, derive addresses, fetch balances
         (printing minimal or verbose info to console depending on verbosity)
      6) Print final summary lines
    """
    parser = argparse.ArgumentParser(
        description="Generate random BIP39 wallets and fetch address balances from Fulcrum."
    )
    parser.add_argument(
        "num_wallets",
        type=int,
        nargs='?',
        help="Number of wallets to generate (must be >= 1, or -1 for infinite).",
    )
    parser.add_argument(
        "num_addresses",
        type=int,
        nargs='?',
        help="Number of addresses per wallet (must be >= 1).",
    )
    parser.add_argument(
        "bip_types",
        type=str,
        nargs='?',
        help="Comma-separated BIP derivation types: 'bip44,bip49,bip84,bip86'",
    )
    parser.add_argument(
        "--num-wallets",
        type=int,
        dest="num_wallets_flag",
        help="Number of wallets to generate (must be >= 1, or -1 for infinite).",
    )
    parser.add_argument(
        "--network",
        type=str,
        dest="network_flag",
        help="Alternative to bip_types positional: comma-separated BIP derivation types (e.g., 'bip44,bip84').",
    )
    parser.add_argument(
        "--output",
        type=str,
        dest="output_path",
        help="Output directory for wallet JSON files (default: current directory).",
    )
    parser.add_argument(
        "--format",
        type=str,
        dest="output_format",
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="If given, print verbose details (debug) to console. Otherwise only info-level messages.",
    )
    parser.add_argument(
        "-L",
        "--logfile",
        action="store_true",
        help="If given, create a .log file in the script directory with a timestamp.",
    )
    parser.add_argument(
        "-w",
        "--wordcount",
        type=int,
        default=12,
        choices=[12, 24],
        help="Mnemonic word count (default: 12).",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="english",
        choices=[
            "english",
            "french",
            "italian",
            "spanish",
            "korean",
            "chinese_simplified",
            "chinese_traditional",
        ],
        help="BIP39 mnemonic language (default: english).",
    )
    parser.add_argument(
        "-s", "--server",
        type=str,
        default="127.0.0.1",
        help="Fulcrum server IP (default: 127.0.0.1)."
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=50001,
        help="Fulcrum server TCP port (default: 50001)."
    )

    args = parser.parse_args()

    # Merge positional and flag-based arguments (flags take precedence)
    if args.num_wallets_flag is not None:
        args.num_wallets = args.num_wallets_flag
    if args.network_flag is not None:
        args.bip_types = args.network_flag
    
    # Validate that required arguments are provided
    if args.num_wallets is None:
        logger.error("\nERROR: num_wallets must be provided (positional or --num-wallets).")
        sys.exit(1)
    if args.num_addresses is None:
        logger.error("\nERROR: num_addresses must be provided as positional argument.")
        sys.exit(1)
    if args.bip_types is None:
        logger.error("\nERROR: bip_types must be provided (positional or --network).")
        sys.exit(1)

    # Enforce that --verbose can only be used in conjunction with --logfile
    if args.verbose and not args.logfile:
        logger.error("\nERROR: The -v/--verbose option requires -L/--logfile")
        sys.exit(1)

    # Validate inputs (-1 is allowed for infinite wallets)
    if args.num_wallets < -1 or args.num_wallets == 0:
        logger.error("\nERROR: num_wallets must be >= 1, or -1 for infinite generation.")
        sys.exit(1)
    if args.num_addresses < 1:
        logger.error("\nERROR: num_addresses must be >= 1.")
        sys.exit(1)
    try:
        ipaddress.ip_address(args.server)
    except ValueError:
        logger.error(f"\nERROR: '{args.server}' is not a valid IP address.")
        sys.exit(1)
    if args.port < 1 or args.port > 65535:
        logger.error("\nERROR: Fulcrum server port must be between 1 and 65535.")
        sys.exit(1)

    # Parse and validate BIP types
    bip_types_list = [
        x.strip().lower() for x in args.bip_types.split(",") if x.strip()
    ]
    allowed_bips = {"bip44", "bip49", "bip84", "bip86"}
    if not bip_types_list:
        logger.error("\nERROR: No valid BIP types specified.")
        sys.exit(1)

    for bip in bip_types_list:
        if bip not in allowed_bips:
            logger.error(
                f"\nERROR: Invalid BIP type '{bip}'. Must be one of: {', '.join(allowed_bips)}."
            )
            sys.exit(1)

        # Configure logging level based on -v/--verbose argument
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Possibly create a .log file
    if args.logfile:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"{timestamp_str}.log"
        log_path = os.path.join(script_dir, log_filename)
        try:
            # Rotating log files after 250 MB
            rotating_fh = RotatingFileHandler(
                log_path,
                maxBytes=250 * 1024 * 1024,
                backupCount=40,
                encoding="utf-8",
            )
            rotating_fh.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(rotating_fh)
        except Exception as e:
            logger.error(
                f"\nERROR: Failed to open log file '{log_path}' for writing: {e}"
            )
            sys.exit(1)

    # Assign parsed arguments
    global FULCRUM_HOST, FULCRUM_PORT
    FULCRUM_HOST = args.server
    FULCRUM_PORT = args.port
    num_wallets = args.num_wallets
    num_addresses = args.num_addresses
    language = args.language
    word_count = args.wordcount
    output_dir = args.output_path if args.output_path else "."
    
    # Create output directory if it doesn't exist
    if output_dir != ".":
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"\nERROR: Failed to create output directory '{output_dir}': {e}")
            sys.exit(1)

    # Handle infinite wallet generation
    infinite_mode = (num_wallets == -1)
    if infinite_mode:
        total_addrs = "∞"
        logger.info("\n===== WALLET RANDOMIZER (INFINITE MODE) =====\n")
    else:
        total_addrs = num_wallets * num_addresses * len(bip_types_list)
        logger.info("\n===== WALLET RANDOMIZER =====\n")
    
    grand_total_sat = 0
    wallets_processed = 0

    # Start timing
    start_time = time.time()

    # Print initial info
    logger.info(f"Number of Wallets:    {num_wallets if not infinite_mode else 'Infinite'}")
    logger.info(f"Addresses per Wallet: {num_addresses}")
    logger.info(f"BIP Type(s):          {', '.join(bip_types_list)}")
    logger.info(f"Mnemonic Language:    {language}")
    logger.info(f"Word count:           {word_count}")
    logger.info(f"Output Directory:     {output_dir}")
    logger.info(f"\nTotal addresses:      {total_addrs}\n")

    from tqdm import tqdm

    # Suppose we set "max_procs = len(bip_types_list)" so if user picks 2 BIP types => 2 processes, etc.
    max_procs = len(bip_types_list)

    try:
        # We create one process per BIP type
        # The 'ppex' is for CPU-bound derivations, 'executor' is for Fulcrum fetches.
        with ProcessPoolExecutor(
            max_workers=max_procs
        ) as ppex, ThreadPoolExecutor(max_workers=num_addresses) as executor:

            # MAIN LOOP: generate wallets, derive addresses (via ProcessPoolExecutor), get balances
            # Create an iterator that either loops num_wallets times or infinitely
            if infinite_mode:
                wallet_iterator = itertools.count(0)  # Truly infinite iterator
                progress_bar = tqdm(
                    desc="Generating wallets",
                    unit=" wallets",
                    leave=False,
                    mininterval=0.5,
                    total=None,  # Infinite progress bar
                )
            else:
                wallet_iterator = range(num_wallets)
                progress_bar = tqdm(
                    wallet_iterator,
                    desc="Generating wallets",
                    unit=" wallets",
                    leave=False,
                    mininterval=0.5,
                )
            
            try:
                for w_i in wallet_iterator:
                    if _stop_requested:
                        logger.warning("\n\nWARNING: CTRL+C Detected! => Stopping early.")
                        break
                    
                    if infinite_mode:
                        progress_bar.update(1)
                
                wallet_display_num = w_i + 1
                logger.debug(f"\n\n=== WALLET {wallet_display_num} ===")

                # 1) Generate a new mnemonic
                mnemonic = generate_random_mnemonic(word_count=word_count, language=language)
                logger.debug(f"\n  Generated mnemonic: {mnemonic}")

                wallet_balance_sat = 0
                wallet_obj = {"bip_types": []}

                # 2) Derive addresses for all BIP types *in parallel processes*
                fut_map = {}
                for bip_type in bip_types_list:
                    fut = ppex.submit(
                        _derive_in_process,
                        bip_type,
                        mnemonic,
                        num_addresses,
                        language,
                    )
                    fut_map[fut] = bip_type

                bip_results = []
                for fut in as_completed(fut_map):
                    bip_type = fut_map[fut]
                    try:
                        bip_type2, derivation_info = fut.result()
                        bip_results.append((bip_type2, derivation_info))
                    except Exception as e:
                        logger.warning(f"\nWARNING: Derivation failed for {bip_type}: {e}")

                # 3) Combine *all* addresses from all BIP types
                all_addresses_for_wallet = []
                bip_entries = []
                for bip_type, derivation_info in bip_results:
                    bip_entry = {
                        "type": bip_type,
                        "extended_private_key": derivation_info["account_xprv"],
                        "extended_public_key": derivation_info["account_xpub"],
                        "addresses": [],  # we'll fill in after we fetch balances
                    }
                    bip_entries.append(bip_entry)

                    # gather these addresses to fetch all at once
                    all_addresses_for_wallet.extend(derivation_info["addresses"])

                # 4) Now call *once* to fetch balances for all addresses, in chunked form
                if all_addresses_for_wallet:
                    results_map = parallel_fetch_balances_chunked(
                        executor,
                        all_addresses_for_wallet,
                        chunk_size=5
                    )
                else:
                    results_map = {}

                # 5) Distribute balances into each bip_entry
                #    (we have bip_entries[i] which corresponds to bip_results[i])
                for (bip_type, derivation_info), bip_entry in zip(bip_results, bip_entries):
                    addresses = derivation_info["addresses"]
                    for addr in addresses:
                        data = results_map.get(addr)
                        if data is not None:
                            final_balance_sat = data["final_balance"]
                            wallet_balance_sat += final_balance_sat
                            final_balance_btc = final_balance_sat / 1e8
                        else:
                            final_balance_btc = 0.0
                            logger.warning(f"        WARNING: Could not fetch balance for address: {addr}")

                        bip_entry["addresses"].append({
                            "address": addr,
                            "balance": str(final_balance_btc),
                        })

                # 6) Append all bip_entries to the wallet object
                wallet_obj["bip_types"].extend(bip_entries)

                # 7) Log or export
                wallet_balance_btc = wallet_balance_sat / 1e8
                logger.debug(f"\n  WALLET {wallet_display_num} TOTAL BALANCE: {wallet_balance_btc} BTC")

                grand_total_sat += wallet_balance_sat
                wallets_processed += 1

                export_wallet_json(
                    wallet_display_num, wallet_obj, mnemonic, language, word_count, output_dir
                )
            finally:
                # Always close the progress bar
                progress_bar.close()

    except (KeyboardInterrupt, InterruptedError) as e:
        logger.warning(f"\n\nWARNING: Script interrupted: {e}")

    finally:
        # Calculate script running time
        elapsed_s = time.time() - start_time
        hours = int(elapsed_s // 3600)
        minutes = int((elapsed_s % 3600) // 60)
        seconds = elapsed_s % 60
        # Calculate totals
        grand_total_btc = grand_total_sat / 1e8
        addresses_per_second = (wallets_processed * num_addresses * len(bip_types_list)) / elapsed_s if elapsed_s > 0 else 0
        if wallets_processed > 0:
            logger.info("\n\n=== SUMMARY ===")
            if infinite_mode:
                logger.info(f"\n{wallets_processed} WALLETS PROCESSED (~ {addresses_per_second:.0f} addr/s)")
            else:
                logger.info(f"\n{wallets_processed}/{num_wallets} WALLETS PROCESSED (~ {addresses_per_second:.0f} addr/s)")
            logger.info(
                f"\nGRAND TOTAL BALANCE ACROSS ALL WALLETS:\n\n  {grand_total_btc} BTC\n"
            )
            logger.info(f"\nScript runtime: {hours}h {minutes}m {seconds:.2f}s\n")
        else:
            logger.info(f"\nNo wallets processed.\n")
        # Close all thread-local clients for Fulcrum
        close_all_threadlocal_clients()


if __name__ == "__main__":
    # Built-in logger setup
    logger = logging.getLogger("walletrandomizer")
    logger.setLevel(logging.INFO)

    # Create a console handler for the terminal output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # Perform the checks at load time
    _check_dependencies()
    
    # Register SIGINT handler so pressing CTRL+C triggers handle_sigint.
    signal.signal(signal.SIGINT, handle_sigint)

    # Run main script
    main()

#STOP PROFILING
#profiler.disable()
#s = io.StringIO()
#ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
#ps.print_stats(50)
#print(s.getvalue())