# Wallet Randomizer

**Wallet Randomizer** (`walletrandomizer.py`) is a Python script that generates random [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) wallets, derives Bitcoin addresses under various derivation paths (BIP44, BIP49, BIP84, BIP86), and then queries their balances using a local [Fulcrum](https://github.com/cculianu/Fulcrum) Electrum server.

The script can export any wallet with a non-zero balance to a JSON file for further analysis. It is primarily intended for experimentation and educational purposes, or for specialized use cases where you need to quickly generate and check multiple wallet addresses.

---

## Table of Contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Command-Line Arguments](#command-line-arguments)
6. [Environment Variables](#environment-variables)
7. [Logging](#logging)
8. [Example](#example)
9. [Directory Structure](#directory-structure)
10. [License](#license)

---

## Features

- **BIP39 Mnemonic Generation**  
  Automatically generates secure BIP39 mnemonics (12 or 24 words in multiple languages).

- **Address Derivation (BIP44, BIP49, BIP84, BIP86)**  
  Derives addresses for multiple derivation paths:
  - BIP44: Legacy (P2PKH)
  - BIP49: Nested SegWit (P2SH-P2WPKH)
  - BIP84: Native SegWit (P2WPKH)
  - BIP86: Taproot (P2TR)

- **Local Fulcrum Queries**  
  Checks each derived address’s final balance by querying a local Fulcrum Electrum server (via TCP).

- **Parallel Processing**  
  Utilizes `ProcessPoolExecutor` for wallet derivation and `ThreadPoolExecutor` for concurrent balance checks, speeding up bulk address queries.

- **Balance-Based JSON Export**  
  Automatically exports wallet data (mnemonic, derivation type, addresses, and balances) to JSON if the total wallet balance is greater than 0.

- **Graceful CTRL+C Handling**  
  Completes the current wallet’s balance checks before stopping, preserving a partial summary.

---

## Requirements

This script requires:

- **Python 3.10 or 3.11**
- The following Python libraries:
  - [mnemonic](https://pypi.org/project/mnemonic/)
  - [bip_utils](https://pypi.org/project/bip_utils/)
  - [base58](https://pypi.org/project/base58/)
  - [python-dotenv](https://pypi.org/project/python-dotenv/)
  - [tqdm](https://pypi.org/project/tqdm/)

It also requires access to a **Fulcrum Electrum server** (default `127.0.0.1:50001`) running on your local machine or a reachable host/port.

---

## Installation

1. **Clone** or **download** this repository.

2. **Install dependencies** in your Python environment:
   ```bash
   pip install mnemonic bip_utils base58 python-dotenv tqdm
   ```

3. (Optional) **Set up Fulcrum** locally or ensure you have network access to a Fulcrum server.

4. (Optional) **Create a `.env` file** if you need custom settings (e.g., host/port for Fulcrum). See [Environment Variables](#environment-variables).

---

## Usage

Run the script directly from a terminal:
```bash
./walletrandomizer.py <num_wallets> <num_addresses> <bip_types> [options]
```
Or explicitly with Python:
```bash
python walletrandomizer.py <num_wallets> <num_addresses> <bip_types> [options]
```

**Example quick run:**
```bash
python walletrandomizer.py 10 5 bip44,bip84
```
This command will generate 10 wallets, each with 5 addresses derived under BIP44 and BIP84, then query balances on each derived address.

---

## Command-Line Arguments

| Argument          | Description                                                                                                                         | Required | Default      |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------|----------|--------------|
| `num_wallets`     | Number of wallets to generate. Must be ≥ 1.                                                                                         | Yes      | N/A          |
| `num_addresses`   | Number of addresses per wallet. Must be ≥ 1.                                                                                        | Yes      | N/A          |
| `bip_types`       | Comma-separated list of BIP derivation types. Possible values: `bip44`, `bip49`, `bip84`, `bip86`.                                  | Yes      | N/A          |
| `-v, --verbose`   | Enable verbose (debug-level) messages in the console.                                                                               | No       | False        |
| `-L, --logfile`   | Create a rotating `.log` file in the script directory with a timestamp.                                                             | No       | False        |
| `-w, --wordcount` | Mnemonic word count. Choose between `12` or `24`.                                                                                   | No       | 12           |
| `-l, --language`  | BIP39 mnemonic language. Options: `english`, `french`, `italian`, `spanish`, `korean`, `chinese_simplified`, `chinese_traditional`. | No       | `english`    |

### Notes on Usage
- **`<num_wallets>`** and **`<num_addresses>`** are integers that specify how many wallets to generate and how many addresses to derive for each wallet.
- **`bip_types`** should be a comma-separated string with at least one of the following: `bip44, bip49, bip84, bip86`. Example: `bip44,bip84`.

---

## Environment Variables

You can override the default Fulcrum server host and port by defining a `.env` file in the same directory as `walletrandomizer.py`, containing:

```ini
FULCRUM_HOST=127.0.0.1
FULCRUM_PORT=50001
```

- If no `.env` is found, the script defaults to `127.0.0.1:50001`.
- You can run Fulcrum on the same machine or point this to a remote Fulcrum instance if reachable.

---

## Logging

- **`-v/--verbose`**: Enables verbose console logs.  
- **`-L/--logfile`**: Writes logs to a rotating file (`.log`) in the script directory.
  - If you combine both flags, you will get detailed console output **and** a log file with the same info.

Log rotation is configured to rotate after the log file reaches ~250MB, keeping up to **40 backups**.

---

## Example

Below is an example of a full command, illustrating most options:

```bash
python walletrandomizer.py 3 2 bip44,bip49,bip84 \
    --verbose \
    --logfile \
    --wordcount 24 \
    --language italian
```

1. **Generates 3 wallets**.  
2. **Each wallet** has 2 derived addresses per BIP type (BIP44, BIP49, BIP84).  
3. **24-word** BIP39 mnemonics in **Italian**.  
4. **Verbose output** to the console and **logs** to a timestamped `.log` file.

Any wallet found to have a **non-zero balance** (across all addresses) will be exported to a randomly named `.json` file.

---

## Directory Structure

Typical layout after cloning:

```
.
├─ walletrandomizer.py
└─ README.md
```

---

## Author

Noah Nowak
