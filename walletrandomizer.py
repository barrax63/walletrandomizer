#!/usr/bin/env python3
import sys
import argparse
import os
import json
from datetime import datetime
from dotenv import load_dotenv

###############################################################################
# LOAD CONFIG FROM .env FILE (FULCRUM HOST/PORT)
###############################################################################
load_dotenv()  # Load .env file variables into environment

FULCRUM_HOST = os.getenv("FULCRUM_HOST")
FULCRUM_PORT = int(os.getenv("FULCRUM_PORT"))

###############################################################################
# LOGGING SETUP
###############################################################################
_log_file = None

def log(*args, sep=" ", end="\n"):
    """
    Custom logging function that prints to the console
    and also writes to a file if _log_file is open.
    """
    msg = sep.join(str(a) for a in args)
    print(msg, end=end)  # Always print to console
    if _log_file is not None:
        _log_file.write(msg + end)
        _log_file.flush()


###############################################################################
# IMPORT CHECKS
###############################################################################
_mnemonic_import_checked = False
_bip_utils_import_checked = False

def _check_mnemonic_import():
    global _mnemonic_import_checked
    if _mnemonic_import_checked:
        return
    try:
        import mnemonic  # check presence
    except ImportError:
        msg = (
            "Error: The 'mnemonic' library is missing.\n"
            "Please install it by running:\n"
            "    pip install mnemonic\n"
        )
        log(msg)
        sys.exit(1)
    _mnemonic_import_checked = True

def _check_bip_utils_import():
    global _bip_utils_import_checked
    if _bip_utils_import_checked:
        return
    try:
        import bip_utils  # check presence
    except ImportError:
        msg = (
            "Error: The 'bip_utils' library is missing.\n"
            "Please install it by running:\n"
            "    pip install bip_utils\n"
        )
        log(msg)
        sys.exit(1)
    _bip_utils_import_checked = True


###############################################################################
# MNEMONIC / ADDRESS GENERATION
###############################################################################
def generate_random_mnemonic(word_count=12, language="english"):
    """
    Generates a random BIP39 mnemonic in the specified language (12 or 24 words).
    """
    _check_mnemonic_import()
    from mnemonic import Mnemonic

    if word_count not in (12, 24):
        raise ValueError("Word count must be 12 or 24.")

    mnemo = Mnemonic(language)
    # For 12 words, use strength=128; for 24 words, strength=256
    strength = 128 if word_count == 12 else 256
    return mnemo.generate(strength=strength)

def derive_addresses(bip_type, seed_phrase, max_addrs=20, language="english"):
    """
    Derives addresses from a given BIP39 seed phrase using bip44, bip49, bip84, or bip86.
    Returns: { "account_xprv", "account_xpub", "addresses" }
    """
    _check_mnemonic_import()
    _check_bip_utils_import()

    from mnemonic import Mnemonic
    from bip_utils import (
        Bip39SeedGenerator,
        Bip44, Bip49, Bip84, Bip86,
        Bip44Coins, Bip49Coins, Bip84Coins, Bip86Coins,
        Bip44Changes
    )

    # Validate seed phrase
    mnemo = Mnemonic(language)
    if not mnemo.check(seed_phrase):
        raise ValueError(
            f"Invalid BIP39 seed phrase for language '{language}' (checksum mismatch)."
        )

    # Convert mnemonic to seed
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()

    # Create the correct bip object
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

    # Derive account node and external addresses
    account_node = bip_obj.Purpose().Coin().Account(0)
    account_xprv = account_node.PrivateKey().ToExtended()
    account_xpub = account_node.PublicKey().ToExtended()

    # Derive external addresses [0..max_addrs-1]
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
# FULCRUM ELECTRUM PROTOCOL QUERY
###############################################################################
def _fetch_data_fulcrum(address, host, port):
    """
    Connect to a local Fulcrum server (Electrum protocol) at host:port (TCP, no SSL).
    Query the 'blockchain.address.get_balance' method for the given address.

    Returns a dict:
      { "final_balance": int }   # sat
    or None if there's an error.
    """
    import socket
    try:
        # 1) Connect to Fulcrum (TCP)
        with socket.create_connection((host, port), timeout=5) as s:
            # 2) Build the JSON request
            req = {
                "id": 0,
                "method": "blockchain.address.get_balance",
                "params": [address]
            }
            # 3) Send request (terminated by newline)
            s.sendall((json.dumps(req) + "\n").encode("utf-8"))

            # 4) Read one line of JSON response
            f = s.makefile()  # Turn into a file-like
            line = f.readline()
            if not line:
                log(f"        No response for address: {address}")
                return None

            resp = json.loads(line)
            if "error" in resp:
                log(f"        Fulcrum error: {resp['error']}")
                return None

            result = resp.get("result", {})
            # 'result' looks like: {"confirmed": <int sat>, "unconfirmed": <int sat>}
            confirmed = result.get("confirmed", 0)
            unconfirmed = result.get("unconfirmed", 0)
            final_balance_sat = confirmed + unconfirmed

            return {"final_balance": final_balance_sat}

    except socket.timeout:
        log(f"        Timeout connecting to Fulcrum for {address}")
        return None
    except Exception as e:
        log(f"        Exception fetching data from Fulcrum for {address}: {e}")
        return None


def get_address_data(address):
    """
    Wrapper to get final balance from Fulcrum's Electrum protocol.
    Return dict {"final_balance": int} or None if error.
    """
    return _fetch_data_fulcrum(address, FULCRUM_HOST, FULCRUM_PORT)


###############################################################################
# MAIN SCRIPT
###############################################################################
def main():
    parser = argparse.ArgumentParser(
        description="Generate random BIP39 wallets (optionally in different languages) "
                    "and fetch balances from Fulcrum (Electrum server)."
    )
    parser.add_argument(
        "num_wallets",
        type=int,
        help="Number of wallets to generate (must be > 0)."
    )
    parser.add_argument(
        "num_addresses",
        type=int,
        help="Number of addresses per wallet (must be > 0)."
    )
    parser.add_argument(
        "bip_types",
        type=str,
        help="Comma-separated list of BIP derivation types (e.g. 'bip84,bip44')."
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
        choices=[
            "english", "french", "italian", "spanish", "korean",
            "chinese_simplified", "chinese_traditional"
        ],
        help="BIP39 mnemonic language (default: english)."
    )

    args = parser.parse_args()

    # Validate numeric inputs
    if args.num_wallets < 1:
        log("Error: num_wallets must be at least 1.")
        sys.exit(1)
    if args.num_addresses < 1:
        log("Error: num_addresses must be at least 1.")
        sys.exit(1)

    # Process BIP types
    bip_types_list = [x.strip().lower() for x in args.bip_types.split(",") if x.strip()]
    allowed_bips = {"bip44", "bip49", "bip84", "bip86"}
    if not bip_types_list:
        log("Error: No valid BIP types specified.")
        sys.exit(1)

    # Validate each requested BIP type
    for bip in bip_types_list:
        if bip not in allowed_bips:
            log(f"Error: Invalid BIP type '{bip}'. Must be one of {', '.join(allowed_bips)}.")
            sys.exit(1)

    # Optional log file
    if args.logfile:
        global _log_file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"{timestamp_str}.log"
        log_path = os.path.join(script_dir, log_filename)
        try:
            _log_file = open(log_path, "w", encoding="utf-8")
        except Exception as e:
            log(f"Failed to open log file '{log_path}' for writing: {e}")
            sys.exit(1)

    # Unpack arguments for clarity
    num_wallets = args.num_wallets
    num_addresses = args.num_addresses
    language = args.language
    word_count = args.wordcount

    total_addrs = num_wallets * num_addresses * len(bip_types_list)

    # Keep track of total BTC across all wallets
    grand_total_sat = 0

    log("\n===== WALLET RANDOMIZER =====\n")
    log(f"Number of Wallets:  {num_wallets}")
    log(f"Addresses/Wallet:   {num_addresses}")
    log(f"BIP Type(s):        {', '.join(bip_types_list)}")
    log(f"Mnemonic Language:  {language}")
    log(f"Word count:         {word_count}")
    log(f"\nTotal addresses:    {total_addrs}")

    for w_i in range(num_wallets):
        log(f"\n\n=== WALLET {w_i + 1}/{num_wallets} ===")

        # Generate a mnemonic in the chosen language
        mnemonic = generate_random_mnemonic(word_count=word_count, language=language)
        log(f"\n  Generated mnemonic: {mnemonic}")

        # Track total BTC for this wallet
        wallet_balance_sat = 0

        # Derive addresses + fetch balances from Fulcrum
        for bip_type in bip_types_list:
            log(f"\n  == Deriving addresses for {bip_type.upper()} ==\n")
            derivation_info = derive_addresses(
                bip_type,
                mnemonic,
                max_addrs=num_addresses,
                language=language
            )
            account_xprv = derivation_info["account_xprv"]
            account_xpub = derivation_info["account_xpub"]
            addresses = derivation_info["addresses"]

            log(f"    Account Extended Private Key: {account_xprv}")
            log(f"    Account Extended Public Key:  {account_xpub}")
            log(f"\n    Derived {len(addresses)} addresses:")

            for addr in addresses:
                log(f"      {addr}")
                data = get_address_data(addr)
                if data is not None:
                    final_balance_sat = data.get("final_balance", 0)
                    wallet_balance_sat += final_balance_sat
                    final_balance_btc = final_balance_sat / 1e8
                    log(f"        ADDRESS BALANCE: {final_balance_btc} BTC")
                else:
                    log(f"        Could not fetch balance for address: {addr}")

        # Summarize wallet total
        wallet_balance_btc = wallet_balance_sat / 1e8
        log(f"\n  WALLET {w_i + 1} TOTAL BALANCE: {wallet_balance_btc} BTC")

        # Add to overall total
        grand_total_sat += wallet_balance_sat

    # Final summary
    grand_total_btc = grand_total_sat / 1e8
    log("\n\n=== SUMMARY ===")
    log(f"\nGRAND TOTAL BALANCE ACROSS ALL WALLETS/ADDRESSES:\n\n {grand_total_btc} BTC\n")

    # Close log file if opened
    if _log_file is not None:
        _log_file.close()


if __name__ == "__main__":
    main()
