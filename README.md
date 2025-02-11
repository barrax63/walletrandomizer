## Wallet Randomizer

This Python script allows you to generate multiple random BIP39 wallets, derive addresses for various BIP types, and **check their balances** using a **local Fulcrum Electrum server** in conjunction with a Bitcoin Core server. You can specify multiple BIP derivation types, set the mnemonic **word count** (12 or 24), choose **different languages**, and optionally log all output to a timestamped file.

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
   - Optionally create a **timestamped** `.log` file (with `-L/--logfile`). This log **rotates** when it reaches 250 MB, with up to 40 backups by default.  
   - Use `-v/--verbose` to show **all** address-level details in the `.log` file.

6. **JSON Exports**  
   - Wallets with a total balance **greater than 0** are automatically exported to a **JSON** file.  
   - Each file is named with a **UUID** (e.g. `24df35e9-b3ca-4cd6-9047-c9f6cd4fb5fd.json`).  
   - The JSON includes the mnemonic, language, word count, and a breakdown of all derived addresses with balances.

---

### Prerequisites

1. **Dependencies**  
   - Python 3.7+  
   - `pip install mnemonic bip_utils base58 python-dotenv tqdm`
2. **Fulcrum**  
   - A **Fulcrum** (Electrum-compatible) server running and **fully synchronized** with the Bitcoin network.  
   - Typically listens on `127.0.0.1:50001` (TCP).  
3. **Bitcoin Core**  
   - Fulcrum depends on your **Bitcoin Core** node; ensure it’s running and synced before starting Fulcrum.  
4. **.env File**  
   - Must define:
     ```
     FULCRUM_HOST=127.0.0.1
     FULCRUM_PORT=50001
     ```
   - If your Fulcrum is on another host/port, edit these values accordingly in `.env`.

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
  Show **address-level** details and the generated mnemonic in `.log` file. Otherwise, only wallet totals and final summary are printed to the `.log` file.
- **`-L, --logfile`**  
  Creates a **rotating** `.log` file in the script directory (up to 250 MB each). By default, up to 40 backups are kept. Mandatory for `-v, --verbose` option.
- **`-w, --wordcount {12,24}`**  
  Select **12** (default) or **24** words for the BIP39 mnemonic.  
- **`-l, --language <lang>`**  
  Choose mnemonic language (`english`, `french`, `italian`, `spanish`, `korean`, `chinese_simplified`, `chinese_traditional`). Defaults to **`english`**.

---

### Examples

1. **Generate 3 wallets, 5 addresses each, using BIP84 (English, 12 words):**
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
   This will derive 3 addresses each for **both** BIP84 **and** BIP44, i.e., 6 total addresses per wallet.
4. **Spanish Mnemonics, 24 words**:
   ```bash
   python walletrandomizer.py 1 2 bip49 -w 24 -l spanish
   ```
   Creates a **24-word** Spanish mnemonic, 1 wallet, 2 addresses each for BIP49.
5. **Verbose Mode**:
   ```bash
   python walletrandomizer.py 1 3 bip86 --verbose -L
   ```
   Log file shows **detailed** info for each address plus final summary. A `.log` file is needed for verbose output.

---

### Output

1. **Verbose vs. Non-Verbose**  
   - **Verbose**: Shows the **mnemonic**, each BIP type’s extended keys (XPRV/XPUB), each **derived address**, and **address-level** balances.  
   - **Non-verbose**: Only prints each wallet’s **“TOTAL BALANCE”** plus the final **GRAND TOTAL**.  

2. **Log File**  
   - If you specify `-L/--logfile`, a timestamped `.log` is created (rotating at 250 MB, up to 40 old logs).  

3. **BIP Types**  
   - BIP type derivations included in the final output (e.g., `bip84,bip86`).

4. **Mnemonic**  
   - The **BIP39** mnemonic (only **printed** in console if `-v` is enabled, but always in the log file).

5. **Account XPRV / XPUB**  
   - Shown in verbose mode.

6. **Address Balances**  
   - Fetched from **Fulcrum** using `blockchain.scripthash.get_balance`.
   - If no UTXOs, balance is `0 BTC`.

7. **Wallet & Grand Totals**  
   - Per-wallet total BTC balance (summed across all addresses and BIP types).
   - Overall **GRAND TOTAL** across **all** generated wallets.

8. **JSON Export**  
   - If a wallet has a **total balance > 0**, it’s automatically exported to a file named `<random-uuid>.json`.  
   - Each JSON file includes:
     - **Mnemonic**  
     - **Mnemonic language** and **word count**  
     - **Addresses** for each selected BIP type along with per-address balances  
     - **Extended private/public keys** for each BIP type  

---

### Script Configuration

- **`.env` for Fulcrum**  
  - Define `FULCRUM_HOST` and `FULCRUM_PORT` in `.env`, for example:
    ```bash
    FULCRUM_HOST=127.0.0.1
    FULCRUM_PORT=50001
    ```
  - Modify if your Fulcrum instance runs elsewhere.

- **Logging to File**  
  - Use `-L/--logfile` to create a rotating `.log` file. It rotates automatically once **250 MB** is reached, keeping up to **40** older logs.

- **Verbose Mode**  
  - `-v` prints detailed data to `.log` file.

- **Ctrl+C** Handling  
  - If you press **Ctrl+C**, the script tries to finish processing the current wallet gracefully and then exits with a partial summary.

---

### Troubleshooting

1. **Missing Dependencies**  
   If you see errors like:
   ```bash
   Error: The 'mnemonic' library is missing.
   ```
   then install them via:
   ```bash
   pip install mnemonic bip_utils base58 python-dotenv tqdm
   ```

2. **Fulcrum Connection Errors**  
   - Ensure Fulcrum is running and **fully synced**.  
   - Check you used the correct host/port in `.env`.  

3. **Zero Balances**  
   - If addresses have never received any transactions, the script will show `0 BTC`.

4. **Log File Rotation**  
   - By default, each log is capped at **250 MB**. Once it hits that size, a new file is started. Up to 40 old logs are kept.  

5. **Verbose Output**  
   - If you forget `-v/--verbose`, you’ll only see wallet totals and the final summary in the `.log` file.

6. **JSON Not Generated**  
   - JSON files are **only** generated for wallets whose total balance is **greater than 0**.  
   - If you expect a wallet to have a balance but you don’t see a JSON file, confirm that there are actual funds on one of the derived addresses.

