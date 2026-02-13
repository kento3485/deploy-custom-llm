#!/bin/bash
set -e

ES_URL="${ELASTICSEARCH_URL:-http://elasticsearch:9200}"

echo "Waiting for Elasticsearch at $ES_URL ..."
MAX_RETRIES=60
RETRY_COUNT=0

until curl -s "$ES_URL/_cluster/health" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Elasticsearch not available after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "Waiting... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 5
done

echo "Elasticsearch is ready. Running create_database.py ..."
python create_database.py

echo "Database initialization complete. Worker exiting."
