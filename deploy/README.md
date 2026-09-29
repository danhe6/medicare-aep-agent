# Deploy on Nebius AI Cloud

One small CPU VM runs everything: the app container (FastAPI + built React site) and Caddy (automatic HTTPS).
Models are called on Nebius Token Factory; health profiles stay in users' browsers; nothing health-related is
written to disk (TRACE_LOG=0, uploaded photos are deleted right after they are read).

## 1. Create the VM (Nebius console)
- Compute → Virtual machines → Create. Ubuntu 24.04, CPU only, 2 vCPU / 8 GB RAM, 50 GB disk.
- Public IP: on. Add your SSH public key (`cat ~/.ssh/id_ed25519.pub` on your Mac; create one with
  `ssh-keygen -t ed25519` if it doesn't exist).
- Allow inbound TCP 22, 80, 443.

## 2. On the VM
```bash
ssh <user>@<PUBLIC_IP>
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER && exit   # log in again after
git clone https://github.com/danhe6/medicare-aep-agent.git      # private repo: use a GitHub token as password
cd medicare-aep-agent
nano .env      # NEBIUS_API_KEY=...  TAVILY_API_KEY=...  GITHUB_TOKEN=... (fine-grained, read-only, this repo)
cd deploy
DOMAIN=<PUBLIC-IP-with-dashes>.sslip.io docker compose up -d --build
docker compose logs -f app         # wait for "datasync: CURRENT -> ..." and "Application startup complete"
```
Open `https://<PUBLIC-IP-with-dashes>.sslip.io` (e.g. `https://203-0-113-10.sslip.io`). Caddy gets the
certificate automatically; sslip.io maps that name to the IP, so no domain purchase is needed.

## 3. Update after a new push
```bash
cd ~/medicare-aep-agent && git pull && cd deploy && DOMAIN=... docker compose up -d --build
```
New weekly data releases are picked up automatically every 6 hours (DATA_REFRESH_HOURS), no redeploy needed.

## Checklist before judging (Dec 1-15)
- VM stays on and billing credits cover through Dec 15.
- `curl https://<domain>/api/meta` shows the newest release_id.
