# Wallet Randomizer

**Wallet Randomizer** is a Docker-based application that continuously generates random [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) wallets, derives Bitcoin addresses under various derivation paths (BIP44, BIP49, BIP84, BIP86), and queries their balances using either a local [Fulcrum](https://github.com/cculianu/Fulcrum) Electrum server or the Blockchain.com public API.

The application features a **real-time monitoring web interface** that displays live metrics and wallet generation progress.

---

## Table of Contents
1. [Features](#features)
2. [Requirements](#requirements)
3. [Quick Start](#quick-start)
4. [Web Monitoring Interface](#web-monitoring-interface)
5. [Balance API Options](#balance-api-options)
6. [Setting Up Bitcoin Core and Fulcrum (Windows)](#setting-up-bitcoin-core-and-fulcrum-windows)
7. [Configuration](#configuration)
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

- **Real-Time Monitoring Interface**  
  Live web dashboard with heart-monitor-style graphs showing:
  - Wallets generated per second
  - Addresses checked per second
  - Balance checks per second
  - Cumulative balance found

- **Automatic Background Processing**  
  Wallet generation starts automatically based on .env configuration with no manual intervention required.

- **Flexible Balance Checking**  
  Choose between:
  - **Fulcrum Electrum Server**: Fast, requires local setup
  - **Blockchain.com API**: No setup required, public API (rate limited)

- **Parallel Processing**  
  Utilizes concurrent processing for wallet derivation and balance checks, speeding up bulk address queries.

- **Balance-Based JSON Export**  
  Automatically exports wallet data (mnemonic, derivation type, addresses, and balances) to JSON if the total wallet balance is greater than 0.

- **Docker-Only Deployment**  
  Simplified deployment with Docker Compose for consistent, reproducible environments.

---

## Requirements

- **Docker** and **Docker Compose** installed on your system
- **Balance API** (choose one):
  - **Fulcrum Electrum server** (default `127.0.0.1:50001`) running on your local machine or a reachable host/port, OR
  - **Internet connection** for Blockchain.com public API (no setup required)

---

## Quick Start

### Option 1: Using Blockchain.com API (Easiest)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/barrax63/walletrandomizer.git
   cd walletrandomizer
   ```

2. **Create a `.env` file from the example:**
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` to use Blockchain.com API:**
   ```bash
   BALANCE_API=blockchain
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

### Option 2: Using Fulcrum Server (Faster)

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
   BALANCE_API=fulcrum
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

## Balance API Options

The application supports two methods for checking Bitcoin address balances:

### Fulcrum Electrum Server (Recommended for Speed)

**Pros:**
- Very fast balance queries
- No rate limiting
- Direct connection to Bitcoin network data
- Better for continuous/high-volume scanning

**Cons:**
- Requires running a local Fulcrum server
- Additional setup required

**Configuration:**
```bash
BALANCE_API=fulcrum
FULCRUM_SERVER=192.168.1.100:50001
```

### Blockchain.com Public API (Easiest Setup)

**Pros:**
- No setup required - works out of the box
- No infrastructure needed
- Good for occasional use or testing
- API key support for higher rate limits

**Cons:**
- Slower than Fulcrum (HTTP requests)
- Subject to rate limiting (especially without API key)
- Depends on external service availability

**Configuration:**
```bash
BALANCE_API=blockchain
BLOCKCHAIN_API_URL=https://blockchain.info  # Optional, uses this by default
BLOCKCHAIN_API_KEY=your-api-key-here        # Optional, but recommended for higher rate limits
```

**Authenticated vs Unauthenticated Usage:**

- **Without API Key (Unauthenticated):** Very strict rate limits - suitable only for testing or very low-volume scanning. You may encounter HTTP 429 errors even with just 1 worker.
- **With API Key (Authenticated):** Higher rate limits - better for continuous scanning, though still slower than Fulcrum.

**How to Obtain a Blockchain.com API Key:**

1. Visit [https://www.blockchain.com/api](https://www.blockchain.com/api)
2. Sign up for a free API key
3. Add your API key to the `.env` file as `BLOCKCHAIN_API_KEY=your-api-key-here`

**Note:** For intensive scanning (many wallets/addresses), Fulcrum is still recommended for best performance.

---

## Setting Up Bitcoin Core and Fulcrum (Windows)

To use Fulcrum with this project, you need a fully synced Bitcoin Core node. This section provides step-by-step instructions for setting up both Bitcoin Core and Fulcrum on Windows.

### Prerequisites

- Windows 10 or later (64-bit)
- At least 1 TB of free disk space (for the full Bitcoin blockchain, ~600GB + indexes)
- Stable internet connection
- 8 GB RAM minimum (16 GB recommended)

### Step 1: Install Bitcoin Core

1. **Download Bitcoin Core:**
   - Visit the official Bitcoin Core download page: [https://bitcoincore.org/en/download/](https://bitcoincore.org/en/download/)
   - Download the Windows installer (`bitcoin-<version>-win64-setup.exe`)

2. **Verify the download (recommended):**
   - Download the SHA256 checksums file and verify the installer integrity
   - See [https://bitcoincore.org/en/download/](https://bitcoincore.org/en/download/) for verification instructions

3. **Install Bitcoin Core:**
   - Run the installer and follow the prompts
   - Choose an installation directory (default is fine)
   - When asked about the data directory, choose a location with sufficient space (1 TB+)

4. **Configure Bitcoin Core for Fulcrum:**

   Before starting the initial sync, create or edit the `bitcoin.conf` file:
   
   - Navigate to your Bitcoin data directory (default: `%APPDATA%\Bitcoin\`)
   - Create a file named `bitcoin.conf` if it doesn't exist
   - Add the following configuration:

   ```ini
   # Server mode (required for Fulcrum)
   server=1
   
   # RPC credentials - CHANGE THESE to your own secure values!
   rpcuser=CHANGE_THIS_USERNAME
   rpcpassword=CHANGE_THIS_PASSWORD
   
   # Transaction index (required for Fulcrum)
   txindex=1
   
   # ZeroMQ notifications (optional but recommended)
   zmqpubhashblock=tcp://127.0.0.1:8433
   
   # Prune setting - DO NOT enable pruning if using Fulcrum
   # prune=0 (default, full node)
   
   # Optional: Reduce bandwidth usage during initial sync
   # maxconnections=10
   
   # Optional: Limit upload bandwidth (in KB/s)
   # maxuploadtarget=500
   ```

   **Important:** Replace `CHANGE_THIS_USERNAME` and `CHANGE_THIS_PASSWORD` with your own secure credentials.

5. **Start Bitcoin Core and begin syncing:**
   - Launch Bitcoin Core from the Start menu
   - The initial blockchain download (IBD) will take several days depending on your internet speed and hardware
   - You can monitor progress in the Bitcoin Core GUI or by checking the debug log

6. **Wait for full synchronization:**
   - Bitcoin Core must be fully synced before Fulcrum can start indexing
   - Check the progress bar in Bitcoin Core or use `bitcoin-cli getblockchaininfo`

### Step 2: Install Fulcrum

1. **Download Fulcrum:**
   - Visit the Fulcrum releases page: [https://github.com/cculianu/Fulcrum/releases](https://github.com/cculianu/Fulcrum/releases)
   - Download the latest Windows release (e.g., `Fulcrum-<version>-win64.zip`)

2. **Extract Fulcrum:**
   - Extract the ZIP file to a folder of your choice (e.g., `C:\Fulcrum\`)
   - **Note:** The examples below use `C:\Fulcrum\` as the installation directory. Adjust paths accordingly if you choose a different location.

3. **Create a Fulcrum configuration file:**
   
   Create a file named `fulcrum.conf` in the Fulcrum folder with the following content:

   ```ini
   # Bitcoin Core RPC connection
   bitcoind = 127.0.0.1:8332
   rpcuser = CHANGE_THIS_USERNAME
   rpcpassword = CHANGE_THIS_PASSWORD
   
   # Data directory for Fulcrum indexes (needs ~100-150 GB)
   # Adjust this path if you installed Fulcrum in a different location
   datadir = C:\Fulcrum\data
   
   # TCP port for Electrum protocol (used by this project)
   tcp = 0.0.0.0:50001
   
   # Optional: SSL port (requires certificate)
   # ssl = 0.0.0.0:50002
   # cert = C:\Fulcrum\server.crt
   # key = C:\Fulcrum\server.key
   
   # Performance tuning (see recommendations below)
   # db_max_open_files = 400
   # worker_threads = 4
   # fast_sync = 1
   ```

   **Important:** The `rpcuser` and `rpcpassword` must match your `bitcoin.conf` settings. Replace `CHANGE_THIS_USERNAME` and `CHANGE_THIS_PASSWORD` with the same credentials you used in `bitcoin.conf`.

   **Performance Tuning Recommendations:**

   | Setting | Description | Recommended Values |
   |---------|-------------|-------------------|
   | `db_max_open_files` | Maximum number of database file handles. Higher values improve performance but use more RAM. | **Low-end (8GB RAM):** 200-400<br>**Mid-range (16GB RAM):** 400-800<br>**High-end (32GB+ RAM):** 1000-2000 |
   | `worker_threads` | Number of threads for processing client requests. Should generally match or be slightly less than your CPU core count. | **4-core CPU:** 4<br>**6-core CPU:** 6<br>**8+ core CPU:** 8-12 |
   | `fast_sync` | Enables faster initial sync at the cost of higher memory usage. Set to `0` on systems with limited RAM. | **8GB RAM:** 0 (disabled)<br>**16GB+ RAM:** 1 (enabled) |
   | `db_mem` | Database cache size in MB. Higher values speed up initial sync and queries. | **8GB RAM:** 256-512<br>**16GB RAM:** 1024-2048<br>**32GB+ RAM:** 2048-4096 |

   **Example configurations:**

   *Low-end system (8GB RAM, 4-core CPU):*
   ```ini
   db_max_open_files = 300
   worker_threads = 4
   fast_sync = 0
   db_mem = 512
   ```

   *Mid-range system (16GB RAM, 6-8 core CPU):*
   ```ini
   db_max_open_files = 600
   worker_threads = 6
   fast_sync = 1
   db_mem = 1536
   ```

   *High-end system (32GB+ RAM, 8+ core CPU):*
   ```ini
   db_max_open_files = 1500
   worker_threads = 10
   fast_sync = 1
   db_mem = 4096
   ```

   **Note:** After changing these settings, restart Fulcrum for them to take effect. Monitor your system's memory usage during initial sync and adjust values if needed.

4. **Create the data directory:**
   
   Adjust the path if you installed Fulcrum in a different location:
   ```cmd
   mkdir C:\Fulcrum\data
   ```

5. **Start Fulcrum for initial sync:**
   
   Open Command Prompt, navigate to your Fulcrum installation folder, and run:
   ```cmd
   cd C:\Fulcrum
   Fulcrum.exe fulcrum.conf
   ```
   
   **Note:** Adjust `C:\Fulcrum` to your actual installation directory if different.

   **Initial indexing notes:**
   - First-time indexing takes several hours (8-24+ hours depending on hardware)
   - Fulcrum will create a ~100-150 GB index database
   - You can monitor progress in the console output
   - SSD storage is highly recommended for the data directory

6. **Verify Fulcrum is running:**
   - Once indexing is complete, Fulcrum will show `Listening on 0.0.0.0:50001`
   - You can test the connection with: `telnet 127.0.0.1 50001`

### Step 3: Configure Wallet Randomizer to Use Fulcrum

1. **Edit your `.env` file:**
   ```bash
   BALANCE_API=fulcrum
   FULCRUM_SERVER=127.0.0.1:50001
   ```

   If running Docker on Windows with WSL2 or Docker Desktop, you may need to use your Windows host IP instead of `127.0.0.1`. To find your IP:
   ```cmd
   ipconfig
   ```
   Look for the IPv4 address of your network adapter (e.g., `192.168.1.100`).

2. **Ensure Windows Firewall allows connections:**
   - Open Windows Defender Firewall
   - Click "Allow an app or feature through Windows Defender Firewall"
   - Add Fulcrum.exe or create an inbound rule for port 50001

3. **Start the Wallet Randomizer:**
   ```bash
   docker-compose up -d
   ```

4. **Verify the connection:**
   - Access the dashboard at `http://localhost:5000`
   - Check that wallet generation is proceeding without connection errors

### Running Fulcrum as a Windows Service (Optional)

For continuous operation, you can run Fulcrum as a Windows service using tools like [NSSM (Non-Sucking Service Manager)](https://nssm.cc/):

1. Download and extract NSSM
2. Open Command Prompt as Administrator
3. Run:
   ```cmd
   nssm install Fulcrum
   ```
4. Configure the service (adjust paths to match your installation directory):
   - **Path:** `C:\Fulcrum\Fulcrum.exe`
   - **Arguments:** `C:\Fulcrum\fulcrum.conf`
   - **Startup directory:** `C:\Fulcrum`
5. Start the service:
   ```cmd
   nssm start Fulcrum
   ```

### Troubleshooting

**Connection refused errors:**
- Verify Bitcoin Core is running and fully synced
- Check that Fulcrum is running and has completed initial indexing
- Ensure Windows Firewall is not blocking connections on port 50001
- If using Docker Desktop, try using the host's LAN IP instead of `127.0.0.1`

**Fulcrum fails to connect to Bitcoin Core:**
- Verify `rpcuser` and `rpcpassword` match in both `bitcoin.conf` and `fulcrum.conf`
- Ensure `server=1` is set in `bitcoin.conf`
- Check that Bitcoin Core's RPC port (8332) is accessible

**Slow performance:**
- Ensure Fulcrum's data directory is on an SSD
- Increase `worker_threads` in `fulcrum.conf` if you have spare CPU cores
- Allow Fulcrum to complete initial indexing before heavy usage

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
# Choose balance API
BALANCE_API=blockchain  # or "fulcrum"

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

### Balance API Configuration

| Variable | Description | Required | Default | Valid Values |
|----------|-------------|----------|---------|--------------|
| `BALANCE_API` | Balance checking method | No | `fulcrum` | `fulcrum`, `blockchain` |

### Fulcrum Server Configuration (if BALANCE_API=fulcrum)

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `FULCRUM_SERVER` | Fulcrum server in format `host:port` (parsed into HOST and PORT) | **Yes*** | `192.168.1.100:50001` |
| `FULCRUM_HOST` | Fulcrum server host (alternative to FULCRUM_SERVER) | No | `192.168.1.100` |
| `FULCRUM_PORT` | Fulcrum server port (alternative to FULCRUM_SERVER) | No | `50001` |

\* Required only when `BALANCE_API=fulcrum`. You can use either `FULCRUM_SERVER` (which is automatically split into host and port) or specify `FULCRUM_HOST` and `FULCRUM_PORT` separately.

### Blockchain.com API Configuration (if BALANCE_API=blockchain)

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `BLOCKCHAIN_API_URL` | Blockchain.com API base URL | No | `https://blockchain.info` |
| `BLOCKCHAIN_API_KEY` | Blockchain.com API key for authenticated requests (higher rate limits) | No | None (unauthenticated) |

**Note:** Without `BLOCKCHAIN_API_KEY`, the application uses unauthenticated API with very strict rate limits. It's highly recommended to obtain a free API key from [blockchain.com/api](https://www.blockchain.com/api) to avoid rate limiting errors.

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
