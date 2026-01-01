#!/bin/bash
set -e

# Determine mode: "web" for web interface, "cli" for command-line
MODE="${MODE:-cli}"

if [ "$MODE" = "web" ]; then
    echo "Starting Wallet Randomizer Web Interface..."
    
    # Parse FULCRUM_SERVER if provided
    if [ -n "$FULCRUM_SERVER" ]; then
        IFS=':' read -r FULCRUM_HOST FULCRUM_PORT <<< "$FULCRUM_SERVER"
        export FULCRUM_HOST="${FULCRUM_HOST:-127.0.0.1}"
        export FULCRUM_PORT="${FULCRUM_PORT:-50001}"
    else
        export FULCRUM_HOST="${FULCRUM_HOST:-127.0.0.1}"
        export FULCRUM_PORT="${FULCRUM_PORT:-50001}"
    fi
    
    # Set web server configuration
    export WEB_HOST="${WEB_HOST:-0.0.0.0}"
    export WEB_PORT="${WEB_PORT:-5000}"
    
    # Start the web server using gunicorn for production
    exec gunicorn --bind "${WEB_HOST}:${WEB_PORT}" \
        --workers "${WEB_WORKERS:-4}" \
        --timeout "${WEB_TIMEOUT:-120}" \
        --access-logfile - \
        --error-logfile - \
        web:app
else
    # CLI mode - original behavior
    
    # Enforce that FULCRUM_SERVER is required
    if [ -z "$FULCRUM_SERVER" ]; then
        echo "ERROR: FULCRUM_SERVER environment variable is required"
        echo "Example: FULCRUM_SERVER=127.0.0.1:50001"
        exit 1
    fi

    # Parse FULCRUM_SERVER into host and port
    IFS=':' read -r FULCRUM_HOST FULCRUM_PORT <<< "$FULCRUM_SERVER"
    if [ -z "$FULCRUM_PORT" ]; then
        FULCRUM_PORT="50001"  # Default port
    fi

    # Build CLI arguments from environment variables
    CLI_ARGS=()

    # Provide all positionals in order, even if they'll be overridden by flags
    # This is required because argparse needs all positional arguments to parse correctly
    # when mixing positionals with optional flags
    # num_wallets (will be overridden by --num-wallets flag if provided)
    NUM_WALLETS_POS="${NUM_WALLETS:-10}"
    CLI_ARGS+=("$NUM_WALLETS_POS")

    # num_addresses (required positional)
    NUM_ADDRESSES="${NUM_ADDRESSES:-5}"
    CLI_ARGS+=("$NUM_ADDRESSES")

    # bip_types (will be overridden by --network flag if provided)
    NETWORK_POS="${NETWORK:-bip84}"
    CLI_ARGS+=("$NETWORK_POS")

    # Now add flags that will override the positionals
    # Add --num-wallets flag if NUM_WALLETS is set (can be -1 for infinite)
    if [ -n "$NUM_WALLETS" ]; then
        CLI_ARGS+=("--num-wallets" "$NUM_WALLETS")
    fi

    # Add --network flag if NETWORK is set (maps to bip_types)
    if [ -n "$NETWORK" ]; then
        CLI_ARGS+=("--network" "$NETWORK")
    fi

    # Add --output flag if OUTPUT_PATH is set
    if [ -n "$OUTPUT_PATH" ]; then
        CLI_ARGS+=("--output" "$OUTPUT_PATH")
    fi

    # Add --format flag if FORMAT is set
    if [ -n "$FORMAT" ]; then
        CLI_ARGS+=("--format" "$FORMAT")
    fi

    # Add --server and --port (split from FULCRUM_SERVER)
    CLI_ARGS+=("--server" "$FULCRUM_HOST")
    CLI_ARGS+=("--port" "$FULCRUM_PORT")

    # Append any additional arguments passed to the container
    CLI_ARGS+=("$@")

    # Execute the Python script with the constructed arguments
    exec python /app/walletrandomizer.py "${CLI_ARGS[@]}"
fi
