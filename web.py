#!/usr/bin/env python3
"""
web.py

Web monitoring interface for the Wallet Randomizer application.
Automatically starts wallet generation process in background and provides
real-time monitoring through a web interface.
"""

import os
import json
import logging
import threading
import time
from datetime import datetime
from collections import deque
from flask import Flask, render_template, jsonify
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
NUM_WALLETS = int(os.getenv("NUM_WALLETS", "-1"))  # -1 for infinite
NUM_ADDRESSES = int(os.getenv("NUM_ADDRESSES", "5"))
NETWORK = os.getenv("NETWORK", "bip84")
WORD_COUNT = int(os.getenv("WORD_COUNT", "12"))
LANGUAGE = os.getenv("LANGUAGE", "english")
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "/data")

# Monitoring constants
MAX_RECENT_WALLETS = 10  # Number of recent wallets to keep in memory
MNEMONIC_DISPLAY_LENGTH = 50  # Max characters to show for mnemonic in UI
GENERATION_DELAY = 0.1  # Delay between wallet generations in seconds

# Global state for monitoring
generation_state = {
    "status": "initializing",  # initializing, running, paused, stopped, error
    "wallets_processed": 0,
    "wallets_with_balance": 0,
    "total_balance_btc": 0.0,
    "current_wallet": None,
    "start_time": None,
    "last_update": None,
    "error": None,
    "recent_wallets": deque(maxlen=MAX_RECENT_WALLETS),  # Keep last N wallets
    "config": {
        "num_wallets": NUM_WALLETS,
        "num_addresses": NUM_ADDRESSES,
        "network": NETWORK,
        "word_count": WORD_COUNT,
        "language": LANGUAGE,
        "fulcrum_host": FULCRUM_HOST,
        "fulcrum_port": FULCRUM_PORT,
    }
}
state_lock = threading.Lock()


def update_state(**kwargs):
    """Thread-safe state update."""
    with state_lock:
        for key, value in kwargs.items():
            if key == "recent_wallets":
                generation_state["recent_wallets"].append(value)
            else:
                generation_state[key] = value
        generation_state["last_update"] = datetime.now().isoformat()


def wallet_generation_worker():
    """Background worker that continuously generates wallets."""
    logger.info("Starting wallet generation worker...")
    
    try:
        # Parse BIP types
        bip_types = [x.strip().lower() for x in NETWORK.split(",") if x.strip()]
        if not bip_types:
            bip_types = ["bip84"]
        
        update_state(
            status="running",
            start_time=datetime.now().isoformat()
        )
        
        # Create Fulcrum client
        fulcrum_client = FulcrumClient(FULCRUM_HOST, FULCRUM_PORT, timeout=5)
        
        wallet_count = 0
        infinite_mode = (NUM_WALLETS == -1)
        
        try:
            while True:
                # Check if we should stop (for non-infinite mode)
                if not infinite_mode and wallet_count >= NUM_WALLETS:
                    update_state(status="completed")
                    break
                
                wallet_count += 1
                
                # Generate mnemonic
                mnemonic = generate_random_mnemonic(WORD_COUNT, LANGUAGE)
                
                wallet_info = {
                    "wallet_number": wallet_count,
                    "mnemonic": mnemonic[:MNEMONIC_DISPLAY_LENGTH] + "..." if len(mnemonic) > MNEMONIC_DISPLAY_LENGTH else mnemonic,  # Truncate for display
                    "timestamp": datetime.now().isoformat(),
                    "bip_types": [],
                    "total_balance": 0.0
                }
                
                update_state(current_wallet=wallet_count)
                
                wallet_balance_sat = 0
                wallet_export = {"bip_types": []}
                
                # Derive addresses for each BIP type
                for bip_type in bip_types:
                    try:
                        derivation_info = derive_addresses(
                            bip_type, mnemonic, NUM_ADDRESSES, LANGUAGE
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
                                final_balance_sat = 0
                                final_balance_btc = 0.0
                            
                            bip_entry["addresses"].append({
                                "address": addr,
                                "balance": str(final_balance_btc)
                            })
                        
                        wallet_export["bip_types"].append(bip_entry)
                        wallet_info["bip_types"].append({
                            "type": bip_type,
                            "addresses_checked": len(derivation_info["addresses"])
                        })
                        
                    except Exception as e:
                        logger.error(f"Error processing BIP type {bip_type}: {e}")
                
                # Update global stats
                wallet_balance_btc = wallet_balance_sat / 1e8
                wallet_info["total_balance"] = wallet_balance_btc
                
                with state_lock:
                    generation_state["wallets_processed"] = wallet_count
                    if wallet_balance_btc > 0:
                        generation_state["wallets_with_balance"] += 1
                        generation_state["total_balance_btc"] += wallet_balance_btc
                    generation_state["recent_wallets"].append(wallet_info)
                    generation_state["last_update"] = datetime.now().isoformat()
                
                # Export if balance > 0
                if wallet_balance_sat > 0:
                    try:
                        export_wallet_json(
                            wallet_count,
                            wallet_export,
                            mnemonic,
                            LANGUAGE,
                            WORD_COUNT,
                            OUTPUT_PATH
                        )
                        logger.info(f"Wallet #{wallet_count} exported with balance: {wallet_balance_btc} BTC")
                    except Exception as e:
                        logger.error(f"Error exporting wallet: {e}")
                
                # Small delay to prevent overwhelming the system
                time.sleep(GENERATION_DELAY)
                
        finally:
            fulcrum_client.close()
            
    except Exception as e:
        logger.exception("Error in wallet generation worker")
        update_state(
            status="error",
            error=str(e)
        )


@app.route("/")
def index():
    """Main monitoring page."""
    return render_template("monitor.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get current generation status."""
    with state_lock:
        return jsonify({
            "status": generation_state["status"],
            "wallets_processed": generation_state["wallets_processed"],
            "wallets_with_balance": generation_state["wallets_with_balance"],
            "total_balance_btc": generation_state["total_balance_btc"],
            "current_wallet": generation_state["current_wallet"],
            "start_time": generation_state["start_time"],
            "last_update": generation_state["last_update"],
            "error": generation_state["error"],
            "recent_wallets": list(generation_state["recent_wallets"]),
            "config": generation_state["config"],
        })


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


# Worker thread management
_worker_started = False
_worker_lock = threading.Lock()


def start_generation_worker():
    """Start the background wallet generation thread (singleton)."""
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            worker_thread = threading.Thread(target=wallet_generation_worker, daemon=True)
            worker_thread.start()
            _worker_started = True
            logger.info("Background wallet generation worker started")


if __name__ == "__main__":
    # Check dependencies at startup
    _check_dependencies()
    
    # Start background worker
    start_generation_worker()
    
    # Run the Flask app
    port = int(os.getenv("WEB_PORT", "5000"))
    host = os.getenv("WEB_HOST", "0.0.0.0")
    
    logger.info(f"Starting Wallet Randomizer Monitoring Interface on {host}:{port}")
    logger.info(f"Fulcrum server: {FULCRUM_HOST}:{FULCRUM_PORT}")
    logger.info(f"Configuration: {NUM_WALLETS if NUM_WALLETS != -1 else 'Infinite'} wallets, {NUM_ADDRESSES} addresses, {NETWORK}")
    
    app.run(host=host, port=port, debug=False)
else:
    # When running with uvicorn, start the worker once when the module is loaded
    # Use singleton pattern to prevent multiple workers
    start_generation_worker()
