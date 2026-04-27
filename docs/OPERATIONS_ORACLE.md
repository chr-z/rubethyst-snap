# Operações na Oracle Cloud — Always Free

Este documento cobre o que é específico de rodar **Rubethyst Snap** em
uma única VM **Ampere ARM64** do Always Free Tier (4 OCPUs, 24 GB RAM,
200 GB disco, 10 TB de egress mensal).

> **Regra de ouro:** ficheiros `.mp4` e companhia **nunca** são
> servidos por URL estática pública. Tudo passa pela API com token
> assinado de curta duração (ver "Anti-leech" abaixo).

---

## 1. Provisão da VM

* Imagem: Ubuntu 22.04 LTS (Aarch64).
* Shape: `VM.Standard.A1.Flex`, 4 OCPU / 24 GB. Os limites Always Free
  permitem distribuir entre instâncias; concentrar tudo numa só
  simplifica operação.
* Disco: 200 GB Boot Volume (block storage gratuito até esse limite).

## 2. Endurecimento mínimo do host

```bash
# Atualizações
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y unattended-upgrades fail2ban ufw

# Firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# SSH apenas com chave
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Updates desatendidos
sudo dpkg-reconfigure -plow unattended-upgrades
```

Replicar a regra na **Security List da VCN** da Oracle: abrir 22, 80,
443 e nada mais. Se o painel Next.js estiver fora da VM, restrinja 22
ao IP de operações; 80/443 ficam abertos ao mundo (Caddy emite TLS).

## 3. Docker e o stack

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

git clone https://github.com/<org>/rubethyst-snap.git /opt/snap
cd /opt/snap
cp .env.example .env       # editar, sobretudo RUBETHYST_DOWNLOAD_TOKEN_SECRET
docker compose -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` traz `caddy-docker-proxy`, `redis` (com AOF
em volume), `api` (read-only sobre `downloads:`), `worker` e `beat`. O
Caddy descobre os serviços pelos labels e emite TLS automaticamente
para `api.rubethystlab.com` (DNS A/AAAA → IP da VM).

## 4. Anti-leech

* Worker grava o ficheiro em `/data/downloads/{job_id}/...`.
* API expõe `POST /api/v1/jobs/{id}/download-url` que assina um JWT
  HS256 com `sub=job_id`, `filename=...`, `identity=...`, `exp=now+1h`.
* O download em si chega em `GET /api/v1/jobs/{id}/file/{filename}?token=...`,
  servido por `FileResponse` sob a network do Caddy.
* **Nunca** publicar `caddy.file_server` apontando para o volume; isso
  derrubaria o gatekeeper.

## 5. Cemitério de ficheiros

`Celery Beat` roda dois scans:

* `sweep_expired_artifacts` — usa o índice de jobs no Redis para apagar
  pastas com `retention_until` vencido (intervalo padrão: 15 min).
* `sweep_download_cemetery` — scan ao volume; remove qualquer pasta
  cuja mtime mais recente seja anterior a `RUBETHYST_CEMETERY_ORPHAN_AGE_HOURS`
  (24 h) **e** que não esteja no índice. Faz limpeza intra-job de
  `.part`, `.ytdl`, `.frag` etc.

Ajuste o intervalo se aumentar o tempo de retry do Celery.

## 6. Persistência do Redis

Volume `./redis_data` montado em `/data` com `redis-server --appendonly
yes`. Em manutenção da Oracle a VM pode reiniciar; com AOF o broker, o
índice de jobs, contadores de cota e tokens ainda são reconstruídos.

Backup leve diário:

```bash
tar -C /opt/snap -czf /var/backups/snap-redis-$(date +%F).tgz redis_data
```

## 7. Monitorização barata

* `GET /api/v1/health` devolve uso de disco, ping Redis e versão do
  yt-dlp; pendurar num `uptime-kuma` externo.
* `docker stats` para CPU/RAM ao vivo.
* `df -h /var/lib/docker /opt/snap/redis_data /data/downloads` no cron
  para alerta de disco.

## 8. Atualizações

```bash
cd /opt/snap
git pull
docker compose -f docker-compose.prod.yml build --pull
docker compose -f docker-compose.prod.yml up -d
```

`yt-dlp` tem release semanal; rodar build sem cache uma vez por semana
mantém o motor compatível com mudanças nos extractors.
