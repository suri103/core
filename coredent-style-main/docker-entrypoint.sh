#!/bin/sh
set -e

echo "Starting nginx..."

# Verify nginx configuration
echo "Verifying nginx configuration..."
nginx -t

echo "Nginx configuration is valid, starting nginx..."

# Start nginx in the background
nginx -g "daemon off;" &
NGINX_PID=$!

# Wait for nginx to be ready
echo "Waiting for nginx to be ready..."
for i in $(seq 1 30); do
    if wget --quiet --tries=1 --spider http://localhost/health 2>/dev/null; then
        echo "Nginx is ready!"
        break
    fi
    echo "Attempt $i: Nginx not ready yet..."
    sleep 1
done

# Check if nginx is ready
if ! wget --quiet --tries=1 --spider http://localhost/health 2>/dev/null; then
    echo "ERROR: Nginx failed to start properly"
    exit 1
fi

echo "Nginx started successfully with PID: $NGINX_PID"

# Wait for nginx to exit
wait $NGINX_PID
