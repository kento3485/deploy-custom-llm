#!/bin/bash
set -e

echo "Starting Elasticsearch..."
/usr/local/bin/docker-entrypoint.sh eswrapper &
ES_PID=$!

echo "Waiting for Elasticsearch to be ready..."
MAX_RETRIES=60
RETRY_COUNT=0

until curl -s http://localhost:9200/_cluster/health | python3 -c "
import sys, json
health = json.load(sys.stdin)
status = health.get('status', '')
if status in ('green', 'yellow'):
    print(f'Elasticsearch is ready (status: {status})')
    sys.exit(0)
else:
    sys.exit(1)
" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Elasticsearch failed to start after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "Waiting for Elasticsearch... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 5
done

echo "Running setup script..."
python3 /opt/setup/setup.py

echo "Setup complete. Elasticsearch is running (PID: $ES_PID)"
wait $ES_PID
