#!/bin/bash
set -e

echo "Starting Wallet Randomizer Web Monitoring Interface..."

# Parse FULCRUM_SERVER if provided, otherwise use separate FULCRUM_HOST and FULCRUM_PORT
if [ -n "$FULCRUM_SERVER" ]; then
    IFS=':' read -r FULCRUM_HOST FULCRUM_PORT <<< "$FULCRUM_SERVER"
    export FULCRUM_HOST="${FULCRUM_HOST:-127.0.0.1}"
    export FULCRUM_PORT="${FULCRUM_PORT:-50001}"
else
    # Use individual settings if FULCRUM_SERVER not provided
    export FULCRUM_HOST="${FULCRUM_HOST:-127.0.0.1}"
    export FULCRUM_PORT="${FULCRUM_PORT:-50001}"
fi

# Set web server configuration
export WEB_HOST="${WEB_HOST:-0.0.0.0}"
export WEB_PORT="${WEB_PORT:-5000}"

# Graceful shutdown handler
shutdown_handler() {
    echo "Received shutdown signal, stopping gracefully..."
    exit 0
}

# Trap SIGTERM and SIGINT for graceful shutdown
trap shutdown_handler SIGTERM SIGINT

# Start the web server using uvicorn for production
# Note: Using single worker (default) because generation state is in-memory per-process.
# Multiple workers would each have their own state and background thread, causing
# inconsistent data between requests. If you need horizontal scaling, use an external
# state store like Redis.
exec uvicorn web:app \
    --host "${WEB_HOST}" \
    --port "${WEB_PORT}" \
    --workers "${WEB_WORKERS:-1}" \
    --timeout-keep-alive "${WEB_TIMEOUT:-120}" \
    --log-level info
