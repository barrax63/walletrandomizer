#!/usr/bin/env python3
"""
web.py

Web interface for the Wallet Randomizer application.
Provides a simple HTTP server with a user-friendly interface for generating and checking wallets.
"""

import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from walletrandomizer import (
    generate_random_mnemonic,
    derive_addresses,
    FulcrumClient,
    _check_dependencies,
    export_wallet_json,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("walletrandomizer-web")

app = Flask(__name__)

# Configuration from environment variables
FULCRUM_HOST = os.getenv("FULCRUM_HOST", "127.0.0.1")
FULCRUM_PORT = int(os.getenv("FULCRUM_PORT", "50001"))
DEFAULT_NUM_WALLETS = int(os.getenv("NUM_WALLETS", "1"))
DEFAULT_NUM_ADDRESSES = int(os.getenv("NUM_ADDRESSES", "5"))
DEFAULT_NETWORK = os.getenv("NETWORK", "bip84")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "/data")


@app.route("/")
def index():
    """Landing page with app overview."""
    return render_template("index.html")


@app.route("/generator")
def generator():
    """Main wallet generator page."""
    return render_template(
        "generator.html",
        default_num_wallets=DEFAULT_NUM_WALLETS,
        default_num_addresses=DEFAULT_NUM_ADDRESSES,
        default_network=DEFAULT_NETWORK,
        fulcrum_host=FULCRUM_HOST,
        fulcrum_port=FULCRUM_PORT,
    )


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        # Test Fulcrum connection
        client = FulcrumClient(FULCRUM_HOST, FULCRUM_PORT, timeout=5)
        client.close()
        fulcrum_status = "connected"
    except Exception as e:
        fulcrum_status = f"error: {str(e)}"
    
    return jsonify({
        "status": "healthy",
        "fulcrum": fulcrum_status,
        "fulcrum_host": FULCRUM_HOST,
        "fulcrum_port": FULCRUM_PORT,
    })


@app.route("/api/generate", methods=["POST"])
def generate_wallets():
    """
    Generate wallets and check balances.
    
    Expected JSON payload:
    {
        "num_wallets": 1,
        "num_addresses": 5,
        "bip_types": ["bip84"],
        "word_count": 12,
        "language": "english"
    }
    """
    try:
        data = request.get_json()
        
        # Validate inputs
        num_wallets = int(data.get("num_wallets", 1))
        num_addresses = int(data.get("num_addresses", 5))
        bip_types = data.get("bip_types", ["bip84"])
        word_count = int(data.get("word_count", 12))
        language = data.get("language", "english")
        
        if num_wallets < 1 or num_wallets > 10:
            return jsonify({"error": "num_wallets must be between 1 and 10"}), 400
        
        if num_addresses < 1 or num_addresses > 20:
            return jsonify({"error": "num_addresses must be between 1 and 20"}), 400
        
        if word_count not in [12, 24]:
            return jsonify({"error": "word_count must be 12 or 24"}), 400
        
        allowed_bips = {"bip44", "bip49", "bip84", "bip86"}
        for bip in bip_types:
            if bip.lower() not in allowed_bips:
                return jsonify({"error": f"Invalid BIP type: {bip}"}), 400
        
        # Generate wallets
        results = []
        
        # Create Fulcrum client
        fulcrum_client = FulcrumClient(FULCRUM_HOST, FULCRUM_PORT, timeout=5)
        
        try:
            for w_i in range(num_wallets):
                # Generate mnemonic
                mnemonic = generate_random_mnemonic(word_count, language)
                
                wallet_obj = {
                    "wallet_number": w_i + 1,
                    "mnemonic": mnemonic,
                    "language": language,
                    "word_count": word_count,
                    "bip_types": []
                }
                
                wallet_balance_sat = 0
                
                # Derive addresses for each BIP type
                for bip_type in bip_types:
                    derivation_info = derive_addresses(
                        bip_type, mnemonic, num_addresses, language
                    )
                    
                    bip_entry = {
                        "type": bip_type,
                        "extended_public_key": derivation_info["account_xpub"],
                        "addresses": []
                    }
                    
                    # Check balances for each address
                    for addr in derivation_info["addresses"]:
                        balance_data = fulcrum_client.get_balance(addr)
                        
                        if balance_data is not None:
                            final_balance_sat = balance_data["final_balance"]
                            wallet_balance_sat += final_balance_sat
                            final_balance_btc = final_balance_sat / 1e8
                        else:
                            final_balance_btc = 0.0
                        
                        bip_entry["addresses"].append({
                            "address": addr,
                            "balance": str(final_balance_btc)
                        })
                    
                    wallet_obj["bip_types"].append(bip_entry)
                
                # Add total balance
                wallet_obj["total_balance"] = str(wallet_balance_sat / 1e8)
                
                # Export if balance > 0
                if wallet_balance_sat > 0:
                    wallet_export = {
                        "bip_types": wallet_obj["bip_types"]
                    }
                    export_wallet_json(
                        w_i + 1,
                        wallet_export,
                        mnemonic,
                        language,
                        word_count,
                        OUTPUT_PATH
                    )
                
                results.append(wallet_obj)
        
        finally:
            fulcrum_client.close()
        
        return jsonify({
            "success": True,
            "wallets": results
        })
    
    except Exception as e:
        logger.exception("Error generating wallets")
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    # Check dependencies at startup
    _check_dependencies()
    
    # Run the Flask app
    port = int(os.getenv("WEB_PORT", "5000"))
    host = os.getenv("WEB_HOST", "0.0.0.0")
    
    logger.info(f"Starting Wallet Randomizer Web Interface on {host}:{port}")
    logger.info(f"Fulcrum server: {FULCRUM_HOST}:{FULCRUM_PORT}")
    
    app.run(host=host, port=port, debug=False)
