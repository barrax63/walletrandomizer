#!/usr/bin/env python3
import sys
import argparse
import os
from datetime import datetime

###############################################################################
# STATIC RPC CREDENTIALS - ADJUST FOR YOUR BITCOIN CORE SETTINGS
###############################################################################
RPC_USER = "rpcuserbitcd"
RPC_PASSWORD = ".qYgPPEZpdoqy83Z"
RPC_URL = "http://127.0.0.1:8332"


###############################################################################
# LOGGING SETUP
###############################################################################
_log_file = None

def log(*args, sep=" ", end="\n"):
    """
    Custom logging function that prints to console
    and also writes to a file if _log_file is open.
    """
    msg = sep.join(str(a) for a in args)
    # Print to console
    print(msg, end=end)
    # If a log file is open, write to it as well
    if _log_file is not None:
        _log_file.write(msg + end)
        _log_file.flush()


###############################################################################
# GENERATE WALLET
###############################################################################
_mnemonic_import_checked = False
_bip_utils_import_checked = False

def _check_mnemonic_import():
    global _mnemonic_import_checked
    if _mnemonic_import_checked:
        return

    try:
        import mnemonic  # only to check import
    except ImportError:
        msg = (
            "Error: The 'mnemonic' library is missing.\n"
            "Please install it by running:\n\n"
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
        import bip_utils  # only to check import
    except ImportError:
        msg = (
            "Error: The 'bip_utils' library is missing.\n"
            "Please install it by running:\n\n"
            "    pip install bip_utils\n"
        )
        log(msg)
        sys.exit(1)
    _bip_utils_import_checked = True

def generate_random_mnemonic(word_count):
    _check_mnemonic_import()
    from mnemonic import Mnemonic

    if word_count not in (12, 24):
        raise ValueError("Word count must be 12 or 24.")

    mnemo = Mnemonic("english")
    # For 12 words, use strength=128; for 24 words, strength=256
    strength = 128 if word_count == 12 else 256
    return mnemo.generate(strength=strength)

def derive_addresses(bip_type, seed_phrase, max_addrs):
    """
    Derives addresses from a given BIP39 seed phrase (seed_phrase)
    using the specified bip_type (bip44, bip49, bip84, bip86).

    Returns dict:
      {
        "account_xprv": str,
        "account_xpub": str,
        "addresses": [ list of derived addresses ]
      }
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
    mnemo = Mnemonic("english")
    if not mnemo.check(seed_phrase):
        raise ValueError("Invalid BIP39 seed phrase (checksum mismatch).")

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

    # Get the "account" node (depth=3): m/purpose'/coin'/account'
    account_node = bip_obj.Purpose().Coin().Account(0)
    account_xprv = account_node.PrivateKey().ToExtended()
    account_xpub = account_node.PublicKey().ToExtended()

    # Derive external addresses [0..max_addrs-1]
    addresses = []
    for i in range(max_addrs):
        child = account_node.Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
        derived_address = child.PublicKey().ToAddress()
        addresses.append(derived_address)

    return {
        "account_xprv": account_xprv,
        "account_xpub": account_xpub,
        "addresses": addresses
    }


###############################################################################
# CHECK WALLET
###############################################################################
def _fetch_data_local(address, rpc_user, rpc_password):
    """
    Fetch Bitcoin address data from local Bitcoin Core using ONLY 'scantxoutset'.
    We do NOT call 'getreceivedbyaddress', so 'disablewallet=1' is okay.

    Returns a dict:
      {
        "final_balance": int    # sat
      }
    or None if there's an error.
    """
    import requests
    from base64 import b64encode

    # Prepare RPC auth header
    auth_str = f"{rpc_user}:{rpc_password}".encode("utf-8")
    auth_b64 = b64encode(auth_str).decode("utf-8")
    headers = {"Authorization": f"Basic {auth_b64}"}

    try:
        # final_balance (in BTC) via scantxoutset
        payload_scantxoutset = {
            "jsonrpc": "1.0",
            "id": "scantxoutset",
            "method": "scantxoutset",
            "params": ["start", [f"addr({address})"]]
        }
        r = requests.post(RPC_URL, json=payload_scantxoutset, headers=headers, timeout=3)
        r.raise_for_status()
        resp = r.json()

        if "error" in resp and resp["error"]:
            log(f"        RPC error (scantxoutset): {resp['error']}")
            return None

        result = resp.get("result", {})
        if not result.get("success", False):
            log("        'scantxoutset' failed or returned no data.")
            return None

        final_balance_btc = result.get("total_amount", 0.0)
        final_balance_sat = int(final_balance_btc * 100_000_000)

        # Return dictionary with final_balance only
        return {
            "final_balance": final_balance_sat
        }

    except requests.RequestException as e:
        log(f"        RequestException fetching data for {address}: {e}")
        return None
    except Exception as e:
        log(f"        Unexpected exception for {address}: {e}")
        return None

def get_local_address_data(address):
    """
    Helper to fetch local RPC data for the given address.
    Returns a dict: {"final_balance": int} or None on failure.
    NO CACHING is applied.
    """
    return _fetch_data_local(address, RPC_USER, RPC_PASSWORD)


###############################################################################
# MAIN SCRIPT LOGIC
###############################################################################
def main():
    parser = argparse.ArgumentParser(
        description="Generate random BIP39 wallets and fetch balances from local Bitcoin Core."
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
        help=(
            "Comma-separated list of BIP derivation types for address generation. "
            "Allowed types: bip44, bip49, bip84, bip86. Example: 'bip84,bip44'"
        )
    )
    parser.add_argument(
        "-l", "--logfile",
        action="store_true",
        help="If given, create a .log file in the script directory with a timestamp."
    )

    args = parser.parse_args()

    # Validate that num_wallets and num_addresses are > 0
    if args.num_wallets < 1:
        log("Error: num_wallets must be at least 1.")
        sys.exit(1)
    if args.num_addresses < 1:
        log("Error: num_addresses must be at least 1.")
        sys.exit(1)

    # Parse comma-separated BIP types
    bip_types_list = [x.strip().lower() for x in args.bip_types.split(",") if x.strip()]
    allowed_bips = {"bip44", "bip49", "bip84", "bip86"}
    if not bip_types_list:
        log("Error: No valid BIP types specified.")
        sys.exit(1)
    # Validate each requested bip
    for bip in bip_types_list:
        if bip not in allowed_bips:
            log(f"Error: Invalid BIP type '{bip}'. Must be one of {', '.join(allowed_bips)}.")
            sys.exit(1)

    # If -l/--logfile is given, create a timestamped log file
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

    num_wallets = args.num_wallets
    num_addresses = args.num_addresses
    total_addrs = num_wallets * num_addresses * len(bip_types_list)

    # Keep track of total balance across all wallets (all bip types)
    grand_total_sat = 0

    log(f"\n===== WALLET RANDOMIZER =====\n")
    log(f"# of Wallets:     {num_wallets}")
    log(f"Addresses/Wallet: {num_addresses}")
    log(f"BIP Type(s):      {', '.join(bip_types_list)}")
    
    log(f"\nTotal addresses:  {total_addrs}")

    for w_i in range(num_wallets):
        log(f"\n\n=== WALLET {w_i + 1}/{num_wallets} ===")

        # Generate a 12-word mnemonic
        mnemonic = generate_random_mnemonic(word_count=12)
        log(f"\n  Generated mnemonic: {mnemonic}")

        # Track the total BTC for this wallet (across all bip types)
        wallet_balance_sat = 0

        # For each requested BIP type, derive addresses & fetch balances
        for bip_type in bip_types_list:
            log(f"\n  == Deriving addresses for {bip_type.upper()} ==\n")
            derivation_info = derive_addresses(bip_type, mnemonic, max_addrs=num_addresses)
            account_xprv = derivation_info["account_xprv"]
            account_xpub = derivation_info["account_xpub"]
            addresses = derivation_info["addresses"]

            log(f"    Account Extended Private Key: {account_xprv}")
            log(f"    Account Extended Public Key:  {account_xpub}")
            log(f"\n    Derived {len(addresses)} addresses:")

            for addr in addresses:
                log(f"      {addr}")
                data = get_local_address_data(addr)
                if data is not None:
                    final_balance_sat = data.get("final_balance", 0)
                    wallet_balance_sat += final_balance_sat
                    final_balance_btc = final_balance_sat / 1e8
                    log(f"        ADDRESS BALANCE: {final_balance_btc} BTC")
                else:
                    log(f"        Could not fetch balance for address: {addr}")

        # Print this wallet's total (across all BIP types)
        wallet_balance_btc = wallet_balance_sat / 1e8
        log(f"\n  WALLET {w_i + 1} TOTAL BALANCE: {wallet_balance_btc} BTC")

        # Add to the grand total
        grand_total_sat += wallet_balance_sat

    # After all wallets, print grand total
    grand_total_btc = grand_total_sat / 1e8
    log("\n\n=== SUMMARY ===")
    log(f"\nGRAND TOTAL BALANCE ACROSS ALL ADDRESSES/WALLETS:\n\n {grand_total_btc} BTC\n")

    # Close log file if opened
    if _log_file is not None:
        _log_file.close()


if __name__ == "__main__":
    main()
