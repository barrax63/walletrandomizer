## Wallet Randomizer

This Python script allows you to generate multiple random BIP39 wallets and check their addresses' balances using a local Bitcoin Core instance. It supports multiple BIP types in a comma-separated list (e.g., `bip84,bip44`).

---

### Features

1. **Random Mnemonic Generation**  
   Generates a random 12-word (or optional 24-word) BIP39 mnemonic for each wallet.

2. **Multiple BIP Types**  
   You can provide one or more derivation types in a comma-separated list (e.g. `bip84,bip49`), and the script will derive addresses for **each** specified BIP type from the same mnemonic.

3. **Local Bitcoin Core Balances**  
   Fetches each derived address's balance from a locally running Bitcoin Core node (`bitcoind`) via JSON-RPC (`getreceivedbyaddress` and `scantxoutset`).

4. **Logging (Optional)**  
   Optionally create a `.log` file in the script directory by using the `-l/--logfile` flag. The log file will be named with a timestamp, e.g., `2025-02-07_14-30-59.log`, and will contain all console output.

---

### Prerequisites

1. **Dependencies**  
   - Python 3.7+  
   - `pip install mnemonic bip_utils requests`

2. **Bitcoin Core**  
   - A locally running Bitcoin Core node with `txindex=1` enabled in your `bitcoin.conf`.  
   - RPC credentials configured in your `bitcoin.conf`.  
   - The script defaults to `RPC_URL = "http://127.0.0.1:8332"`.  
   - Ensure your `RPC_USER` and `RPC_PASSWORD` in the script match your local Bitcoin Core settings.

---

### Usage

```bash
python walletrandomizer.py <num_wallets> <num_addresses> <bip_types> [options]
```

- **`<num_wallets>`**: Integer number of wallets to generate (must be > 0).  
- **`<num_addresses>`**: Integer number of addresses to derive per wallet (must be > 0).  
- **`<bip_types>`**: A comma-separated list of one or more of `bip44`, `bip49`, `bip84`, or `bip86`.  
  - Example: `bip84,bip44`  

#### Optional Arguments

- **`-l, --logfile`**: If provided, creates a `.log` file in the same directory as the script using a timestamped filename.

#### Examples

1. **Generate 3 wallets, 5 addresses each, using only BIP84**:
   ```bash
   python walletrandomizer.py 3 5 bip84
   ```
2. **Generate 2 wallets, 3 addresses each, with logging to file**:
   ```bash
   python walletrandomizer.py 2 3 bip44 --logfile
   ```
3. **Generate 2 wallets with multiple BIP types**:
   ```bash
   python walletrandomizer.py 2 3 bip84,bip44
   ```
   This will derive 3 addresses for BIP84 **and** 3 addresses for BIP44 for each wallet (6 total per wallet).

---

### Output

1. **Wallet Count** and **Addresses per Wallet**:  
   Printed to the console (and to the log file if `-l` is used).

2. **BIP Types**:  
   Shows which derivation paths were used (e.g., `bip84,bip44`).

3. **Mnemonic**:  
   The 12-word seed for each generated wallet.

4. **Account XPRV / XPUB**:  
   Master extended private/public keys at the account level, shown for each BIP type.

5. **Derived Addresses**:  
   A list of derived addresses for each BIP type.

6. **Balance Checks**:  
   Final balances fetched from your local node’s UTXO set (via `scantxoutset`).

7. **Per-Wallet Summary**:  
   Shows the combined BTC balance **across all BIP types** for that wallet.

8. **Grand Total**:  
   Aggregate BTC balance for **all** addresses across **all** generated wallets and **all** BIP types.

---

### Script Configuration

- **RPC Credentials**:  
  Edit the top of the script:
  ```python
  RPC_USER = "myrpcuser"
  RPC_PASSWORD = "myrpcpassword"
  RPC_URL = "http://127.0.0.1:8332"
  ```
  to match your `bitcoin.conf` settings.

- **Mnemonic Word Count**:  
  The script currently generates 12-word BIP39 mnemonics. You can adjust this by changing `generate_random_mnemonic(word_count=12)` if you wish to use 24 words.

---

### Troubleshooting

- **Missing Dependencies**:  
  If you see errors like `Error: The 'mnemonic' library is missing.`, install via:
  ```bash
  pip install mnemonic bip_utils requests
  ```

- **Connection Refused**:  
  Make sure Bitcoin Core is running with RPC enabled, and your `RPC_PORT` is correct (`8332` by default).

- **Insufficient or No UTXOs**:  
  If the local node returns `0 BTC` for addresses, it usually means those addresses have never received any transaction.

- **Logging Issues**:  
  If the script cannot create the log file, it prints an error and exits.