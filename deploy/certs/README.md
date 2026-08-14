# Lab TLS material (mkcert)

Do not commit `*.pem` files. `lab-key.pem` and the mkcert CA key are secrets.

```text
python scripts/lab_https.py --apply-env
```

Then start Caddy. **No Docker:** install [Caddy](https://caddyserver.com/docs/install) and run from repo root (elevated if `:80`/`:443` bind fails):

```text
caddy run --config deploy/Caddyfile.host --adapter caddyfile
```

Compose: `docker compose --profile edge up caddy` (`deploy/Caddyfile`).

That writes:

| File | Role |
|------|------|
| `lab.pem` / `lab-key.pem` | Caddy `:443` server cert (localhost + LAN IP SANs) |
| `rootCA.pem` | **Public** CA — phones download `http://<LAN>/lab/ca.crt` |

Install the CA on the phone **before** opening `https://<LAN>/demo/whip/`. iOS: Settings → Profile Downloaded → install, then Settings → General → About → Certificate Trust Settings → Full Trust. Android Chrome: open the `.crt` and install as a CA.

Production uses a public hostname + Let’s Encrypt, not these files.
