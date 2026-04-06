## Installation on Alpine Linux

### 1. Install system dependencies

```sh
apk add --no-cache python3 nginx uv
```


Enable OpenRC:

```sh
rc-update add nginx default
```

### 2. Deploy application code

Copy the project to `/opt/M14404` (or your preferred path):

```sh
cd /opt
mkdir M14404
git clone https://github.com/Nircek/M14404.git
cd M14404
```

### 3. Create and install Python environment with `uv`

```sh
uv sync --frozen
```

This will create a virtual environment and install all dependencies defined in `pyproject.toml`.

### 4. Configure environment

Set environment variables in `/etc/conf.d/asgi` (created by you):

```sh
cat | tee /etc/conf.d/M14404 << EOF
M14404_ENV=prod
M14404_DB_PATH=/var/lib/M14404/M14404.db
M14404_ORIGIN_DOMAIN_NAME=abc.xyz
EOF
```

Create the database directory:

```sh
mkdir -p /var/lib/M14404
chown nginx:nginx /var/lib/M14404
```

### 5. Configure OpenRC service

Copy the OpenRC script:

```sh
cp /opt/M14404/deploy/openrc/M14404 /etc/init.d/M14404
chmod +x /etc/init.d/M14404
```

Register the service:

```sh
rc-update add M14404 default
```

### 6. Configure Nginx

Copy the Nginx config:

```sh
cp /opt/M14404/deploy/nginx/M14404.conf /etc/nginx/http.d/M14404.conf
```

Test and reload Nginx:

```sh
nginx -t
rc-service nginx restart
```

### 7. Start the ASGI service

```sh
rc-service M14404 start
```

The service listens on port `8000` locally, and Nginx proxies all HTTP and WebSocket traffic from port `80` (including dynamic subdomains) to it.

