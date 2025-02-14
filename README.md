**Wallet Randomizer**  
A Python script that generates random BIP39 wallets (12- or 24-word mnemonics), derives addresses for various BIP standards (bip44, bip49, bip84, bip86), and checks final balances using a local Fulcrum Electrum server. Balances are fetched via scripthash-based queries.

---

## Requirements

- **Python** 3.10 or 3.11
- The following Python packages:
  - `mnemonic`
  - `bip_utils`
  - `base58`
  - `python-dotenv`
  - `tqdm`
  
Install them with:

```bash
pip install mnemonic bip_utils base58 python-dotenv tqdm
```

## Usage

1. **Fulcrum Server**  
   Configure your Fulcrum server hostname and port in a `.env` file:
   ```
   FULCRUM_HOST=127.0.0.1
   FULCRUM_PORT=50001
   ```
   By default, the script uses `127.0.0.1` and port `50001`.

2. **Run the Script**  
   ```bash
   python3 walletrandomizer.py <num_wallets> <num_addresses> <bip_types> [options]
   ```
   - **`<num_wallets>`**: How many wallets to generate.
   - **`<num_addresses>`**: Number of addresses to derive per wallet.
   - **`<bip_types>`**: Comma-separated list of BIP derivation types (e.g. `bip44,bip49,bip84,bip86`).

   **Options**:
   - `-w, --wordcount {12,24}`: Mnemonic word count (default: 12).
   - `-l, --language {english,french,italian,spanish,korean,chinese_simplified,chinese_traditional}`  
     Sets the BIP39 mnemonic language (default: `english`).
   - `-v, --verbose`: Print debug-level logs (requires `-L`).
   - `-L, --logfile`: Write logs to a timestamped file.

   Example:
   ```bash
   python3 walletrandomizer.py 10 5 bip44,bip84 -w 24 -l english -L
   ```

3. **Output**  
   - The script displays a summary of the total wallet balances found.
   - Any wallet with a balance greater than 0 BTC is exported to a JSON file named with a random UUID.
