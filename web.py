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
import requests
from datetime import datetime
from collections import deque
from flask import Flask, render_template, jsonify
from asgiref.wsgi import WsgiToAsgi
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

flask_app = Flask(__name__)

# Configuration from environment variables
BALANCE_API = os.getenv("BALANCE_API", "fulcrum").lower()  # fulcrum or blockchain
FULCRUM_HOST = os.getenv("FULCRUM_HOST", "127.0.0.1")
FULCRUM_PORT = int(os.getenv("FULCRUM_PORT", "50001"))
BLOCKCHAIN_API_URL = os.getenv("BLOCKCHAIN_API_URL", "https://blockchain.info")
BLOCKCHAIN_API_KEY = os.getenv("BLOCKCHAIN_API_KEY")  # Optional API key for higher rate limits
BLOCKCHAIN_RATE_LIMIT = float(os.getenv("BLOCKCHAIN_RATE_LIMIT", "10.0"))  # Delay in seconds between API calls (default 10s for unauthenticated)
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


###############################################################################
# BALANCE CHECKER ABSTRACTION
###############################################################################

class BlockchainComClient:
    """
    Client for Blockchain.com API to check Bitcoin address balances.
    
    Supports both authenticated (with API key) and unauthenticated modes.
    Authenticated mode provides higher rate limits.
    """
    
    def __init__(self, api_url: str = "https://blockchain.info", timeout: int = 10, api_key: str = None, request_delay: float = 1.0):
        """
        Initialize Blockchain.com API client.
        
        Args:
            api_url (str): Base URL for Blockchain.com API
            timeout (int): Request timeout in seconds
            api_key (str, optional): API key for authenticated requests with higher rate limits
            request_delay (float): Delay in seconds between API requests for rate limiting
        """
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.api_key = api_key
        self.request_delay = request_delay
        self._last_request_time = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'WalletRandomizer/1.0'
        })
    
    def _rate_limit(self):
        """Apply rate limiting between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def get_balance(self, address: str) -> dict | None:
        """
        Query balance for a specific Bitcoin address using Blockchain.com API.
        
        Args:
            address (str): Bitcoin address
            
        Returns:
            dict | None: {"final_balance": int} with balance in satoshis, or None on error
        """
        # Apply rate limiting before making request
        self._rate_limit()
        
        try:
            if self.api_key:
                # Use authenticated endpoint with API key for higher rate limits
                url = f"{self.api_url}/balance"
                params = {
                    "active": address,
                    "api_code": self.api_key
                }
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    # Response is JSON with address as key
                    data = response.json()
                    if address in data and "final_balance" in data[address]:
                        return {"final_balance": data[address]["final_balance"]}
                    else:
                        logger.warning(f"Address {address} or final_balance field not found in API response")
                        return None
                elif response.status_code == 429:
                    logger.warning(f"Blockchain.com API rate limit exceeded for {address}")
                    return None
                else:
                    logger.warning(f"Blockchain.com API error for {address}: HTTP {response.status_code}")
                    return None
            else:
                # Use unauthenticated endpoint (strict rate limits)
                url = f"{self.api_url}/q/addressbalance/{address}"
                response = self.session.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    # Response is just the balance in satoshis as plain text
                    balance_sat = int(response.text.strip())
                    return {"final_balance": balance_sat}
                elif response.status_code == 500 and "No free outputs" in response.text:
                    # Address exists but has no balance (0 satoshis)
                    return {"final_balance": 0}
                elif response.status_code == 429:
                    logger.warning(f"Blockchain.com API rate limit exceeded for {address}. Consider using an API key.")
                    return None
                else:
                    logger.warning(f"Blockchain.com API error for {address}: HTTP {response.status_code}")
                    return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"Blockchain.com API timeout for {address}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Blockchain.com API request error for {address}: {e}")
            return None
        except (ValueError, AttributeError) as e:
            logger.warning(f"Blockchain.com API response parsing error for {address}: {e}")
            return None


def create_balance_checker():
    """
    Factory function to create the appropriate balance checker based on configuration.
    
    Returns:
        Balance checker client (FulcrumClient or BlockchainComClient)
    """
    if BALANCE_API == "blockchain":
        if BLOCKCHAIN_API_KEY:
            logger.info(f"Using Blockchain.com API with authentication for balance checks: {BLOCKCHAIN_API_URL}")
            logger.info(f"Rate limit: {BLOCKCHAIN_RATE_LIMIT}s between requests")
        else:
            logger.info(f"Using Blockchain.com API (unauthenticated) for balance checks: {BLOCKCHAIN_API_URL}")
            logger.info(f"Rate limit: {BLOCKCHAIN_RATE_LIMIT}s between requests")
            logger.warning("No BLOCKCHAIN_API_KEY set. Using unauthenticated API with strict rate limits. Consider setting BLOCKCHAIN_API_KEY for higher limits.")
        return BlockchainComClient(api_url=BLOCKCHAIN_API_URL, api_key=BLOCKCHAIN_API_KEY, request_delay=BLOCKCHAIN_RATE_LIMIT)
    else:
        logger.info(f"Using Fulcrum server for balance checks: {FULCRUM_HOST}:{FULCRUM_PORT}")
        return FulcrumClient(FULCRUM_HOST, FULCRUM_PORT, timeout=5)


###############################################################################
# MONITORING STATE
###############################################################################

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
        "balance_api": BALANCE_API,
        "fulcrum_host": FULCRUM_HOST if BALANCE_API == "fulcrum" else None,
        "fulcrum_port": FULCRUM_PORT if BALANCE_API == "fulcrum" else None,
        "blockchain_api_url": BLOCKCHAIN_API_URL if BALANCE_API == "blockchain" else None,
        "blockchain_api_authenticated": bool(BLOCKCHAIN_API_KEY) if BALANCE_API == "blockchain" else None,
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
        
        # Create balance checker client (Fulcrum or Blockchain.com)
        balance_client = create_balance_checker()
        
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
                            balance_data = balance_client.get_balance(addr)
                            
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
            balance_client.close()
            
    except Exception as e:
        logger.exception("Error in wallet generation worker")
        update_state(
            status="error",
            error=str(e)
        )


@flask_app.route("/")
def index():
    """Main monitoring page."""
    return render_template("monitor.html")


@flask_app.route("/api/status", methods=["GET"])
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


@flask_app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        # Test balance API connection
        client = create_balance_checker()
        # Try a simple test (checking a known address with zero balance for quick response)
        # Using a burn address that's known to exist
        test_result = client.get_balance("1111111111111111111114oLvT2")  # Known burn address
        client.close()
        
        if test_result is not None:
            api_status = "connected"
        else:
            api_status = "error: unable to query balance"
    except Exception as e:
        api_status = f"error: {str(e)}"
    
    response_data = {
        "status": "healthy",
        "balance_api": BALANCE_API,
        "api_status": api_status,
    }
    
    # Add API-specific info
    if BALANCE_API == "fulcrum":
        response_data["fulcrum_host"] = FULCRUM_HOST
        response_data["fulcrum_port"] = FULCRUM_PORT
    elif BALANCE_API == "blockchain":
        response_data["blockchain_api_url"] = BLOCKCHAIN_API_URL
    
    return jsonify(response_data)


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


# Create ASGI-compatible app for uvicorn
# This properly wraps Flask's WSGI interface for ASGI servers
app = WsgiToAsgi(flask_app)


if __name__ == "__main__":
    # Check dependencies at startup
    _check_dependencies()
    
    # Start background worker
    start_generation_worker()
    
    # Run the Flask app directly (not through uvicorn)
    port = int(os.getenv("WEB_PORT", "5000"))
    host = os.getenv("WEB_HOST", "0.0.0.0")
    
    logger.info(f"Starting Wallet Randomizer Monitoring Interface on {host}:{port}")
    if BALANCE_API == "blockchain":
        if BLOCKCHAIN_API_KEY:
            logger.info(f"Balance API: Blockchain.com (authenticated) ({BLOCKCHAIN_API_URL})")
        else:
            logger.info(f"Balance API: Blockchain.com (unauthenticated) ({BLOCKCHAIN_API_URL})")
    else:
        logger.info(f"Balance API: Fulcrum ({FULCRUM_HOST}:{FULCRUM_PORT})")
    logger.info(f"Configuration: {NUM_WALLETS if NUM_WALLETS != -1 else 'Infinite'} wallets, {NUM_ADDRESSES} addresses, {NETWORK}")
    
    flask_app.run(host=host, port=port, debug=False)
else:
    # When running with uvicorn, start the worker once when the module is loaded
    # Use singleton pattern to prevent multiple workers
    start_generation_worker()
