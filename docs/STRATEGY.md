# Estratégia comercial — Rubethyst Snap

## Posicionamento

Rubethyst Snap é o produto de download de vídeo da **Rubethyst Lab**.
Vendemos um motor multi-plataforma (yt-dlp + ffmpeg) entregue como SaaS
com SLA, controle de banda e UX moderna. O diferencial é técnico
(velocidade, smart 1080p, suporte a pós-live de YouTube) e operacional
(custos previsíveis, anti-leech, retenção curta).

## Planos

| Plano | Preço | Duração máx. | Resolução máx. | Concorrência | Retenção |
|-------|-------|--------------|----------------|--------------|----------|
| Free  | 0     | 15 min       | 720p           | 1            | 6 h      |
| Pro   | $9/mês| 12 h         | 1080p smart    | 3            | 48 h     |
| API   | sob consulta | 12 h | 4K             | 10+          | 7 d      |

* Free: rate limit `RUBETHYST_FREE_RATE_PER_HOUR` (default 10/hora),
  presets `720p`, `audio`, `mp3`. Marca d'água do produto na UI.
* Pro: presets `smart_1080`, `1080p`, `mp4`, `audio`, `mp3`. Sem
  branding, com histórico de jobs e download-url renovável.
* API: contrato direto, quotas próprias, faturação por job concluído
  + GB egress.

## Métricas de billing

* Tempo de download bem-sucedido (proxy de CPU+IO).
* Bytes egress consumidos pelo signed URL (rate-limit por plano).
* Número de jobs/dia (rate per hour é hard-cap).

## Compliance e operação

* Termos das plataformas (YouTube, Twitch, etc.) proíbem certos usos;
  Rubethyst Snap é um motor — a responsabilidade é do cliente. Manter
  ToS explícito, opt-in para conteúdo de terceiros, política DMCA.
* LGPD/GDPR: signed URLs com TTL curto (1 h), retenção curta no plano
  Free, deleção determinística pelo cemitério do Beat.
* Logs nunca contêm IPs em claro: identidade derivada por hash
  (`ip:` ou `key:`). Tokens JWT não persistem além do `exp`.

## Anti-abuso

* Tokens JWT curtos (1 h default) em vez de URLs públicas estáticas.
* Concurrency hard-cap por identidade (`snap:inflight:{identity}`).
* Rate-limit fixed-window no Redis (`snap:rate:{identity}:{hour}`).
* Cemitério remove órfãos > 24 h, garantindo que abuso de uploads
  parciais não enche os 200 GB da VM Oracle.
* Health check pública (`/healthz`) sem detalhes; detalhes só em
  `/api/v1/health` (atrás de auth no futuro).

## Roadmap mínimo de produção

1. Produto: Free + Pro com checkout (Stripe ou Lemon Squeezy).
2. Painel Next.js (somente API key, sem DB próprio no MVP).
3. Auditoria persistente: trocar `RedisJobRepository` por implementação
   SQLite/PostgreSQL para histórico além da retenção.
4. Métricas: Prometheus + Grafana free tier.
5. Faturação variável (egress GB) só após validar margem com flat-rate.

## Custos esperados (MVP)

* Oracle Always Free: $0 enquanto se mantiver dentro de 4 OCPU, 24 GB
  RAM, 200 GB disco e 10 TB egress.
* DNS: $0 com Cloudflare Free.
* Stripe: ~3% por transação.
* Domínio: ~$15/ano.

Custo marginal por job tende a zero enquanto cabermos no Always Free.
A primeira despesa real vai aparecer quando ultrapassarmos egress;
nesse ponto, mover assets para Cloudflare R2 (10 GB grátis, $0.015/GB
acima) com URL assinada continua barato.
