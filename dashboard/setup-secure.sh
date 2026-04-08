#!/bin/bash

# Setup script for secure dashboard with HTTPS and basic auth
# Run this script before starting the dashboard with docker-compose-secure.yml

set -e

echo "=== Sandbox Dashboard Security Setup ==="
echo ""

# Create directories
mkdir -p ssl auth

# Generate self-signed SSL certificate
if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then
    echo "📜 Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/key.pem \
        -out ssl/cert.pem \
        -subj "/C=EU/ST=State/L=City/O=Organization/CN=sandbox-dashboard"
    echo "✅ SSL certificate generated (valid for 365 days)"
    echo "   Location: ssl/cert.pem, ssl/key.pem"
else
    echo "✅ SSL certificate already exists"
fi

echo ""

# Create htpasswd file for basic auth
if [ ! -f auth/.htpasswd ]; then
    echo "🔐 Setting up basic authentication..."
    echo ""
    echo "Please enter a username for dashboard access:"
    read -r USERNAME

    echo "Please enter a password:"
    # Use docker to run htpasswd if available, otherwise check if htpasswd is installed
    if command -v docker &> /dev/null; then
        docker run --rm -it httpd:alpine htpasswd -nB "$USERNAME" > auth/.htpasswd
    elif command -v htpasswd &> /dev/null; then
        htpasswd -cB auth/.htpasswd "$USERNAME"
    else
        echo "❌ Error: Neither docker nor htpasswd is available"
        echo "   Install apache2-utils (Debian/Ubuntu) or httpd-tools (RHEL/CentOS)"
        exit 1
    fi

    echo "✅ Basic auth credentials created"
    echo "   Username: $USERNAME"
else
    echo "✅ Basic auth file already exists"
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "To start the secure dashboard:"
echo "  docker-compose -f docker-compose-secure.yml up -d"
echo ""
echo "Access the dashboard at:"
echo "  https://YOUR_IP (or https://localhost for testing)"
echo ""
echo "Note: You'll see a browser warning about the self-signed certificate."
echo "      This is normal - click 'Advanced' and 'Proceed' to continue."
echo ""
echo "For production, replace ssl/cert.pem and ssl/key.pem with real certificates"
echo "(e.g., from Let's Encrypt)"
