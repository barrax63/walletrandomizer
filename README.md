# Wallet Randomizer

**Wallet Randomizer** (`walletrandomizer.py`) is a Python script that generates random [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) wallets, derives Bitcoin addresses under various derivation paths (BIP44, BIP49, BIP84, BIP86), and then queries their balances using a local [Fulcrum](https://github.com/cculianu/Fulcrum) Electrum server.

The script can export any wallet with a non-zero balance to a JSON file for further analysis. It is primarily intended for experimentation and educational purposes, or for specialized use cases where you need to quickly generate and check multiple wallet addresses.

---

## Table of Contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Usage](#usage)
   - [Direct Python Usage](#direct-python-usage)
   - [Docker/Compose Usage](#dockercompose-usage)
5. [Command-Line Arguments](#command-line-arguments)
6. [Environment Variables (Docker/Compose)](#environment-variables-dockercompose)
7. [Infinite Wallet Generation](#infinite-wallet-generation)
8. [Logging](#logging)
9. [Example](#example)
10. [Author](#author)

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
  Checks each derived address's final balance by querying a Fulcrum Electrum server (via TCP).

- **Parallel Processing**  
  Utilizes `ProcessPoolExecutor` for wallet derivation and `ThreadPoolExecutor` for concurrent balance checks, speeding up bulk address queries.

- **Balance-Based JSON Export**  
  Automatically exports wallet data (mnemonic, derivation type, addresses, and balances) to JSON if the total wallet balance is greater than 0.

- **Graceful CTRL+C Handling**  
  Completes the current wallet's balance checks before stopping, preserving a partial summary.

- **Infinite Wallet Generation**  
  Generate wallets indefinitely by setting `--num-wallets -1` or `NUM_WALLETS=-1` (Docker), useful for continuous scanning.

- **Docker/Compose Support**  
  Containerized deployment with environment variable configuration for easy integration and deployment.

---

## Requirements

This script requires:

- **Python 3.10 or 3.11** (or use the provided Docker image)
- The following Python libraries:
  - [mnemonic](https://pypi.org/project/mnemonic/)
  - [bip_utils](https://pypi.org/project/bip_utils/)
  - [base58](https://pypi.org/project/base58/)
  - [tqdm](https://pypi.org/project/tqdm/)

It also requires access to a **Fulcrum Electrum server** (default `127.0.0.1:50001`) running on your local machine or a reachable host/port.

---

## Installation

### Direct Installation

1. **Clone** or **download** this repository.

2. **Install dependencies** in your Python environment:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) **Set up Fulcrum** locally or ensure you have network access to a Fulcrum server.

### Docker Installation

1. **Clone** or **download** this repository.

2. **Build the Docker image** (or use docker-compose):
   ```bash
   docker build -t walletrandomizer:latest .
   ```

---

## Usage

### Direct Python Usage

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

**Infinite wallet generation:**
```bash
python walletrandomizer.py --num-wallets -1 5 bip44,bip84 --server 127.0.0.1 --port 50001
```
This will generate wallets indefinitely until interrupted with CTRL+C.

### Docker/Compose Usage

The easiest way to run the wallet randomizer is with Docker Compose.

1. **Create a `.env` file** in the project directory with your configuration:
   ```bash
   FULCRUM_SERVER=192.168.1.100:50001
   NUM_WALLETS=100
   NUM_ADDRESSES=10
   NETWORK=bip44,bip84,bip86
   OUTPUT_PATH=/data
   ```

2. **Run with Docker Compose:**
   ```bash
   docker-compose up
   ```

3. **Access generated wallet files:**
   Wallet JSON files with non-zero balances will be saved to the mounted volume.
   ```bash
   docker volume inspect walletrandomizer_wallet-data
   ```

**Infinite mode with Docker Compose:**
Set `NUM_WALLETS=-1` in your `.env` file:
```bash
FULCRUM_SERVER=192.168.1.100:50001
NUM_WALLETS=-1
NUM_ADDRESSES=5
NETWORK=bip84
OUTPUT_PATH=/data
```

**Run directly with Docker:**
```bash
docker run --rm \
  -e FULCRUM_SERVER=192.168.1.100:50001 \
  -e NUM_WALLETS=10 \
  -e NUM_ADDRESSES=5 \
  -e NETWORK=bip44,bip84 \
  -e OUTPUT_PATH=/data \
  -v $(pwd)/output:/data \
  walletrandomizer:latest
```

---

## Command-Line Arguments

| Argument          | Description                                                                                                                         | Required | Default      |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------|----------|--------------|
| `num_wallets`     | Number of wallets to generate. Must be ≥ 1, or -1 for infinite generation.                                                         | Yes*     | N/A          |
| `num_addresses`   | Number of addresses per wallet. Must be ≥ 1.                                                                                        | Yes      | N/A          |
| `bip_types`       | Comma-separated list of BIP derivation types. Possible values: `bip44`, `bip49`, `bip84`, `bip86`.                                  | Yes*     | N/A          |
| `--num-wallets`   | Alternative flag for num_wallets (takes precedence over positional).                                                                | No       | N/A          |
| `--network`       | Alternative flag for bip_types (takes precedence over positional).                                                                  | No       | N/A          |
| `--output`        | Output directory for wallet JSON files.                                                                                              | No       | `.` (current)|
| `--format`        | Output format.                                                                                                                       | No       | `json`       |
| `-v, --verbose`   | Enable verbose (debug-level) messages in the console.                                                                               | No       | False        |
| `-L, --logfile`   | Create a rotating `.log` file in the script directory with a timestamp.                                                             | No       | False        |
| `-w, --wordcount` | Mnemonic word count. Choose between `12` or `24`.                                                                                   | No       | 12           |
| `-l, --language`  | BIP39 mnemonic language. Options: `english`, `french`, `italian`, `spanish`, `korean`, `chinese_simplified`, `chinese_traditional`. | No       | `english`    |
| `-s, --server`    | Fulcrum server IP address.                                                                                                          | No       | `127.0.0.1`  |
| `-p, --port`      | Fulcrum server TCP port.                                                                                                            | No       | `50001`      |

\* Required unless provided via flag alternative (--num-wallets, --network).

### Notes on Usage
- **`<num_wallets>`** and **`<num_addresses>`** are integers that specify how many wallets to generate and how many addresses to derive for each wallet.
- **`bip_types`** should be a comma-separated string with at least one of the following: `bip44, bip49, bip84, bip86`. Example: `bip44,bip84`.
- **Infinite mode:** Set `num_wallets` or `--num-wallets` to `-1` to generate wallets indefinitely.

---

## Environment Variables (Docker/Compose)

When using Docker or Docker Compose, configure the wallet randomizer using environment variables:

| Variable          | Description                                                                 | Required | Default          |
|-------------------|-----------------------------------------------------------------------------|----------|------------------|
| `FULCRUM_SERVER`  | Fulcrum server address in format `host:port` (e.g., `192.168.1.100:50001`) | **Yes**  | N/A              |
| `NUM_WALLETS`     | Number of wallets to generate (use `-1` for infinite)                       | No       | `10`             |
| `NUM_ADDRESSES`   | Number of addresses per wallet                                              | No       | `5`              |
| `NETWORK`         | Comma-separated BIP types (e.g., `bip44,bip84,bip86`)                       | No       | `bip44,bip84`    |
| `OUTPUT_PATH`     | Directory for output JSON files (inside container)                          | No       | `/data`          |
| `FORMAT`          | Output format                                                                | No       | `json`           |

**Example `.env` file:**
```bash
FULCRUM_SERVER=192.168.1.100:50001
NUM_WALLETS=100
NUM_ADDRESSES=10
NETWORK=bip84,bip86
OUTPUT_PATH=/data
```

---

## Infinite Wallet Generation

The wallet randomizer supports **infinite wallet generation mode**, which continuously generates and checks wallets until manually stopped.

**To enable infinite mode:**
- Direct usage: `python walletrandomizer.py --num-wallets -1 5 bip84 --server 127.0.0.1`
- Docker/Compose: Set `NUM_WALLETS=-1` in your environment variables

**Features in infinite mode:**
- Wallets are generated continuously
- Progress bar shows total wallets processed (not percentage)
- Press CTRL+C to gracefully stop after the current wallet completes
- Summary shows total wallets processed (not X/Y format)

**Use cases:**
- Continuous scanning for wallets with balances
- Long-running discovery operations
- Automated wallet generation pipelines

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
    --language italian \
    --server 10.0.0.15 \
    --port 60001 \
    --output /tmp/wallets
```

1. **Generates 3 wallets**.  
2. **Each wallet** has 2 derived addresses per BIP type (BIP44, BIP49, BIP84).  
3. **24-word** BIP39 mnemonics in **Italian**.  
4. **Verbose output** to the console and **logs** to a timestamped `.log` file.
5. **Fulcrum** server at `10.0.0.15` port `60001`.
6. **Output** JSON files saved to `/tmp/wallets`.

Any wallet found to have a **non-zero balance** (across all addresses) will be exported to a randomly named `.json` file.

**Docker Compose example:**
```bash
# Create .env file
cat > .env << EOF
FULCRUM_SERVER=10.0.0.15:60001
NUM_WALLETS=3
NUM_ADDRESSES=2
NETWORK=bip44,bip49,bip84
OUTPUT_PATH=/data
EOF

# Run with docker-compose
docker-compose up
```

---

## Author

Noah Nowak
