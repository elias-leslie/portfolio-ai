#!/usr/bin/env bash
#
# fix-cache-permissions.sh - Fix cache directory permissions for portfolio-ai service account
#
# Creates and sets proper permissions for HuggingFace transformers cache.
# The portfolio-ai user is a system account with no home directory, so we need
# to configure a writable cache location in /var/cache.

set -euo pipefail

echo "==> Fixing cache directory permissions for portfolio-ai user..."

# Create HuggingFace cache directory
echo "Creating /var/cache/portfolio-ai/huggingface..."
sudo mkdir -p /var/cache/portfolio-ai/huggingface

# Set ownership to portfolio-ai user
echo "Setting ownership to portfolio-ai:portfolio-ai..."
sudo chown -R portfolio-ai:portfolio-ai /var/cache/portfolio-ai/huggingface

# Verify permissions
echo "Verifying permissions..."
ls -ld /var/cache/portfolio-ai/huggingface

echo ""
echo "==> Cache directory created successfully!"
echo ""
echo "Next steps:"
echo "1. Add TRANSFORMERS_CACHE environment variable to systemd services"
echo "2. Restart services to pick up the new cache location"
echo ""
echo "Add this line to portfolio-backend.service and portfolio-celery.service:"
echo "Environment=\"TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface\""
