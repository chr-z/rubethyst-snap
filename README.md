# Rubethyst Snap

Motor multi-plataforma de download de vídeo construído sobre
[yt-dlp](https://github.com/yt-dlp/yt-dlp) e empacotado como SaaS pela
**Rubethyst Lab**. O mesmo núcleo serve três frentes: biblioteca
Python, API HTTP (FastAPI + Celery + Redis) e cliente desktop Tkinter.

## Highlights

* **Smart 1080p** — escolhe a stream de maior bitrate cabendo na altura
  do plano (`smart_1080` preset).
* **Pré-fetch de metadados** — `POST /api/v1/preview` resolve título,
  duração e formatos sem baixar nada.
* **Anti-leech** — entrega final só por URL assinada (JWT HS256, TTL 1
  hora). Sem `file_server` público sobre `/data/downloads`.
* **Progresso em tempo real** — SSE em `/api/v1/jobs/{id}/stream`,
  alimentado por Redis Pub/Sub a partir do `progress_hook` do yt-dlp.
* **Operação sólida** — Celery + Beat com retries (`autoretry_for`,
  `retry_backoff`), cleanup TTL, cemitério de órfãos para evitar que o
  disco encha com `.part` / `.ytdl` / `.frag`.
* **Sobrevive a reboots** — Redis com AOF + volume; cotas, fila e
  estado de jobs ficam intactos depois de manutenção da VM.

## Instalação local

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api]"
copy .env.example .env
docker compose up -d                       # Redis com AOF
.\.venv\Scripts\python.exe -m rubethyst_snap.api.main
```

`ffmpeg` precisa estar disponível no `PATH`. No Windows:
`winget install Gyan.FFmpeg`.

### Docker no WSL (recomendado no Windows, sem Docker Desktop)

Corre o motor **Docker só dentro da distro** (menos RAM no Windows, sem
integração pesada do Desktop). O repositório em `D:\…` aparece no WSL em
`/mnt/d/…`.

1. **Instalar Docker Engine + Compose** (ex.: Ubuntu no WSL):

   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose-v2
   sudo usermod -aG docker "$USER"
   ```

   Em distros sem o pacote `docker-compose-v2`, instala o plugin oficial
   ([Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/))
   ou o pacote legado `docker-compose` para teres o comando `docker compose`.

   Fecha a sessão do WSL (`exit`) ou corre `newgrp docker` para o grupo
   `docker` passar a valer sem reiniciar a distro.

2. **Subir o Redis** a partir da raiz do repo (caminho de exemplo):

   ```bash
   cd /mnt/d/Rubethyst/granloader   # ajusta ao teu caminho
   ./scripts/wsl/redis-up.sh        # ou: docker compose up -d
   ```

3. **Ligar a API ao Redis**: no `.env` do Windows ou do WSL, mantém
   `RUBETHYST_REDIS_URL=redis://127.0.0.1:6379/0`. O porto `6379` exposto
   pelo Compose fica acessível em `localhost` tanto no WSL como no
   Windows (WSL2).

Podes correr a API e o worker **no Windows** (venv + `celery … --pool=solo`)
ou **tudo no WSL** (venv Python lá dentro); o browser em Windows continua a
abrir `http://localhost:3000` / `http://localhost:8000` como habitual.

### Docker Desktop no Windows (opcional)

Se preferires o Desktop em vez do Docker no WSL, vê
`scripts/windows/install-docker-desktop.ps1` e
`scripts/windows/ensure-docker-path.ps1` (detalhes no histórico do README
ou nesses ficheiros).

> O worker Celery não roda em multi-process no Windows nativo. Para
> dev local use o entrypoint (consome **snap.default** e **snap.pro**):
>
> ```powershell
> .\.venv\Scripts\python.exe -m rubethyst_snap.worker.main --pool=solo
> ```
>
> Evita `celery -A … worker` sem `--queues`, senão jobs **Pro** ficam presos
> na fila `snap.pro`.

### Frontend (Next.js)

```powershell
cd frontend
copy .env.example .env.local               # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm install
npm run dev                                # http://localhost:3000
```

O bundle do browser lê `NEXT_PUBLIC_API_BASE` em build time; para
produção, defina a variável no compose (`docker-compose.prod.yml` já
injeta via `ARG`).

Certifique-se que `RUBETHYST_CORS_ORIGINS` inclui `http://localhost:3000`
no `.env` da API — o `.env.example` já traz o default correto.

## Uso como biblioteca

```python
from rubethyst_snap import download

result = download(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_dir="./out",
    preset="smart_1080",
)
print(result.output_path, result.bytes_written)
```

Presets disponíveis: `smart_1080`, `1080p`, `720p`, `mp4`, `best`,
`audio`, `mp3`.

## Uso como SaaS

Crie um job e ouça o progresso ao vivo:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "content-type: application/json" \
  -H "X-Plan: free" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","preset":"720p"}'

curl -N http://localhost:8000/api/v1/jobs/<id>/stream
```

Quando o job termina, peça uma URL assinada e baixe:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/<id>/download-url
# {"download_url": "https://api.../api/v1/jobs/<id>/file/<name>?token=...", ...}
```

A documentação OpenAPI fica em <http://localhost:8000/docs>.

## Uso como desktop

```powershell
.\.venv\Scripts\python.exe -m rubethyst_snap.desktop.app
```

A aplicação Tkinter chama o mesmo motor — útil para testes locais e
para um cliente gratuito acoplado ao SaaS.

## Estrutura

```text
rubethyst_snap/
  core/        motor headless (yt-dlp wrapper, formatos, smart sort)
  api/         FastAPI + tokens + SSE + health
  worker/      tasks Celery + cleanup (TTL + cemitério)
  jobs/        repositório de jobs (Protocol + impl. Redis)
  quotas/      planos Free/Pro, concorrência, rate limit
  storage/     gerência do volume /data/downloads
  desktop/     cliente Tkinter
frontend/      app Next.js (App Router, Tailwind) do SaaS
docs/          arquitetura, estratégia, operações Oracle
scripts/       validate_post_live.py; windows/ e wsl/ (Docker dev)
```

Detalhes em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/STRATEGY.md](docs/STRATEGY.md) e
[docs/OPERATIONS_ORACLE.md](docs/OPERATIONS_ORACLE.md).

## Compliance

Este projeto é um motor técnico. Operá-lo como serviço pago envolve
responsabilidade legal sobre direito autoral, termos das plataformas
de origem e proteção de dados. Leia [docs/STRATEGY.md](docs/STRATEGY.md)
**antes** de habilitar cobrança.
