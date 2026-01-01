# Wallet Randomizer

**Wallet Randomizer** is a Docker-based application that generates random [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) wallets, derives Bitcoin addresses under various derivation paths (BIP44, BIP49, BIP84, BIP86), and queries their balances using a local [Fulcrum](https://github.com/cculianu/Fulcrum) Electrum server.

The application provides both a **web interface** and a **command-line interface**, both running in Docker containers.

---

## Table of Contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Quick Start](#quick-start)
4. [Web Interface](#web-interface)
5. [Command-Line Interface](#command-line-interface)
6. [Configuration](#configuration)
7. [Docker Services](#docker-services)
8. [Environment Variables](#environment-variables)
9. [Examples](#examples)
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

- **Web Interface**  
  Modern, responsive web UI for easy wallet generation and balance checking.

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

3. **Edit `.env` and configure your Fulcrum server:**
   ```bash
   FULCRUM_SERVER=192.168.1.100:50001
   MODE=web
   ```

4. **Start the web interface:**
   ```bash
   docker-compose up -d
   ```

5. **Access the web interface:**
   Open your browser and navigate to `http://localhost:5000`

---

## Web Interface

The web interface provides a user-friendly way to generate wallets and check balances.

### Starting the Web Interface

```bash
docker-compose up -d
```

The web server will be available at `http://localhost:5000` (or the port specified in your `.env` file).

### Features

- **Landing Page:** Overview of the application and its features
- **Wallet Generator:** Interactive form to configure and generate wallets
- **Real-time Results:** View generated wallets, addresses, and balances
- **Status Indicators:** Connection status and operation progress
- **Responsive Design:** Works on desktop, tablet, and mobile devices

### Web Interface Configuration

Configure the web interface using environment variables in your `.env` file:

```bash
MODE=web
FULCRUM_SERVER=192.168.1.100:50001
WEB_HOST=0.0.0.0
WEB_PORT=5000
WEB_WORKERS=4
WEB_TIMEOUT=120
```

### Accessing Exported Wallets

Wallets with non-zero balances are automatically exported to JSON files in the Docker volume:

```bash
# List exported wallets
docker-compose exec web ls -la /data

# Copy a wallet file to your local machine
docker cp $(docker-compose ps -q web):/data/<wallet-file>.json ./
```

---

## Command-Line Interface

For advanced users or automated workflows, the CLI mode is available.

### Running CLI Mode

**Option 1: Using Docker Compose (uncomment the CLI service in docker-compose.yml)**

Edit `docker-compose.yml` and uncomment the `cli` service, then:

```bash
docker-compose up cli
```

**Option 2: Using Docker directly**

```bash
docker run --rm \
  -e MODE=cli \
  -e FULCRUM_SERVER=192.168.1.100:50001 \
  -e NUM_WALLETS=10 \
  -e NUM_ADDRESSES=5 \
  -e NETWORK=bip44,bip84 \
  -e OUTPUT_PATH=/data \
  -v $(pwd)/output:/data \
  barrax63/walletrandomizer:latest
```

### CLI Features

- **Infinite Wallet Generation:** Set `NUM_WALLETS=-1` for continuous wallet generation
- **Multiple BIP Types:** Comma-separated list (e.g., `bip44,bip49,bip84,bip86`)
- **Configurable Output:** Set output directory with `OUTPUT_PATH`

---

## Configuration

### Creating a `.env` File

Copy the example configuration:

```bash
cp .env.example .env
```

Edit the `.env` file with your preferred settings. See [Environment Variables](#environment-variables) for all available options.

---

## Docker Services

### Web Service (Default)

The web service provides the HTTP interface for wallet generation.

```yaml
services:
  web:
    image: barrax63/walletrandomizer:latest
    ports:
      - "5000:5000"
    environment:
      - MODE=web
      - FULCRUM_SERVER=127.0.0.1:50001
    volumes:
      - walletrandomizer_storage:/data
```

### CLI Service (Optional)

The CLI service can run alongside or instead of the web service for automated workflows.

```yaml
services:
  cli:
    image: barrax63/walletrandomizer:latest
    environment:
      - MODE=cli
      - FULCRUM_SERVER=127.0.0.1:50001
      - NUM_WALLETS=10
      - NUM_ADDRESSES=5
      - NETWORK=bip84
    volumes:
      - walletrandomizer_storage:/data
```

---

## Environment Variables

### Mode Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MODE` | Run mode: `web` or `cli` | `cli` | No |

### Fulcrum Server Configuration

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `FULCRUM_SERVER` | Fulcrum server in format `host:port` | **Yes*** | `192.168.1.100:50001` |
| `FULCRUM_HOST` | Fulcrum server host (alternative to FULCRUM_SERVER) | No | `192.168.1.100` |
| `FULCRUM_PORT` | Fulcrum server port (alternative to FULCRUM_SERVER) | No | `50001` |

\* Required for CLI mode. For web mode, you can use either `FULCRUM_SERVER` or both `FULCRUM_HOST` and `FULCRUM_PORT`.

### Wallet Generation Configuration

| Variable | Description | Default | Valid Values |
|----------|-------------|---------|--------------|
| `NUM_WALLETS` | Number of wallets to generate (CLI: -1 for infinite) | `10` (CLI), `1` (web) | ≥1 or -1 |
| `NUM_ADDRESSES` | Number of addresses per wallet | `5` | ≥1 |
| `NETWORK` | Comma-separated BIP types | `bip84` | `bip44,bip49,bip84,bip86` |
| `OUTPUT_PATH` | Output directory for JSON files | `/data` | Any valid path |
| `FORMAT` | Output format | `json` | `json` |

### Web Server Configuration (web mode only)

| Variable | Description | Default |
|----------|-------------|---------|
| `WEB_HOST` | Web server host | `0.0.0.0` |
| `WEB_PORT` | Web server port | `5000` |
| `WEB_WORKERS` | Number of gunicorn workers | `4` |
| `WEB_TIMEOUT` | Request timeout in seconds | `120` |

---

## Examples

### Example 1: Web Interface with Custom Configuration

Create a `.env` file:

```bash
MODE=web
FULCRUM_SERVER=10.0.0.15:60001
NUM_ADDRESSES=10
NETWORK=bip84,bip86
WEB_PORT=8080
```

Start the service:

```bash
docker-compose up -d
```

Access at `http://localhost:8080`

### Example 2: CLI Mode - Generate 100 Wallets

```bash
docker run --rm \
  -e MODE=cli \
  -e FULCRUM_SERVER=10.0.0.15:60001 \
  -e NUM_WALLETS=100 \
  -e NUM_ADDRESSES=10 \
  -e NETWORK=bip44,bip84,bip86 \
  -v $(pwd)/output:/data \
  barrax63/walletrandomizer:latest
```

### Example 3: Infinite Wallet Generation (CLI)

Create a `.env` file:

```bash
MODE=cli
FULCRUM_SERVER=192.168.1.100:50001
NUM_WALLETS=-1
NUM_ADDRESSES=5
NETWORK=bip84
```

Start the service:

```bash
docker-compose up cli
```

Press CTRL+C to stop gracefully.

### Example 4: Building and Running Locally

```bash
# Build the image
docker build -t walletrandomizer:latest .

# Run web interface
docker run --rm \
  -e MODE=web \
  -e FULCRUM_SERVER=127.0.0.1:50001 \
  -p 5000:5000 \
  -v $(pwd)/data:/data \
  walletrandomizer:latest

# Run CLI
docker run --rm \
  -e MODE=cli \
  -e FULCRUM_SERVER=127.0.0.1:50001 \
  -e NUM_WALLETS=10 \
  -e NUM_ADDRESSES=5 \
  -e NETWORK=bip84 \
  -v $(pwd)/data:/data \
  walletrandomizer:latest
```

---

## Author

Noah Nowak
