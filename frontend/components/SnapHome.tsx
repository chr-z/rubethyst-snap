"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiFetch, getPublicApiBase } from "@/lib/api";
import type {
  Job,
  PlanInfo,
  PreviewResponse,
  SseProgressEvent,
} from "@/lib/types";
import { PreviewCard } from "./PreviewCard";

const ACTIVE_PLAN = "pro" as const;

type FlowState =
  | { kind: "idle" }
  | { kind: "previewing" }
  | { kind: "ready"; preview: PreviewResponse; url: string }
  | {
      kind: "downloading";
      preview: PreviewResponse;
      url: string;
      jobId: string;
      event: SseProgressEvent | null;
    }
  | {
      kind: "finished";
      preview: PreviewResponse;
      url: string;
      jobId: string;
      result: { download_url: string; filename: string };
    }
  | {
      kind: "failed";
      preview: PreviewResponse;
      url: string;
      jobId?: string;
      error: string;
    };

export function SnapHome() {
  const [urlInput, setUrlInput] = useState("");
  const [flow, setFlow] = useState<FlowState>({ kind: "idle" });
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const info = await apiFetch<PlanInfo>("/api/v1/plan", {
          headers: { "X-Plan": ACTIVE_PLAN },
        });
        if (!cancelled) setPlan(info);
      } catch {
        if (!cancelled) {
          setPlan({
            name: ACTIVE_PLAN,
            max_duration_seconds: 12 * 3600,
            max_filesize_mb: 8192,
            max_height: 2160,
            concurrency: 3,
            rate_per_hour: 120,
            retention_hours: 48,
            allowed_presets: ["smart_1080", "1080p", "720p", "best", "mp4", "audio", "mp3"],
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const closeStream = useCallback(() => {
    const es = eventSourceRef.current;
    if (es && es.readyState !== EventSource.CLOSED) {
      es.close();
    }
    eventSourceRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      closeStream();
    };
  }, [closeStream]);

  const handleAnalyze = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const url = urlInput.trim();
      if (!url) return;

      setAnalyzeError(null);
      setFlow({ kind: "previewing" });
      try {
        const preview = await apiFetch<PreviewResponse>("/api/v1/preview", {
          method: "POST",
          headers: { "X-Plan": ACTIVE_PLAN },
          body: JSON.stringify({ url }),
        });
        setFlow({ kind: "ready", preview, url });
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Não foi possível analisar o vídeo.";
        setAnalyzeError(message);
        setFlow({ kind: "idle" });
      }
    },
    [urlInput],
  );

  const startDownload = useCallback(
    async (
      preview: PreviewResponse,
      url: string,
      options?: { formatId?: string | null; preset?: string },
    ) => {
      closeStream();
      try {
        const body: Record<string, unknown> = {
          url,
          preset: options?.preset ?? "smart_1080",
        };
        if (options?.formatId) body.format_id = options.formatId;
        const job = await apiFetch<Job>("/api/v1/jobs", {
          method: "POST",
          headers: { "X-Plan": ACTIVE_PLAN },
          body: JSON.stringify(body),
        });
        setFlow({
          kind: "downloading",
          preview,
          url,
          jobId: job.id,
          event: null,
        });
        openStream(job.id, preview, url);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Falha ao criar o job.";
        setFlow({
          kind: "failed",
          preview,
          url,
          error: message,
        });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [closeStream],
  );

  const openStream = useCallback(
    (jobId: string, preview: PreviewResponse, url: string) => {
      const base = getPublicApiBase();
      const es = new EventSource(`${base}/api/v1/jobs/${jobId}/stream`, {
        withCredentials: false,
      });
      eventSourceRef.current = es;

      es.addEventListener("progress", (raw) => {
        let data: SseProgressEvent;
        try {
          data = JSON.parse((raw as MessageEvent).data);
        } catch {
          return;
        }

        if (data.status === "finished") {
          closeStream();
          void finalizeSuccess(jobId, preview, url);
          return;
        }

        if (data.status === "error") {
          closeStream();
          setFlow({
            kind: "failed",
            preview,
            url,
            jobId,
            error: data.message ?? "O download falhou.",
          });
          return;
        }

        setFlow((prev) => {
          if (prev.kind !== "downloading" || prev.jobId !== jobId) return prev;
          return { ...prev, event: data };
        });
      });

      es.addEventListener("error", () => {
        if (es.readyState === EventSource.CLOSED) {
          return;
        }
        closeStream();
        setFlow((prev) => {
          if (prev.kind !== "downloading" || prev.jobId !== jobId) return prev;
          return {
            kind: "failed",
            preview: prev.preview,
            url: prev.url,
            jobId: prev.jobId,
            error: "Conexão com o servidor interrompida.",
          };
        });
      });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [closeStream],
  );

  const finalizeSuccess = useCallback(
    async (jobId: string, preview: PreviewResponse, url: string) => {
      try {
        const job = await apiFetch<Job>(`/api/v1/jobs/${jobId}`, {
          method: "GET",
          headers: { "X-Plan": ACTIVE_PLAN },
        });
        if (!job.result) {
          setFlow({
            kind: "failed",
            preview,
            url,
            jobId,
            error: "Job concluído sem artefato.",
          });
          return;
        }
        setFlow({
          kind: "finished",
          preview,
          url,
          jobId,
          result: {
            download_url: job.result.download_url,
            filename: job.result.filename,
          },
        });
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Não foi possível recuperar o link de download.";
        setFlow({ kind: "failed", preview, url, jobId, error: message });
      }
    },
    [],
  );

  const reset = useCallback(() => {
    closeStream();
    setFlow({ kind: "idle" });
    setAnalyzeError(null);
    setUrlInput("");
  }, [closeStream]);

  const isPreviewing = flow.kind === "previewing";
  const showCard = flow.kind !== "idle" && flow.kind !== "previewing";

  return (
    <div className="flex-1 w-full flex flex-col">
      <header className="w-full border-b border-border/80">
        <div className="mx-auto max-w-5xl px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_12px_var(--color-accent)]" />
            <span className="font-semibold tracking-tight">
              Rubethyst Snap
            </span>
          </div>
          <nav className="text-sm text-muted hidden sm:flex items-center gap-6">
            <a href="#como-funciona" className="hover:text-foreground">
              Como funciona
            </a>
            <a
              href="https://github.com"
              className="hover:text-foreground"
              rel="noopener"
            >
              GitHub
            </a>
          </nav>
        </div>
      </header>

      <main className="flex-1 w-full">
        <section className="mx-auto max-w-3xl px-6 pt-20 pb-10 flex flex-col items-center text-center">
          <span className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted">
            <span className="h-px w-6 bg-border" />
            Smart 1080p, sem fricção
            <span className="h-px w-6 bg-border" />
          </span>
          <h1 className="mt-6 text-4xl sm:text-5xl font-semibold tracking-tight leading-[1.05] bg-gradient-to-b from-foreground to-foreground/70 bg-clip-text text-transparent">
            Baixe qualquer vídeo, no melhor bitrate possível.
          </h1>
          <p className="mt-5 max-w-xl text-base sm:text-lg text-muted leading-relaxed">
            Cole o link, clique em <strong className="text-foreground">Analisar</strong>{" "}
            e receba o ficheiro pronto. Sem anúncios, sem redirecionamentos,
            sem surpresas.
          </p>

          <form
            onSubmit={handleAnalyze}
            className="mt-10 w-full flex flex-col sm:flex-row gap-3"
          >
            <input
              type="url"
              required
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=…"
              className="flex-1 h-14 rounded-2xl bg-surface-strong/60 border border-border focus:border-accent focus:ring-2 focus:ring-accent/40 outline-none px-5 text-base placeholder:text-muted/70 transition"
              disabled={isPreviewing || flow.kind === "downloading"}
            />
            <button
              type="submit"
              disabled={isPreviewing || urlInput.trim().length === 0}
              className="h-14 rounded-2xl px-7 font-medium bg-accent text-white hover:bg-accent-strong disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2 shadow-[0_0_32px_-12px_var(--color-accent)]"
            >
              {isPreviewing ? <Spinner /> : null}
              {isPreviewing ? "Analisando…" : "Analisar"}
            </button>
          </form>

          {analyzeError ? (
            <p className="mt-4 text-sm text-danger">{analyzeError}</p>
          ) : null}
        </section>

        {showCard ? (
          <section className="mx-auto max-w-3xl px-6 pb-24">
            <PreviewCard
              flow={flow}
              plan={plan}
              onDownload={startDownload}
              onReset={reset}
            />
          </section>
        ) : (
          <section
            id="como-funciona"
            className="mx-auto max-w-4xl px-6 pb-24 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm"
          >
            <FeatureCard
              title="Smart 1080p"
              body="Escolhemos a stream de maior bitrate até 1080p e remuxamos em MP4."
            />
            <FeatureCard
              title="SSE em tempo real"
              body="Progresso ao vivo do yt-dlp direto do worker, sem polling."
            />
            <FeatureCard
              title="Link assinado"
              body="Download final por URL temporária; sem leech, sem abuso de banda."
            />
          </section>
        )}
      </main>

      <footer className="border-t border-border/80">
        <div className="mx-auto max-w-5xl px-6 py-6 text-sm text-muted flex flex-wrap items-center justify-between gap-4">
          <span>Rubethyst Lab · {new Date().getFullYear()}</span>
          <span>yt-dlp + ffmpeg, servido em casa.</span>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="font-medium">{title}</h3>
      <p className="mt-2 text-muted leading-relaxed">{body}</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="2.5"
        className="opacity-25"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
