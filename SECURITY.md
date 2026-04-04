# Security Hardening Guide

This document covers recommended security measures for deploying web_share_app in a public-facing environment. Items marked **[implemented]** are already handled by the application or installer. All others require manual configuration.

---

## App-level

### Admin rate limiting [implemented]

Failed admin authentication attempts are tracked per IP address. After 5 failures within a 15-minute window, that IP is locked out for the remainder of the window. The lockout resets on service restart.

`X-Forwarded-For` is respected, so the real client IP is used when the app sits behind a reverse proxy. No configuration required.

### HTML output escaping [implemented]

Values from `content_config.json` inserted into the Open Graph meta tags (site title, URLs) are HTML-escaped before injection, preventing malformed output if the config contains special characters.

### Security response headers

Set these headers at your reverse proxy. They cost nothing and eliminate entire classes of browser-side attacks.

**Caddy** — add to your site block:

```caddy
header {
    X-Content-Type-Options    "nosniff"
    X-Frame-Options           "DENY"
    Referrer-Policy           "no-referrer"
    Content-Security-Policy   "default-src 'self'; media-src 'self' blob:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    -Server
}
```

**nginx** — add to your `server` or `location` block:

```nginx
add_header X-Content-Type-Options  "nosniff"          always;
add_header X-Frame-Options         "DENY"              always;
add_header Referrer-Policy         "no-referrer"       always;
add_header Content-Security-Policy "default-src 'self'; media-src 'self' blob:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'" always;
more_clear_headers Server;
```

> **Note on CSP:** `unsafe-inline` is required for the inline styles used by the flavor overlay components. If you remove those features, you can tighten this policy.

---

## Service hardening

### Non-root service user [implemented]

The installer creates a system account `webshare` with no login shell and no home directory, and runs the service as that user. File permissions are set as follows:

| Path | Owner | Mode | Purpose |
|---|---|---|---|
| `$APP_DIR/` | `webshare` | `750` | App root, not world-readable |
| `$APP_DIR/.env` | `webshare` | `600` | Secrets, owner-only |
| `$APP_DIR/data/` | `webshare` | `700` | SQLite database, owner-only |
| `$APP_DIR/backgrounds/` | `webshare` | `755` | Background files |
| `/var/log/webshare/` | `webshare` | `750` | Log files |

If you add background files after installation, they will be owned by root by default and may not be readable by the service. Fix with:

```sh
chown webshare:webshare /path/to/web_share_app/backgrounds/*
```

---

## Network hardening

### Restrict port 80 to the reverse proxy only

The app listens on `0.0.0.0:80`, which means anything on your LAN can reach it directly, bypassing your reverse proxy and HTTPS. Lock it down.

**If the reverse proxy is on a separate host**, use nftables on the container to only accept connections from the proxy's IP:

```sh
# /etc/nftables.conf
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;
        iif lo accept
        ct state established,related accept
        tcp dport 22 accept
        tcp dport 80 ip saddr YOUR_PROXY_IP accept
    }
}
```

Apply: `nft -f /etc/nftables.conf`

To persist across reboots on Alpine:
```sh
rc-update add nftables boot
```

**If the reverse proxy is on the same host**, bind Uvicorn to localhost only instead. Edit the service definition to use `--host 127.0.0.1`:

*OpenRC* (`/etc/init.d/webshare`):
```sh
command_args="app.main:app --host 127.0.0.1 --port 8000 --workers 1"
```

*systemd* (`/etc/systemd/system/webshare.service`):
```ini
ExecStart=/path/to/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

### Admin path rate limiting at the reverse proxy

A second layer of rate limiting at the proxy level catches attacks before they reach the app. This also covers the case where the service restarts and the in-memory lockout resets.

**Caddy:**
```caddy
@admin path /admin /api/admin/*
rate_limit @admin {
    zone admin_zone {
        key    {remote_host}
        events 10
        window 1m
    }
}
```

**nginx** (requires `ngx_http_limit_req_module`, included in most builds):
```nginx
limit_req_zone $binary_remote_addr zone=admin:10m rate=10r/m;

location ~ ^/(admin|api/admin) {
    limit_req zone=admin burst=5 nodelay;
    proxy_pass http://localhost:80;
}
```

### Cloudflare (if applicable)

If Cloudflare sits in front of your reverse proxy:

- Enable **Bot Fight Mode** (Security → Bots)
- Add a **Rate Limiting rule** on `/admin*` and `/api/admin*` paths
- Set the WAF to **Medium** sensitivity or higher
- These are available on the free plan

---

## Container hardening (Proxmox LXC)

### Use an unprivileged container

Unprivileged containers map the container's root user (UID 0) to an unpredictable high UID on the Proxmox host (e.g. UID 100000). A container escape does not yield host root access.

Set this at container creation time in the Proxmox UI: **Unprivileged container: ✓**. It cannot be changed after creation without recreating the container.

### Set resource limits

In the Proxmox UI under the container's **Resources** tab:

| Resource | Suggested limit |
|---|---|
| CPU cores | 1–2 |
| Memory | 256–512 MB |
| Swap | 256 MB |
| Disk | Size appropriately for your backgrounds directory |

These prevent a compromised or misbehaving container from impacting other services on the host.

---

## Secrets management

### Jellyfin API key scoping

Create a dedicated Jellyfin service account for this app rather than using your admin API key. The app only needs read access to the library. If the key is ever exposed, the blast radius is limited to read access on media metadata and streams — not Jellyfin administration.

In Jellyfin: **Dashboard → API Keys → + (Add)** — create a key named `webshare` and note it is not associated with an admin user.

### ADMIN_TOKEN strength

The admin token is the only authentication barrier for the admin portal. Use a randomly generated string of at least 32 characters. Generate one with:

```sh
openssl rand -base64 32
```

### .env file permissions

The installer sets `.env` to mode `600` (owner read/write only). Verify this is intact after any manual edits:

```sh
ls -la /path/to/web_share_app/.env
# Should show: -rw------- 1 webshare webshare
```

---

## Ongoing

- **Keep Alpine packages updated:** `apk upgrade` periodically, or set up `apk-cron` for automatic security updates.
- **Monitor logs** at `/var/log/webshare/` for unusual patterns — repeated 401s on `/api/admin`, unexpected IPs, abnormal stream request volumes.
- **Rotate the ADMIN_TOKEN** if you suspect it has been observed. Update `.env` and restart the service.
