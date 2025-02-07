## Wallet Randomizer

This Python script allows you to generate multiple random BIP39 wallets and check their addresses' balances using a local Bitcoin Core instance. It supports multiple BIP types (comma-separated), custom mnemonic word count (12 or 24), various languages, and stores RPC credentials in a `.env` file.

---

### Features

1. **Random Mnemonic Generation**  
   - Generates a random BIP39 mnemonic in **12 words** (default) or **24 words** using `--wordcount`.
   - Supports **various languages** (English, Spanish, French, Italian, Korean, Chinese Simplified, Chinese Traditional) via `--language`.

2. **Multiple BIP Types**  
   - Provide one or more derivation types in a comma-separated list, e.g. `bip84,bip49,bip44`, to derive addresses for each type from the same mnemonic.

3. **Local Bitcoin Core Balances**  
   - Uses `scantxoutset` to fetch final balances from a local Bitcoin Core node (`bitcoind`).  
   - Works with **`disablewallet=1`** in `bitcoin.conf` since it does **not** use wallet RPC calls.

4. **.env for Credentials**  
   - Credentials (`RPC_USER`, `RPC_PASSWORD`, `RPC_URL`) are loaded from a `.env` file, keeping secrets out of the script.  
   - Uses `python-dotenv` to load these into environment variables.

5. **Logging (Optional)**  
   - Optionally create a `.log` file in the script directory by using the `-L/--logfile` flag. The file is timestamped (e.g., `2025-02-07_14-30-59.log`) and contains all console output.

---

### Prerequisites

1. **Dependencies**  
   - Python 3.7+  
   - `pip install mnemonic bip_utils requests python-dotenv`

2. **Bitcoin Core**  
   - A locally running Bitcoin Core node with `txindex=1` enabled in your `bitcoin.conf`.  
   - **No wallet** is required (`disablewallet=1` is okay).  
   - Your `.env` file must contain:
     ```
     RPC_USER=<your_rpc_user>
     RPC_PASSWORD=<your_rpc_password>
     RPC_URL=http://127.0.0.1:8332
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

- **`-L, --logfile`**  
  If used, creates a `.log` file in the script directory with a timestamp.  
- **`-w, --wordcount {12,24}`**  
  Choose **12** (default) or **24** words for your mnemonic.  
- **`-l, --language <lang>`**  
  Select the mnemonic language (`english`, `french`, `italian`, `spanish`, `korean`, `chinese_simplified`, `chinese_traditional`). Defaults to **`english`**.

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
3. **Generate 2 wallets with multiple BIP types**:
   ```bash
   python walletrandomizer.py 2 3 bip84,bip44
   ```
   - Derives 3 addresses each for BIP84 **and** BIP44 (6 total per wallet).
4. **Spanish Mnemonics, 24 words**:
   ```bash
   python walletrandomizer.py 1 2 bip49 -w 24 -l spanish
   ```
   - 1 wallet, 2 addresses, BIP49, **24-word** Spanish mnemonic.

---

### Output

1. **Wallet Count** and **Addresses per Wallet**  
   Printed to the console (and to the log file if `--logfile` is used).

2. **BIP Types**  
   Shows which derivation paths were used (e.g., `bip84,bip44`).

3. **Mnemonic**  
   The BIP39 mnemonic words for each generated wallet.

4. **Account XPRV / XPUB**  
   Master extended private/public keys at the account level, for each BIP type.

5. **Derived Addresses**  
   A list of addresses for each BIP type.

6. **Balance Checks**  
   Uses **`scantxoutset`** to get each address’s final balance from your local node.  
   - **No** wallet RPC calls used → works with `disablewallet=1`.

7. **Per-Wallet Summary**  
   Displays the combined BTC balance **across all BIP types** for each wallet.

8. **Grand Total**  
   The total BTC balance across **all** addresses in **all** wallets.

---

### Script Configuration

- **`.env` Credentials**  
  - Put your user/pass/URL in `.env`:
    ```bash
    RPC_USER=user
    RPC_PASSWORD=passwd
    RPC_URL=http://127.0.0.1:8332
    ```
  - The script loads them automatically with `load_dotenv()`.

- **Word Count & Language**  
  - Defaults to 12 words and English.  
  - Use `--wordcount 24` for 24 words.  
  - Use `--language spanish` (etc.) for other languages.

---

### Troubleshooting

1. **Missing Dependencies**  
   If you see something like:
   ```bash
   Error: The 'mnemonic' library is missing.
   ```
   Install via:
   ```bash
   pip install mnemonic bip_utils requests python-dotenv
   ```

2. **Connection Refused**  
   Make sure Bitcoin Core is running with:
   ```ini
   server=1
   rpcuser=user
   rpcpassword=passwd
   txindex=1
   ```
   and that `RPC_URL` matches (`http://127.0.0.1:8332`).

3. **0 BTC Balances**  
   Likely means those addresses never received any transactions.

4. **Logging Issues**  
   If the script can’t write the `.log` file, it prints an error. Check directory permissions.

5. **SSL Errors**  
   If you previously set `rpcssl=1`, remove it or set up a proxy. Official Bitcoin Core doesn’t support built-in SSL. Use plain HTTP (`127.0.0.1:8332`) or an external stunnel/Nginx.