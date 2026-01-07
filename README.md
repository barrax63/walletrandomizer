# Wallet Randomizer

**Wallet Randomizer** is a Docker-based application that continuously generates random [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) wallets, derives Bitcoin addresses under various derivation paths (BIP44, BIP49, BIP84, BIP86), and queries their balances using a local [Fulcrum](https://github.com/cculianu/Fulcrum) Electrum server.

The application features a **real-time monitoring web interface** that displays live metrics and wallet generation progress.

---

## Table of Contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Quick Start](#quick-start)
4. [Web Monitoring Interface](#web-monitoring-interface)
5. [Configuration](#configuration)
6. [Environment Variables](#environment-variables)
7. [Examples](#examples)
8. [Author](#author)

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

- **Real-Time Monitoring Interface**  
  Live web dashboard with heart-monitor-style graphs showing:
  - Wallets generated per second
  - Addresses checked per second
  - Balance checks per second
  - Cumulative balance found

- **Automatic Background Processing**  
  Wallet generation starts automatically based on .env configuration with no manual intervention required.

- **Local Fulcrum Queries**  
  Checks each derived address's final balance by querying a Fulcrum Electrum server (via TCP).

- **Parallel Processing**  
  Utilizes concurrent processing for wallet derivation and balance checks, speeding up bulk address queries.

- **Balance-Based JSON Export**  
  Automatically exports wallet data (mnemonic, derivation type, addresses, and balances) to JSON if the total wallet balance is greater than 0.

- **Docker-Only Deployment**  
  Simplified deployment with Docker Compose for consistent, reproducible environments.

---

## Requirements

- **Docker** and **Docker Compose** installed on your system
- Access to a **Fulcrum Electrum server** (default `127.0.0.1:50001`) running on your local machine or a reachable host/port

---

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/barrax63/walletrandomizer.git
   cd walletrandomizer
   ```

2. **Create a `.env` file from the example:**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` and configure your settings:**
   ```bash
   FULCRUM_SERVER=192.168.1.100:50001
   NUM_WALLETS=-1  # -1 for infinite generation
   NUM_ADDRESSES=5
   NETWORK=bip84
   ```

4. **Start the monitoring interface:**
   ```bash
   docker-compose up -d
   ```

5. **Access the monitoring dashboard:**
   Open your browser and navigate to `http://localhost:5000`

   The wallet generation process starts automatically in the background!

---

## Web Monitoring Interface

The monitoring interface provides real-time visualization of the wallet generation process.

### Starting the Monitor

```bash
docker-compose up -d
```

The monitoring dashboard will be available at `http://localhost:5000` (or the port specified in your `.env` file).

### Dashboard Features

- **Live Performance Metrics**
  - Wallets/second graph (heart-monitor style)
  - Addresses/second graph
  - Balance checks/second graph
  - Cumulative balance found graph

- **Current Statistics**
  - Total wallets processed
  - Wallets with balance found
  - Total BTC balance discovered
  - Runtime duration

- **Configuration Display**
  - Shows active configuration parameters
  - Fulcrum server connection status

- **Recent Wallets Feed**
  - Last 10 wallets generated
  - Highlighted when balance found
  - Truncated mnemonic display
  - BIP types and addresses checked

### Auto-Start Behavior

When you start the container, wallet generation begins automatically based on your `.env` configuration. No manual trigger is required - just open the dashboard to monitor progress.

### Accessing Exported Wallets

Wallets with non-zero balances are automatically exported to JSON files in the Docker volume:

```bash
# List exported wallets
docker-compose exec walletrandomizer ls -la /data

# Copy a wallet file to your local machine
docker cp $(docker-compose ps -q walletrandomizer):/data/<wallet-file>.json ./
```

---

## Configuration

### Creating a `.env` File

Copy the example configuration:

```bash
cp .env.example .env
```

Edit the `.env` file with your preferred settings. See [Environment Variables](#environment-variables) for all available options.

### Key Configuration Options

```bash
# Infinite wallet generation (recommended for continuous monitoring)
NUM_WALLETS=-1

# Number of addresses to check per wallet
NUM_ADDRESSES=5

# BIP derivation types (comma-separated)
NETWORK=bip84,bip86

# Mnemonic settings
WORD_COUNT=12
LANGUAGE=english
```

---

## Environment Variables

### Fulcrum Server Configuration

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `FULCRUM_SERVER` | Fulcrum server in format `host:port` | **Yes** | `192.168.1.100:50001` |
| `FULCRUM_HOST` | Fulcrum server host (alternative) | No | `192.168.1.100` |
| `FULCRUM_PORT` | Fulcrum server port (alternative) | No | `50001` |

### Wallet Generation Configuration

| Variable | Description | Default | Valid Values |
|----------|-------------|---------|--------------|
| `NUM_WALLETS` | Number of wallets to generate (-1 for infinite) | `-1` | ≥1 or -1 |
| `NUM_ADDRESSES` | Number of addresses per wallet | `5` | ≥1 |
| `NETWORK` | Comma-separated BIP types | `bip84` | `bip44,bip49,bip84,bip86` |
| `WORD_COUNT` | Mnemonic word count | `12` | `12` or `24` |
| `LANGUAGE` | Mnemonic language | `english` | See below |
| `OUTPUT_PATH` | Output directory for JSON files | `/data` | Any valid path |

**Supported Languages:** `english`, `french`, `italian`, `spanish`, `korean`, `chinese_simplified`, `chinese_traditional`

### Web Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `WEB_HOST` | Web server host | `0.0.0.0` |
| `WEB_PORT` | Web server port | `5000` |
| `WEB_WORKERS` | Number of uvicorn workers | `4` |
| `WEB_TIMEOUT` | Request timeout in seconds | `120` |

---

## Examples

### Example 1: Infinite Generation with Multiple BIP Types

Create a `.env` file:

```bash
FULCRUM_SERVER=10.0.0.15:60001
NUM_WALLETS=-1
NUM_ADDRESSES=10
NETWORK=bip84,bip86
WORD_COUNT=12
LANGUAGE=english
```

Start the service:

```bash
docker-compose up -d
```

Access the monitoring dashboard at `http://localhost:5000` to watch the live generation process.

### Example 2: Limited Generation with All BIP Types

```bash
FULCRUM_SERVER=192.168.1.100:50001
NUM_WALLETS=1000
NUM_ADDRESSES=5
NETWORK=bip44,bip49,bip84,bip86
WORD_COUNT=24
LANGUAGE=english
```

This will generate exactly 1000 wallets with 24-word mnemonics, checking all BIP types.

### Example 3: Building and Running Locally

```bash
# Build the image
docker build -t walletrandomizer:latest .

# Run with environment variables
docker run --rm \
  -e FULCRUM_SERVER=127.0.0.1:50001 \
  -e NUM_WALLETS=-1 \
  -e NUM_ADDRESSES=5 \
  -e NETWORK=bip84 \
  -p 5000:5000 \
  -v $(pwd)/data:/data \
  walletrandomizer:latest
```

Access the dashboard at `http://localhost:5000`

---

## Author

Noah Nowak
