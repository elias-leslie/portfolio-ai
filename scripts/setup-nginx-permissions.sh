#!/bin/bash
# Grant kasadis permission to manage nginx without password
# Run with: sudo bash ~/portfolio-ai/scripts/setup-nginx-permissions.sh

set -e

cat > /etc/sudoers.d/portfolio-nginx << 'EOF'
# Allow kasadis to manage nginx without password
kasadis ALL=(ALL) NOPASSWD: /usr/sbin/nginx
kasadis ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx
kasadis ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload nginx
kasadis ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop nginx
kasadis ALL=(ALL) NOPASSWD: /usr/bin/systemctl start nginx
kasadis ALL=(ALL) NOPASSWD: /usr/bin/systemctl status nginx
kasadis ALL=(ALL) NOPASSWD: /usr/bin/tail -f /var/log/nginx/*
kasadis ALL=(ALL) NOPASSWD: /usr/bin/tail /var/log/nginx/*
kasadis ALL=(ALL) NOPASSWD: /usr/bin/cat /var/log/nginx/*
EOF

chmod 440 /etc/sudoers.d/portfolio-nginx
visudo -c

echo "Done. You can now run nginx commands without password:"
echo "  sudo nginx -t"
echo "  sudo systemctl restart nginx"
echo "  sudo tail -f /var/log/nginx/portfolio-ai-error.log"
