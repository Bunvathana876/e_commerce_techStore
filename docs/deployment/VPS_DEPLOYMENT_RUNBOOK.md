# Blue Panda E-Commerce — Production Linux VPS Deployment Runbook

**Document Version:** 1.0.0  
**Target Architecture:** Single-node Linux Virtual Private Server (VPS)  
**Operating System:** Ubuntu 22.04 LTS / 24.04 LTS (x86_64 or aarch64)  
**Security Level:** Production / High-Assurance  

---

## 1. Architecture Overview

The Blue Panda production stack consists of six core services coordinated via Docker Compose, isolated on private container networks, with Caddy providing edge TLS termination:

```
[ Public Internet ]
        |
        | :80 / :443 (HTTPS, HTTP/3, Let's Encrypt TLS)
        v
+-------------------------------------------------------------------------+
| Host OS (Ubuntu Linux, UFW Firewall: 22, 80, 443)                       |
|                                                                         |
| +---------------------------------------------------------------------+ |
| | Caddy Reverse Proxy (Edge Container, Non-Root, no-new-privileges)    | |
| +---------------------------------------------------------------------+ |
|      | shop.example.com            | manage.example.com    | api.example.com
|      v                             v                       v            |
| +-------------------------+ +---------------------+ +-----------------+ |
| | Storefront (Next.js 16) | | Management (Next.js)| | Backend API     | |
| | Port 3000 (Internal)    | | Port 3001 (Internal)| | (FastAPI)       | |
| | Non-Root node:node      | | Non-Root node:node  | | 2 Uvicorn       | |
| +-------------------------+ +---------------------+ | Workers         | |
|                                                     +-----------------+ |
|                                                              |          |
| [ Internal Bridge Network: data (No Host Port Binding) ]     |          |
|      +-------------------------------------------------------+          |
|      |                                                       |          |
|      v                                                       v          |
| +------------------------------------+ +------------------------------+ |
| | PostgreSQL 16 (Private Container)  | | Redis 7.4 (Private Container)| |
| | Data Volume: postgres_data         | | In-Memory Sliding Window Rate| |
| | Least-Privilege DML Role           | | Limiting with Lua Scripts    | |
| +------------------------------------+ +------------------------------+ |
+-------------------------------------------------------------------------+
```

---

## 2. Server Specifications & Prerequisites

### 2.1 Hardware Requirements
- **CPU:** 2 vCPU cores minimum (4 vCPU recommended for high concurrency)
- **RAM:** 4 GB minimum (8 GB recommended for combined builds + PostgreSQL cache)
- **Storage:** 40 GB NVMe / SSD minimum
- **Network:** 1 Gbps port, static public IPv4 (and optional IPv6)

### 2.2 Domain Names & DNS Configuration
Configure DNS `A` records (and `AAAA` if IPv6 is enabled) at your domain registrar/DNS provider before starting:
- `shop.yourdomain.com`  -> `YOUR_VPS_PUBLIC_IP`
- `manage.yourdomain.com` -> `YOUR_VPS_PUBLIC_IP`
- `api.yourdomain.com`    -> `YOUR_VPS_PUBLIC_IP`

*TTL recommendation:* Set to `300` (5 minutes) during initial launch to allow rapid DNS corrections if necessary.

---

## 3. Host Hardening & OS Preparation

### 3.1 Update System Packages
Connect to your VPS as `root` via SSH:
```bash
apt-get update && apt-get upgrade -y
apt-get install -y ufw curl wget git jq openssl ca-certificates gnupg lsb-release
```

### 3.2 Create Dedicated Non-Root Deployment User
Do not run application containers or management scripts as `root`:
```bash
adduser --disabled-password --gecos "" bluepanda
usermod -aG sudo bluepanda
echo "bluepanda ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/bluepanda
```

### 3.3 Configure Host Firewall (UFW)
Only SSH (port 22) and Web traffic (ports 80 & 443 TCP/UDP) are exposed. All database (5432) and cache (6379) ports remain strictly internal:
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP (ACME Challenge)'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 443/udp comment 'HTTP/3 (QUIC)'
ufw enable
ufw status verbose
```

### 3.4 Install Docker Engine & Docker Compose Plugin
Install the official upstream Docker Engine:
```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Grant bluepanda user docker privileges
usermod -aG docker bluepanda
```

### 3.5 Configure Docker Log Limits
Prevent unconstrained container logs from exhausting disk space. Create `/etc/docker/daemon.json`:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "5"
  }
}
```
Restart Docker to apply:
```bash
systemctl restart docker
```

---

## 4. Application Checkout & Directory Structure

Log in as the `bluepanda` user:
```bash
su - bluepanda
```

### 4.1 Deployment Workspace
Create the production deployment root at `/opt/blue-panda`:
```bash
sudo mkdir -p /opt/blue-panda
sudo chown bluepanda:bluepanda /opt/blue-panda
cd /opt/blue-panda
```

### 4.2 Code Setup Procedure
Due to the repository's modular sub-repository architecture, clone the root deployment files and source components:
```bash
# Clone the deployment orchestration repository
git clone https://github.com/Bunvathana876/e_commerce_backend.git backend
git clone https://github.com/Bunvathana876/e_commerce_storefront.git storefront
git clone https://github.com/Bunvathana876/e_commerce_mangement.git management

# Ensure deploy/ and scripts/ directories are present
# (Copy deploy/ from the staging-verified tree)
mkdir -p deploy/production deploy/scripts
```

Ensure production helper scripts are executable:
```bash
chmod +x deploy/scripts/*.sh
chmod +x deploy/production/*.sh
```

---

## 5. Production Environment & Secret Generation

### 5.1 Initialize `.env` from Template
```bash
cp deploy/production/.env.example deploy/production/.env
chmod 600 deploy/production/.env
```

### 5.2 Cryptographic Secret Generation
Generate high-entropy random secrets using OpenSSL:
```bash
# Generate secrets
ADMIN_DB_PASS=$(openssl rand -hex 24)
APP_DB_PASS=$(openssl rand -hex 24)
REDIS_PASS=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Generate backup encryption key (store securely off-server!)
sudo mkdir -p /etc/blue-panda
openssl rand -hex 32 | sudo tee /etc/blue-panda/backup.key > /dev/null
sudo chmod 400 /etc/blue-panda/backup.key
sudo chown bluepanda:bluepanda /etc/blue-panda/backup.key
```

### 5.3 Configure `deploy/production/.env`
Populate `/opt/blue-panda/deploy/production/.env` with production parameters:
```ini
COMPOSE_PROJECT_NAME=blue-panda-production
CADDY_IMAGE=caddy:2.8.4-alpine
POSTGRES_IMAGE=postgres:16-alpine
REDIS_IMAGE=redis:7.4-alpine

STOREFRONT_IMAGE=blue-panda-storefront:prod
MANAGEMENT_IMAGE=blue-panda-management:prod
BACKEND_IMAGE=blue-panda-backend:prod

# Real Domain Names
SHOP_DOMAIN=shop.yourdomain.com
MANAGE_DOMAIN=manage.yourdomain.com
API_DOMAIN=api.yourdomain.com
ACME_EMAIL=admin@yourdomain.com

# PostgreSQL Configuration
POSTGRES_DB=blue_panda_production
POSTGRES_USER=blue_panda_admin
POSTGRES_PASSWORD=<INSERT_ADMIN_DB_PASS>
APP_DB_USER=blue_panda_app
APP_DB_PASSWORD=<INSERT_APP_DB_PASS>
POSTGRES_MAX_CONNECTIONS=150
POSTGRES_SHARED_BUFFERS=256MB

# Backend Database Connection (Least-Privilege App User)
DATABASE_URL=postgresql+psycopg2://blue_panda_app:<INSERT_APP_DB_PASS>@postgres:5432/blue_panda_production

# Redis Distributed Rate Limiting
REDIS_PASSWORD=<INSERT_REDIS_PASS>
RATE_LIMIT_STORAGE_URL=redis://:<INSERT_REDIS_PASS>@redis:6379/0
RATE_LIMIT_FAIL_OPEN=true

# Authentication & Security
JWT_SECRET_KEY=<INSERT_JWT_SECRET>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=["https://shop.yourdomain.com","https://manage.yourdomain.com"]
BACKEND_WORKERS=2
TRUSTED_PROXY_IPS=172.16.0.0/12

# Runtime Upload Limits
MAX_REQUEST_BODY_SIZE=10MB
MAX_UPLOAD_SIZE_BYTES=5242880
MAX_IMAGE_DIMENSION=4096
MAX_IMAGE_PIXELS=16777216

# Next.js Build-Time Public Endpoints
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api
NEXT_PUBLIC_MANAGEMENT_URL=https://manage.yourdomain.com
NEXT_PUBLIC_STOREFRONT_URL=https://shop.yourdomain.com

# Encrypted Backup Settings
BACKUP_DESTINATION=/opt/blue-panda-backups
BACKUP_RETENTION_DAYS=30
BACKUP_ENCRYPTION_KEY_FILE=/etc/blue-panda/backup.key
```

---

## 6. Building Production Docker Images

Build immutable production images locally on the host:
```bash
cd /opt/blue-panda

# 1. Build Backend API
docker build -t blue-panda-backend:prod -f backend/Dockerfile.prod backend

# 2. Build Storefront Website (injecting build-time API domain)
docker build -t blue-panda-storefront:prod -f storefront/Dockerfile.prod \
  --build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api \
  --build-arg NEXT_PUBLIC_MANAGEMENT_URL=https://manage.yourdomain.com \
  storefront

# 3. Build Management Admin Website (injecting build-time API domain)
docker build -t blue-panda-management:prod -f management/Dockerfile.prod \
  --build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api \
  --build-arg NEXT_PUBLIC_STOREFRONT_URL=https://shop.yourdomain.com \
  management
```

Verify images exist and non-root users are configured:
```bash
docker images | grep blue-panda
```

---

## 7. Database Initialization & Schema Migrations

### 7.1 Start PostgreSQL and Redis First
Start the persistence layer to allow database initialization:
```bash
docker compose -f deploy/production/compose.yaml up -d postgres redis
```

Wait 10 seconds and check container health:
```bash
docker compose -f deploy/production/compose.yaml ps
```
Both `postgres` and `redis` must display `(healthy)`.

### 7.2 Execute Operator-Approved Alembic Migrations
Migrations are strictly decoupled from application container boot:
```bash
./deploy/scripts/migrate-approved.sh --compose
```
Verify output shows:
```
Post-migration revision: ... (head)
Schema migration executed successfully.
```

### 7.3 Apply Least-Privilege DML Permissions
Apply strict DML permissions to `blue_panda_app` so it cannot alter or drop tables:
```bash
./deploy/scripts/setup-db-least-privilege.sh
```

---

## 8. Launching the Full Stack

### 8.1 Start Application & Reverse Proxy Containers
```bash
docker compose -f deploy/production/compose.yaml up -d
```

### 8.2 Monitor Container Startup
Watch health checks transition to healthy:
```bash
watch docker compose -f deploy/production/compose.yaml ps
```
Expected output:
```
NAME                                   STATUS
blue-panda-production-backend-1        Up (healthy)
blue-panda-production-caddy-1          Up (healthy)
blue-panda-production-management-1     Up (healthy)
blue-panda-production-postgres-1       Up (healthy)
blue-panda-production-redis-1          Up (healthy)
blue-panda-production-storefront-1     Up (healthy)
```

---

## 9. Verification & Validation Probes

Execute the verification checklist to confirm production readiness:

### 9.1 Internal Readiness Probe
```bash
docker compose -f deploy/production/compose.yaml exec backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/readyz').read().decode())"
```
*Expected:* `{"status":"ready","database":"connected"}`

### 9.2 Rate Limiter Redis Connection
```bash
docker compose -f deploy/production/compose.yaml exec redis redis-cli -a "$REDIS_PASSWORD" ping
```
*Expected:* `PONG`

### 9.3 Public HTTPS Probes
From an external computer or terminal:
```bash
# 1. Check Storefront Homepage
curl -Iv https://shop.yourdomain.com

# 2. Check Management Admin Portal
curl -Iv https://manage.yourdomain.com

# 3. Check API Health
curl -Iv https://api.yourdomain.com/health

# 4. Check Documentation Disabled in Production (404 expected)
curl -s -o /dev/null -w "%{http_code}\n" https://api.yourdomain.com/docs
# Expected: 404
```

### 9.4 Verify TLS Certificate Issuance
Check Caddy logs to confirm Let's Encrypt / ZeroSSL issued valid certificates:
```bash
docker compose -f deploy/production/compose.yaml logs caddy | grep -i "certificate obtained"
```

---

## 10. Automated Encrypted Backup Setup

### 10.1 Prepare Backup Directory
```bash
sudo mkdir -p /opt/blue-panda-backups
sudo chown bluepanda:bluepanda /opt/blue-panda-backups
```

### 10.2 Configure Daily Backup Cron
Open crontab:
```bash
crontab -e
```
Add daily backup at 02:30 UTC:
```cron
30 2 * * * /opt/blue-panda/deploy/scripts/backup-postgres.sh >> /opt/blue-panda-backups/backup.log 2>&1
```

### 10.3 Test Encrypted Backup Execution
Manually trigger a backup to verify OpenSSL PBKDF2 encryption:
```bash
/opt/blue-panda/deploy/scripts/backup-postgres.sh
```
Check that encrypted `.sql.gz.enc` file was generated:
```bash
ls -lh /opt/blue-panda-backups/
```

### 10.4 Verify Disaster Recovery Restore Drill
Test that the backup can be decrypted and restored cleanly into an isolated drill database:
```bash
LATEST_BACKUP=$(ls -t /opt/blue-panda-backups/*.enc | head -n 1)
/opt/blue-panda/deploy/scripts/restore-drill.sh "${LATEST_BACKUP}"
```
*Expected:* `Disaster recovery drill PASSED 100%! All checks succeeded.`

---

## 11. Zero / Minimal-Downtime Application Upgrades

When releasing application code updates:

### Step 1: Pull Code & Build New Images
```bash
cd /opt/blue-panda
git pull origin main

# Rebuild images with new version tags
docker build -t blue-panda-backend:v1.1.0 -f backend/Dockerfile.prod backend
```

### Step 2: Create Pre-Deployment Backup
```bash
./deploy/scripts/backup-postgres.sh
```

### Step 3: Run Database Migrations (if any)
```bash
./deploy/scripts/migrate-approved.sh --compose
```

### Step 4: Gracefully Recreate Containers
Update the image tags in `.env` and recreate the services:
```bash
docker compose -f deploy/production/compose.yaml up -d --no-deps backend storefront management
```
Caddy will automatically buffer incoming requests during the momentary sub-second container swap.

---

## 12. Rollback Procedure

If an update introduces regressions or errors:

### 12.1 Fast Image Rollback
1. Revert image tags in `deploy/production/.env`:
   ```ini
   BACKEND_IMAGE=blue-panda-backend:prod-previous
   STOREFRONT_IMAGE=blue-panda-storefront:prod-previous
   MANAGEMENT_IMAGE=blue-panda-management:prod-previous
   ```
2. Reapply containers:
   ```bash
   docker compose -f deploy/production/compose.yaml up -d
   ```

### 12.2 Database Rollback (Emergency Only)
If migrations corrupted data or failed mid-way:
1. Stop the application backend:
   ```bash
   docker compose -f deploy/production/compose.yaml stop backend
   ```
2. Restore from the pre-deployment encrypted backup:
   ```bash
   RESTORE_CONFIRM=true ./deploy/scripts/restore-drill.sh /opt/blue-panda-backups/blue_panda_production_YYYYMMDD_HHMMSS.sql.gz.enc
   ```
3. Restart backend:
   ```bash
   docker compose -f deploy/production/compose.yaml start backend
   ```

---

## 13. Incident Response & Troubleshooting Checklist

| Symptom | Diagnostic Command | Remediation Step |
| :--- | :--- | :--- |
| **502 Bad Gateway from Caddy** | `docker compose -f deploy/production/compose.yaml logs caddy` | Check if backend or storefront container crashed: `docker compose ps` |
| **Backend Failing Health Check** | `docker compose -f deploy/production/compose.yaml logs backend` | Verify PostgreSQL connection and `/readyz` response. Check database disk space. |
| **Database Connection Exhaustion** | `docker compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"` | Check `max_connections` in `compose.yaml` (default 150) vs total worker pools. |
| **Redis Connection Error** | `docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping` | If Redis is down and `RATE_LIMIT_FAIL_OPEN=true`, API requests will proceed. Restart Redis: `docker compose restart redis`. |
| **Disk Space Alert** | `df -h` | Prune unused docker images: `docker image prune -a -f`. Check `/opt/blue-panda-backups`. |
