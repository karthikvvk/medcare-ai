# MedCare AI — Corrected Deployment Guide
### Amazon Linux 2023 · EC2 · GHCR · GitHub Actions · Nginx · Certbot · DuckDNS

**Domain:** `https://medcareai.duckdns.org`
**Elastic IP:** `35.154.233.70`
**EC2 user:** `ec2-user`
**Repo:** `https://github.com/karthikvvk/medcare-ai.git`

Your EC2 instance, Elastic IP, DuckDNS record, and security group (22/80/443 inbound) are already confirmed working. This guide covers everything from a blank instance to a live auto-deploying app, with the volume-path bug from the old guide fixed to match your real GitHub Actions workflow.

---

## The one bug this guide fixes

Your **actual** deploy workflow (`.github/workflows/deploy.yml`) runs:

```bash
docker run -d --name medcare-ai -p 8000:8000 \
  -v /data/medcare:/data \
  --env-file /home/ec2-user/medcare.env \
  ghcr.io/karthikvvk/medcare-ai:latest
```

That mounts your host's persistent folder to **`/data`** inside the container — not `/workspace`. Every command below is written to match that. If `medcare.env` still has a `sqlite:////workspace/...` path from an earlier attempt, that's the most likely reason the container was failing health checks or silently dropping data. This guide uses `/data` consistently everywhere — env file, manual first run, and the workflow.

---

## Step 1 — SSH into your EC2 instance

From your local machine:

```bash
chmod 400 ~/Downloads/medcare-key.pem
ssh -i ~/Downloads/medcare-key.pem ec2-user@35.154.233.70
```

Everything from here on runs **on the EC2 server**, unless marked "on your local machine."

---

## Step 2 — Install Docker

```bash
sudo dnf update -y
sudo dnf install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
newgrp docker
docker --version
```

---

## Step 3 — Install Nginx

```bash
sudo dnf install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
nginx -v
```

---

## Step 4 — Install Certbot + DuckDNS plugin (free HTTPS)

```bash
sudo dnf install -y python3-pip augeas-libs
sudo pip3 install certbot certbot-nginx certbot-dns-duckdns
certbot --version
```

Create the DuckDNS credentials file (get your token from duckdns.org, top of the page after logging in):

```bash
mkdir -p ~/.secrets/certbot
nano ~/.secrets/certbot/duckdns.ini
```

Paste (replace with your real token):

```ini
dns_duckdns_token = YOUR_DUCKDNS_TOKEN_HERE
```

Save (`Ctrl+X → Y → Enter`), then lock it down:

```bash
chmod 600 ~/.secrets/certbot/duckdns.ini
```

Request the certificate:

```bash
sudo certbot certonly \
  --authenticator dns-duckdns \
  --dns-duckdns-credentials ~/.secrets/certbot/duckdns.ini \
  --dns-duckdns-propagation-seconds 60 \
  -d medcareai.duckdns.org \
  --email YOUR_EMAIL@gmail.com \
  --agree-tos \
  --non-interactive
```

Set up auto-renewal:

```bash
sudo certbot renew --dry-run
echo "0 3 1 */2 * sudo certbot renew --quiet && sudo systemctl reload nginx" | crontab -
```

---

## Step 5 — Configure Nginx as reverse proxy

```bash
sudo nano /etc/nginx/conf.d/medcare.conf
```

Paste:

```nginx
server {
    listen 80;
    server_name medcareai.duckdns.org;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name medcareai.duckdns.org;

    ssl_certificate     /etc/letsencrypt/live/medcareai.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/medcareai.duckdns.org/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection keep-alive;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        client_max_body_size 50M;
    }
}
```

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 6 — Create the persistent data directory

```bash
sudo mkdir -p /data/medcare
sudo chown ec2-user:ec2-user /data/medcare
```

This is the host folder that maps to `/data` inside the container, per your workflow. SQLite lives here, and it survives every redeploy.

---

## Step 7 — Create the environment file

```bash
nano /home/ec2-user/medcare.env
```

Paste and fill in your real values:

```env
# Required — matches the -v /data/medcare:/data mount in the workflow
DATABASE_URL=sqlite:////data/medcare_pharma.db

API_BASE_URL=https://medcareai.duckdns.org
PORT=8000

# Optional — only needed if app/services/explanation_service.py calls Ollama's
# hosted cloud API for natural-language explanations. If it doesn't, delete
# these three lines.
OLLAMA_HOST=https://ollama.com
OLLAMA_MODEL=llama3.2
OLLAMA_API_KEY=your_ollama_cloud_api_key_here
```

Save (`Ctrl+X → Y → Enter`). Never commit this file to GitHub.

> **Verify before moving on:** open `app/core/config.py` and confirm the app reads `DATABASE_URL` in this `sqlite:////data/...` form, and check `app/api/main.py` for the actual health-check route (the workflow assumes `/api/health` — if your route is named differently, update Step 9's `curl` command and the workflow file to match).

---

## Step 8 — GitHub PAT and repo secrets

Generate a PAT once: `github.com/settings/tokens` → **Generate new token (classic)** → scopes `write:packages` + `read:packages`. Copy it immediately — it's shown only once.

In your repo → **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `EC2_HOST` | `35.154.233.70` |
| `EC2_SSH_KEY` | full contents of `medcare-key.pem`, `-----BEGIN` through `-----END` inclusive — get it with `cat ~/Downloads/medcare-key.pem` on your local machine |
| `GHCR_PAT` | the PAT you just generated |

`GITHUB_TOKEN` for the build-and-push job is auto-provided by GitHub — no secret needed for that one.

---

## Step 9 — First manual deploy (one time only)

Before GitHub Actions can pull an image, one has to exist in GHCR. Easiest path: push once from your local machine, then run it once on EC2.

**On your local machine**, from the repo root:

```bash
docker build -t ghcr.io/karthikvvk/medcare-ai:latest .
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u karthikvvk --password-stdin
docker push ghcr.io/karthikvvk/medcare-ai:latest
```

**Back on EC2:**

```bash
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u karthikvvk --password-stdin

docker pull ghcr.io/karthikvvk/medcare-ai:latest

docker run -d \
  --name medcare-ai \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /data/medcare:/data \
  --env-file /home/ec2-user/medcare.env \
  ghcr.io/karthikvvk/medcare-ai:latest

docker ps
docker logs medcare-ai --tail 50
curl http://localhost:8000/api/health
```

If `curl` returns something other than a clean 200/JSON response, check `docker logs medcare-ai` first — a crash loop here usually means the `DATABASE_URL` path doesn't match what `config.py` expects, or a missing env var.

Open `https://medcareai.duckdns.org` in your browser — it should load over HTTPS.

---

## Step 10 — Test the CI/CD pipeline

From your local machine:

```bash
echo "# deployed $(date)" >> README.md
git add README.md
git commit -m "test: trigger auto-deploy"
git push origin main
```

Watch **GitHub → your repo → Actions tab**. Two jobs run in sequence:

```
Build & Push to GHCR   (~3–5 min)
Deploy to EC2           (~30 sec)
```

Once both are green, reload `https://medcareai.duckdns.org` — your new code is live. From here on, every `git push origin main` auto-deploys.

---

## Day-to-day commands (on EC2)

```bash
docker logs medcare-ai -f              # live logs
docker ps                              # container status
docker restart medcare-ai              # manual restart
docker system df && du -sh /data/medcare   # disk usage
sudo systemctl status nginx            # nginx status
sudo certbot certificates              # SSL cert expiry
sudo certbot renew                     # force SSL renewal
```

---

## Quick reference — where every secret/value goes

| Value | Where it's used |
|---|---|
| GitHub PAT | `GHCR_PAT` repo secret **+** typed into `docker login` on EC2 and locally (Step 9) |
| DuckDNS token | Only in `~/.secrets/certbot/duckdns.ini` on EC2 — never a GitHub secret |
| Elastic IP `35.154.233.70` | `EC2_HOST` repo secret + DuckDNS "current ip" field |
| `.pem` key contents | `EC2_SSH_KEY` repo secret only |
| `DATABASE_URL`, `OLLAMA_*`, `PORT`, `API_BASE_URL` | `/home/ec2-user/medcare.env` on EC2 only — never a GitHub secret |
| Ollama Cloud API key | Ollama account → API keys (ollama.com), pasted into `medcare.env` — unrelated to AWS |
