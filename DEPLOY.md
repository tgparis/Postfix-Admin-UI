# Production Deployment (Rocky Linux 9)

Recommended layout: **nginx terminates TLS** → **uvicorn listens only on localhost**.

## 1. Prepare the system

```bash
sudo dnf install -y python3 python3-pip python3-devel mariadb-devel nginx

# Create a dedicated user
sudo useradd --system --home-dir /opt/postfixadmin-lite --shell /sbin/nologin postfixadmin

# Copy the application
sudo mkdir -p /opt/postfixadmin-lite
sudo cp -a postfixadmin-lite/* /opt/postfixadmin-lite/
sudo chown -R postfixadmin:postfixadmin /opt/postfixadmin-lite
```

## 2. Python environment

```bash
sudo -u postfixadmin python3 -m venv /opt/postfixadmin-lite/venv
sudo -u postfixadmin /opt/postfixadmin-lite/venv/bin/pip install -r /opt/postfixadmin-lite/requirements.txt
```

## 3. Configuration

```bash
sudo -u postfixadmin cp /opt/postfixadmin-lite/.env.example /opt/postfixadmin-lite/.env
sudo -u postfixadmin chmod 600 /opt/postfixadmin-lite/.env
sudo -u postfixadmin vi /opt/postfixadmin-lite/.env
```

Production `.env` example (app binds only to localhost):

```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=postfix
DB_PASSWORD=your-db-password
DB_NAME=postfix

ADMIN_PASSWORD=strong-random-password-here

HOST=127.0.0.1
PORT=8080

# Leave SSL_* empty when nginx handles TLS
# SSL_CERTFILE=
# SSL_KEYFILE=
```

## 4. systemd

```bash
sudo cp postfixadmin-lite.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now postfixadmin-lite
sudo systemctl status postfixadmin-lite
```

## 5. nginx (TLS termination)

```bash
# Edit the server_name and certificate paths in the config
sudo cp nginx-postfixadmin-lite.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

Open the firewall if needed:

```bash
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 6. Optional: SELinux

If SELinux is enforcing and you see denials:

```bash
sudo setsebool -P httpd_can_network_connect 1
# or more targeted if you prefer
```

## 7. Updates

```bash
cd /opt/postfixadmin-lite
sudo -u postfixadmin /opt/postfixadmin-lite/venv/bin/pip install -U -r requirements.txt
sudo systemctl restart postfixadmin-lite
```

## Alternative: uvicorn handles TLS directly

If you prefer not to use nginx, set the SSL paths in `.env` and change the systemd unit `ExecStart` to include the SSL flags (or just run `python main.py` which already supports them). In that case set `HOST=0.0.0.0` and open the port. The nginx approach is preferred for production.

## Security notes

- Keep `.env` mode 600 and owned by the service user.
- Use a strong `ADMIN_PASSWORD`.
- Prefer binding the app to `127.0.0.1` and letting nginx handle public HTTPS.
- Consider IP allow-listing in nginx if the admin interface should not be publicly reachable.
- Regularly update the system and the Python packages.
