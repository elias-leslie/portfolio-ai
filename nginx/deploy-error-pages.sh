#!/bin/bash
# Deploy custom error pages for nginx

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating error pages directory..."
sudo mkdir -p /var/www/portfolio-ai/error-pages

echo "Copying 502 error page..."
sudo cp "$SCRIPT_DIR/502.html" /var/www/portfolio-ai/error-pages/

echo "Updating nginx config..."
sudo cp "$SCRIPT_DIR/portfolio-ai.conf" /etc/nginx/sites-available/portfolio-ai

echo "Testing nginx configuration..."
sudo nginx -t

echo "Reloading nginx..."
sudo systemctl reload nginx

echo "Done! Custom dark mode error page with auto-recovery is now active."
