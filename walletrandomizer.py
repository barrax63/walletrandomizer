#!/usr/bin/env python3
"""
wallet_randomizer_fulcrum.py

Generates random BIP39 wallets, derives addresses for specified BIP types (bip44/bip49/bip84/bip86),
and fetches their final balances using a local Fulcrum Electrum server (via scripthash).
"""

import sys
import argparse
import os
import json
import socket
import hashlib
from datetime import datetime

###############################################################################
# GLOBAL VERBOSE FLAG
###############################################################################
_VERBOSE = False  # Will be set via command-line argument -v/--verbose

###############################################################################
# LOGGING SETUP
###############################################################################
_log_file = None

def log(*args, sep=" ", end="\n", always=False):
    """
    Custom logging function that conditionally prints to console
    based on _VERBOSE and always writes to the log file if open.

    Args:
        *args: Message parts to be joined by 'sep'.
        sep (str, optional): Separator for message parts. Defaults to " ".
        end (str, optional): Line ending. Defaults to "\n".
        always (bool, optional):
            - If True, always print to console regardless of _VERBOSE.
            - If False, only print if _VERBOSE is True.

    The function always writes output to the log file (if one is open),
    but only prints to the console if `always=True` or `_VERBOSE` is True.
    """
    msg = sep.join(str(a) for a in args)

    # Always write the message to the log file if present
    if _log_file is not None:
        _log_file.write(msg + end)
        _log_file.flush()

    # Conditionally print to console:
    #   if always=True, print no matter what
    #   else only print if _VERBOSE is True
    if always or _VERBOSE:
        print(msg, end=end)

###############################################################################
# UNIFIED IMPORT CHECK
###############################################################################
def _check_dependencies():
    """
    Checks that all required libraries (mnemonic, bip_utils, base58, python-dotenv) are installed.
    Exits with an error message if any are missing.

    This is done once at startup to ensure all required modules are present.
    """
    dependencies = [
        ("mnemonic", "mnemonic"),
        ("bip_utils", "bip_utils"),
        ("base58", "base58"),
        ("dotenv", "python-dotenv")
    ]
    for mod, install_name in dependencies:
        try:
            __import__(mod)
        except ImportError:
            msg = (
                f"Error: The '{mod}' library is missing.\n"
                f"Please install it by running:\n\n"
                f"    pip install {install_name}\n"
            )
            # Use always=True to ensure user sees this error on console
            log(msg, always=True)
            sys.exit(1)

# Perform the checks at load time
_check_dependencies()

###############################################################################
# LOAD CONFIG FROM .env FILE (FULCRUM HOST/PORT)
###############################################################################
from dotenv import load_dotenv
load_dotenv()  # Load .env variables for Fulcrum connection

FULCRUM_HOST = os.getenv("FULCRUM_HOST", "127.0.0.1")
FULCRUM_PORT = int(os.getenv("FULCRUM_PORT", "50001"))

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
        raise ValueError("Word count must be 12 or 24.")

    # For 12 words, strength=128 bits; for 24 words, strength=256 bits
    strength = 128 if word_count == 12 else 256
    mnemo = Mnemonic(language)
    return mnemo.generate(strength=strength)


def derive_addresses(bip_type: str, seed_phrase: str, max_addrs: int, language: str) -> dict:
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
        Bip44, Bip49, Bip84, Bip86,
        Bip44Coins, Bip49Coins, Bip84Coins, Bip86Coins,
        Bip44Changes
    )

    mnemo = Mnemonic(language)
    if not mnemo.check(seed_phrase):
        raise ValueError(f"Invalid BIP39 seed phrase for language '{language}'.")

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
        raise ValueError(f"Unsupported BIP type: {bip_type}")

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
        "addresses": addresses
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
                f"Unsupported bech32 witnessVer={wit_ver}, len={len(wit_data)} for address: {address}"
            )
    else:
        # Legacy (base58) addresses: 1... => version=0, 3... => version=5
        raw = b58decode(address)
        if len(raw) < 5:
            raise ValueError(f"Invalid base58 decode length for {address}")

        version = raw[0]
        payload = raw[1:-4]
        if version == 0:
            # P2PKH => OP_DUP OP_HASH160 <20-byte> OP_EQUALVERIFY OP_CHECKSIG
            return b"\x76\xa9\x14" + payload + b"\x88\xac"
        elif version == 5:
            # P2SH => OP_HASH160 <20-byte> OP_EQUAL
            return b"\xa9\x14" + payload + b"\x87"
        else:
            raise ValueError(f"Unsupported base58 version byte: {version}")


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
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        # Turn the raw socket into a file-like object for easier line-based reading
        self.f = self.sock.makefile("r")

    def close(self):
        """Close the TCP connection and file stream gracefully."""
        try:
            self.f.close()
        except:
            pass
        try:
            self.sock.close()
        except:
            pass

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
            "params": [shash]
        }
        line_out = json.dumps(req_obj) + "\n"
        # Send the JSON request line
        self.sock.sendall(line_out.encode("utf-8"))

        # Read exactly one line of JSON response
        line_in = self.f.readline()
        if not line_in:
            log(f"No response from Fulcrum for {address}")
            return None

        try:
            resp = json.loads(line_in)
        except json.JSONDecodeError as e:
            log(f"JSON parse error for {address}: {e}")
            return None

        if "error" in resp:
            log(f"Fulcrum error for {address}: {resp['error']}")
            return None

        result = resp.get("result", {})
        confirmed = result.get("confirmed", 0)
        unconfirmed = result.get("unconfirmed", 0)
        final_bal = confirmed + unconfirmed
        return {"final_balance": final_bal}


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
         (printing minimal or verbose info to console depending on _VERBOSE)
      6) Print final summary lines
    """
    parser = argparse.ArgumentParser(
        description="Generate random BIP39 wallets and fetch address balances from Fulcrum."
    )
    parser.add_argument(
        "num_wallets",
        type=int,
        help="Number of wallets to generate (must be >= 1)."
    )
    parser.add_argument(
        "num_addresses",
        type=int,
        help="Number of addresses per wallet (must be >= 1)."
    )
    parser.add_argument(
        "bip_types",
        type=str,
        help="Comma-separated BIP derivation types: 'bip44,bip49,bip84,bip86'"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="If given, print verbose details to console. Otherwise only final balances."
    )
    parser.add_argument(
        "-L", "--logfile",
        action="store_true",
        help="If given, create a .log file in the script directory with a timestamp."
    )
    parser.add_argument(
        "-w", "--wordcount",
        type=int,
        default=12,
        choices=[12, 24],
        help="Mnemonic word count (default: 12)."
    )
    parser.add_argument(
        "-l", "--language",
        type=str,
        default="english",
        choices=["english", "french", "italian", "spanish", "korean",
                 "chinese_simplified", "chinese_traditional"],
        help="BIP39 mnemonic language (default: english)."
    )

    args = parser.parse_args()

    # Capture whether the user wants verbose console output
    global _VERBOSE
    _VERBOSE = args.verbose

    # Possibly create a .log file
    global _log_file
    if args.logfile:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"{timestamp_str}.log"
        log_path = os.path.join(script_dir, log_filename)
        try:
            _log_file = open(log_path, "w", encoding="utf-8")
        except Exception as e:
            log(f"Failed to open log file '{log_path}' for writing: {e}", always=True)
            sys.exit(1)

    # Validate numeric inputs
    if args.num_wallets < 1:
        log("Error: num_wallets must be >= 1.", always=True)
        sys.exit(1)
    if args.num_addresses < 1:
        log("Error: num_addresses must be >= 1.", always=True)
        sys.exit(1)

    # Parse and validate BIP types
    bip_types_list = [x.strip().lower() for x in args.bip_types.split(",") if x.strip()]
    allowed_bips = {"bip44", "bip49", "bip84", "bip86"}
    if not bip_types_list:
        log("Error: No valid BIP types specified.", always=True)
        sys.exit(1)

    for bip in bip_types_list:
        if bip not in allowed_bips:
            log(f"Error: Invalid BIP type '{bip}'. Must be one of: {', '.join(allowed_bips)}.", always=True)
            sys.exit(1)

    num_wallets = args.num_wallets
    num_addresses = args.num_addresses
    language = args.language
    word_count = args.wordcount

    total_addrs = num_wallets * num_addresses * len(bip_types_list)
    grand_total_sat = 0

    # Print initial info (always shown on console)
    log("\n===== WALLET RANDOMIZER =====\n", always=True)
    log(f"Number of Wallets:    {num_wallets}", always=True)
    log(f"Addresses per Wallet: {num_addresses}", always=True)
    log(f"BIP Type(s):          {', '.join(bip_types_list)}", always=True)
    log(f"Mnemonic Language:    {language}", always=True)
    log(f"Word count:           {word_count}", always=True)
    log(f"\nTotal addresses:      {total_addrs}", always=True)

    # Create a single FulcrumClient session for all address queries
    client = FulcrumClient(FULCRUM_HOST, FULCRUM_PORT, timeout=5)

    # MAIN LOOP: generate wallets, derive addresses, get balances
    for w_i in range(num_wallets):
        # If verbose, show detailed heading, else skip
        log(f"\n\n=== WALLET {w_i + 1}/{num_wallets} ===", always=_VERBOSE)

        mnemonic = generate_random_mnemonic(word_count=word_count, language=language)
        # If verbose, show the generated mnemonic in console
        log(f"\n  Generated mnemonic: {mnemonic}", always=_VERBOSE)

        wallet_balance_sat = 0

        for bip_type in bip_types_list:
            # If verbose, show bip_type details
            log(f"\n  == Deriving addresses for {bip_type.upper()} ==\n", always=_VERBOSE)

            derivation_info = derive_addresses(
                bip_type,
                mnemonic,
                max_addrs=num_addresses,
                language=language
            )
            account_xprv = derivation_info["account_xprv"]
            account_xpub = derivation_info["account_xpub"]
            addresses = derivation_info["addresses"]

            # Log details only if verbose
            log(f"    Account Extended Private Key: {account_xprv}", always=_VERBOSE)
            log(f"    Account Extended Public Key:  {account_xpub}", always=_VERBOSE)
            log(f"\n    Derived {len(addresses)} addresses:", always=_VERBOSE)

            for addr in addresses:
                log(f"      {addr}", always=_VERBOSE)
                data = client.get_balance(addr)
                if data is not None:
                    final_balance_sat = data["final_balance"]
                    wallet_balance_sat += final_balance_sat
                    final_balance_btc = final_balance_sat / 1e8

                    # If verbose, log each address's balance
                    log(f"        ADDRESS BALANCE: {final_balance_btc} BTC", always=_VERBOSE)
                else:
                    log(f"        Could not fetch balance for address: {addr}", always=_VERBOSE)

        # Print wallet total balance to console always
        wallet_balance_btc = wallet_balance_sat / 1e8
        log(f"\n  WALLET {w_i + 1} TOTAL BALANCE: {wallet_balance_btc} BTC", always=True)

        grand_total_sat += wallet_balance_sat

    # After all wallets, print summary lines (always)
    grand_total_btc = grand_total_sat / 1e8
    log("\n\n=== SUMMARY ===", always=True)
    log(f"\nGRAND TOTAL BALANCE ACROSS ALL WALLETS/ADDRESSES:\n\n {grand_total_btc} BTC\n", always=True)

    # Close connection
    client.close()

    # Close log file if opened
    if _log_file is not None:
        _log_file.close()


if __name__ == "__main__":
    main()
