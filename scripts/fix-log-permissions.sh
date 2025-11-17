#!/bin/bash
# Fix log file permissions for portfolio-ai services

echo "Fixing log file permissions..."
sudo chown portfolio-ai:portfolio-ai /var/log/portfolio-ai/*.log
sudo chmod 644 /var/log/portfolio-ai/*.log

echo "Restarting services..."
sudo systemctl restart portfolio-backend portfolio-celery portfolio-beat portfolio-frontend

echo "Done! Services restarted with correct log permissions."
