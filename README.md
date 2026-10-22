# PostfixAdmin Lite

Small FastAPI admin UI that talks directly to your existing PostfixAdmin `domain` and `alias` tables. No PHP, no schema changes.

## Setup (Rocky 9)

```bash
# Install system deps if needed
sudo dnf install -y python3-pip python3-devel mariadb-devel

cd /opt/postfixadmin-lite   # or wherever you copy these files

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your DB credentials, admin password, and SSL paths
```

## HTTPS

If you have certs (Let's Encrypt, commercial, or self-signed), set in `.env`:

```
SSL_CERTFILE=/etc/letsencrypt/live/mail.example.com/fullchain.pem
SSL_KEYFILE=/etc/letsencrypt/live/mail.example.com/privkey.pem
# SSL_CA_CERTS=...   # only if needed and not already in the cert file
```

The app will automatically start with HTTPS when both `SSL_CERTFILE` and `SSL_KEYFILE` are set. Otherwise it falls back to HTTP.

Make sure the user running the app can read the key file (often `chmod 640` + group membership, or run as a user that has access).

## Run

```bash
source venv/bin/activate
python main.py
```

Or with systemd (example unit):

```ini
[Unit]
Description=PostfixAdmin Lite
After=network.target mariadb.service

[Service]
Type=simple
User=postfixadmin
WorkingDirectory=/opt/postfixadmin-lite
EnvironmentFile=/opt/postfixadmin-lite/.env
ExecStart=/opt/postfixadmin-lite/venv/bin/python main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Auth

HTTP Basic Auth. Username can be anything; password is the `ADMIN_PASSWORD` from `.env`.

## What it does

- List / create / edit / delete domains
- List / create / edit / delete aliases
- Toggle active flag
- When deleting a domain, related aliases are also removed

Tables used: `domain`, `alias` (exactly as in PostfixAdmin).
