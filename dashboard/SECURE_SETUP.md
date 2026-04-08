# Secure Dashboard Setup (HTTPS + Authentication)

This guide shows how to deploy the dashboard with **HTTPS encryption** and **basic authentication**.

## Quick Setup

### 1. Run the Setup Script

```bash
cd dashboard
./setup-secure.sh
```

This will:
- Generate a self-signed SSL certificate (valid 365 days)
- Create basic auth credentials (username/password)
- Set up required directories

### 2. Start the Secure Dashboard

```bash
docker-compose -f docker-compose-secure.yml up -d
```

### 3. Access the Dashboard

Open your browser to:
```
https://YOUR_EC2_IP
```

You'll be prompted for:
1. **Browser warning**: Click "Advanced" → "Proceed" (self-signed cert)
2. **Login prompt**: Enter the username/password you created

## Architecture

```
Browser (HTTPS)
    ↓
Nginx (:443) - SSL Termination + Basic Auth
    ↓
Streamlit Dashboard (:8083) - Internal network
    ↓
DynamoDB (via IAM role)
```

## Security Features

✅ **HTTPS/TLS encryption** - All traffic encrypted
✅ **Basic authentication** - Username/password required
✅ **Security headers** - HSTS, X-Frame-Options, etc.
✅ **HTTP → HTTPS redirect** - Port 80 redirects to 443
✅ **Internal network** - Dashboard not exposed directly

## Production SSL Certificate

For production, replace the self-signed certificate with a real one:

### Option 1: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Stop nginx temporarily
docker-compose -f docker-compose-secure.yml stop nginx

# Get certificate (replace with your domain)
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem dashboard/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem dashboard/ssl/key.pem

# Restart nginx
docker-compose -f docker-compose-secure.yml up -d nginx
```

### Option 2: Use Existing Certificates

```bash
# Copy your certificates to the ssl directory
cp /path/to/your/cert.pem dashboard/ssl/cert.pem
cp /path/to/your/key.pem dashboard/ssl/key.pem

# Restart nginx
docker-compose -f docker-compose-secure.yml restart nginx
```

## Managing Users

### Add a New User

```bash
# Using docker
docker run --rm -it httpd:alpine htpasswd -nB newuser >> auth/.htpasswd

# Or using htpasswd directly
htpasswd -B auth/.htpasswd newuser

# Restart nginx to apply changes
docker-compose -f docker-compose-secure.yml restart nginx
```

### Remove a User

```bash
# Edit the file and remove the line for that user
nano auth/.htpasswd

# Restart nginx
docker-compose -f docker-compose-secure.yml restart nginx
```

### Change Password

```bash
# Remove old entry and add new one
htpasswd -B auth/.htpasswd username

# Restart nginx
docker-compose -f docker-compose-secure.yml restart nginx
```

## Troubleshooting

### Can't access on port 443

**Check EC2 Security Group:**
```
Inbound Rules:
- Type: HTTPS
- Port: 443
- Source: Your IP (or 0.0.0.0/0 for testing)
```

**Check nginx is running:**
```bash
docker ps | grep nginx
docker logs sandbox-dashboard-nginx
```

### SSL Certificate Error

**For self-signed cert**: This is normal. Click "Advanced" → "Proceed to site"

**For production**: Verify certificate files:
```bash
openssl x509 -in ssl/cert.pem -text -noout
```

### Authentication Not Working

**Check htpasswd file exists:**
```bash
ls -la auth/.htpasswd
cat auth/.htpasswd  # Should show username:hashed_password
```

**Test credentials:**
```bash
# From outside the container
curl -u username:password -k https://localhost
```

### View Logs

```bash
# Nginx logs
docker logs sandbox-dashboard-nginx

# Dashboard logs
docker logs sandbox-dashboard
```

## Port Reference

| Port | Service | Exposed |
|------|---------|---------|
| 443  | HTTPS (nginx) | Yes - External |
| 80   | HTTP redirect | Yes - Redirects to 443 |
| 8083 | Streamlit | No - Internal only |

## Files Structure

```
dashboard/
├── ssl/
│   ├── cert.pem          # SSL certificate
│   └── key.pem           # SSL private key
├── auth/
│   └── .htpasswd         # Basic auth credentials
├── nginx.conf            # Nginx configuration
├── docker-compose-secure.yml
└── setup-secure.sh
```

## Updating Dashboard

When you update the dashboard code:

```bash
# Rebuild dashboard image
docker-compose -f docker-compose-secure.yml build dashboard

# Restart services
docker-compose -f docker-compose-secure.yml down
docker-compose -f docker-compose-secure.yml up -d
```

The nginx config and auth remain unchanged.

## Monitoring

### Check if services are healthy

```bash
# Both should be running
docker ps

# Check health
docker inspect sandbox-dashboard | grep -A 5 Health
```

### Monitor resource usage

```bash
docker stats sandbox-dashboard sandbox-dashboard-nginx
```

## Backup

**Important files to backup:**
```bash
# Backup credentials
cp auth/.htpasswd auth/.htpasswd.backup

# Backup SSL certs (if custom)
cp ssl/cert.pem ssl/cert.pem.backup
cp ssl/key.pem ssl/key.pem.backup
```
