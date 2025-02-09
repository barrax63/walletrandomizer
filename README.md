## Wallet Randomizer

This Python script allows you to generate multiple random BIP39 wallets, derive addresses for various BIP types, and **check their balances** using a **local Fulcrum Electrum server** in cunjunction with a Bitcoin Core server. You can specify multiple BIP derivation types, set the mnemonic **word count** (12 or 24), choose **different languages**, and optionally log all output to a timestamped file.

---

### Features

1. **Random Mnemonic Generation**  
   - Generates a random **BIP39 mnemonic** in **12 words** (default) or **24 words** with the `-w/--wordcount` flag.  
   - Supports **various languages**—English, French, Italian, Spanish, Korean, Chinese Simplified, Chinese Traditional—via `--language`.

2. **Multiple BIP Types**  
   - Specify one or more derivation types in a comma-separated list (e.g. `bip84,bip49,bip44,bip86`), and the script derives addresses for **each** type from the same mnemonic.

3. **Fulcrum (Electrum) Balances**  
   - Uses `blockchain.scripthash.get_balance` calls to fetch final balances from your **Fulcrum** instance.  
   - Maintains a **single** TCP connection for all queries (reducing overhead).

4. **.env for Host/Port**  
   - The `.env` file stores `FULCRUM_HOST` and `FULCRUM_PORT` so you don’t need to hardcode or pass them as arguments.  
   - We use [`python-dotenv`](https://pypi.org/project/python-dotenv/) to load these into environment variables.

5. **Logging & Verbose Control**  
   - Optionally create a **timestamped** `.log` file (with `-L/--logfile`).  
   - Use `-v/--verbose` to show **all** address-level details in the console. Otherwise, the script only prints final wallet balances and summary lines to the console.  
   - The log file **always** contains the **full** verbose output.

---

### Prerequisites

1. **Dependencies**  
   - Python 3.7+  
   - `pip install mnemonic bip_utils base58 python-dotenv`

2. **Fulcrum**  
   - A **Fulcrum** (Electrum-compatible) server running and **fully synchronized** with the Bitcoin network.  
   - Typically listens on `127.0.0.1:50001` (TCP).  

3. **.env File**  
   - Must define:
     ```
     FULCRUM_HOST=127.0.0.1
     FULCRUM_PORT=50001
     ```

---

### Usage

```bash
python walletrandomizer.py <num_wallets> <num_addresses> <bip_types> [options]
```

Where:
- **`<num_wallets>`**: Number of wallets to generate (must be > 0).  
- **`<num_addresses>`**: Number of addresses to derive per wallet (must be > 0).  
- **`<bip_types>`**: A comma-separated list of `bip44`, `bip49`, `bip84`, `bip86` (one or more).

#### Optional Arguments

- **`-v, --verbose`**  
  Show **address-level** details and mnemonic in console. Otherwise only per-wallet totals and a final summary.  
- **`-L, --logfile`**  
  Creates a `.log` file in the script directory with a timestamp (contains **all** verbose output).  
- **`-w, --wordcount {12,24}`**  
  Select **12** (default) or **24** words for the BIP39 mnemonic.  
- **`-l, --language <lang>`**  
  Choose mnemonic language (`english`, `french`, `italian`, `spanish`, `korean`, `chinese_simplified`, `chinese_traditional`). Defaults to **`english`**.

---

### Examples

1. **Generate 3 wallets, 5 addresses each, using only BIP84 (English, 12 words)**:
   ```bash
   python walletrandomizer.py 3 5 bip84
   ```
2. **Generate 2 wallets, 3 addresses each, logging to file**:
   ```bash
   python walletrandomizer.py 2 3 bip44 --logfile
   ```
3. **Generate 2 wallets with multiple BIP types (e.g. BIP84 & BIP44)**:
   ```bash
   python walletrandomizer.py 2 3 bip84,bip44
   ```
   This will derive 3 addresses each for BIP84 **and** BIP44 per wallet (6 total addresses per wallet).
4. **Spanish Mnemonics, 24 words**:
   ```bash
   python walletrandomizer.py 1 2 bip49 -w 24 -l spanish
   ```
   Creates a **24-word** Spanish mnemonic, 1 wallet, 2 addresses each for BIP49.

5. **Verbose Mode**:
   ```bash
   python walletrandomizer.py 1 3 bip86 --verbose
   ```
   Console shows **detailed** info for each address, plus a final summary. A `.log` is optional.

---

### Output

1. **Verbose vs. Non-Verbose**  
   - **Verbose**: Shows the **mnemonic**, each BIP type’s extended keys (XPRV/XPUB), each **derived address**, and **address-level** balances.  
   - **Non-verbose**: Only prints each wallet’s **“TOTAL BALANCE”** plus the final **GRAND TOTAL**.  

2. **Log File**  
   - If you specify `-L/--logfile`, a timestamped `.log` is created with **all** verbose information, regardless of console verbosity.

3. **BIP Types**  
   Shows which derivation paths were used (e.g., `bip84,bip86`).

4. **Mnemonic**  
   The **BIP39** mnemonic (only **printed** in console if `-v` is enabled, but **always** in log file).

5. **Account XPRV / XPUB**  
   Shown in verbose mode.

6. **Address Balances**  
   Fetched from **Fulcrum** using `blockchain.scripthash.get_balance`. If no UTXOs, balance is `0 BTC`.

7. **Wallet & Grand Totals**  
   Prints each wallet’s final BTC balance (summed across all BIP types) and an overall **GRAND TOTAL**.

---

### Script Configuration

- **`.env` for Fulcrum**  
  - Define `FULCRUM_HOST` and `FULCRUM_PORT` in `.env`, e.g.:
    ```bash
    FULCRUM_HOST=127.0.0.1
    FULCRUM_PORT=50001
    ```
  - If your Fulcrum uses SSL, you may need to adapt the script to create an **SSL** socket instead of a plain TCP connection.

- **Word Count & Language**  
  - Defaults to **12** words in **English**.  
  - `--wordcount 24` for 24 words, `--language french` for French, etc.

---

### Troubleshooting

1. **Missing Dependencies**  
   If you see errors like:
   ```bash
   Error: The 'mnemonic' library is missing.
   ```
   install them via:
   ```bash
   pip install mnemonic bip_utils base58 python-dotenv
   ```

2. **Fulcrum Connection Errors**  
   - Ensure Fulcrum is running and **fully synced**.  
   - Check you used the correct host/port in `.env`.  

3. **0 BTC Balances**  
   If addresses have never received transactions, the script will show `0 BTC`.

4. **Logging Issues**  
   If a `.log` file can’t be created, an error is printed and the script exits.

5. **Verbose Mode**  
   If you forget `-v/--verbose`, you’ll only see wallet totals and final summary on console. However, if `-L` is also used, the log file still has full address-level details.
