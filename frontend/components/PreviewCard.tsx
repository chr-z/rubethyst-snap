"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import type {
  PlanInfo,
  PreviewResponse,
  ProgressStatus,
  SseProgressEvent,
} from "@/lib/types";
import { formatBytes, formatDuration, formatEta } from "@/lib/format";
import {
  formatLabel,
  selectAudioFormats,
  selectVideoFormats,
  type VideoFormatOption,
} from "@/lib/formats";

type Flow =
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

interface Props {
  flow: Flow;
  plan: PlanInfo | null;
  onDownload: (
    preview: PreviewResponse,
    url: string,
    options?: { formatId?: string | null; preset?: string },
  ) => void;
  onReset: () => void;
}

const AUTO_VALUE = "__auto__";
const AUDIO_ONLY_VALUE = "__audio__";

export function PreviewCard({ flow, plan, onDownload, onReset }: Props) {
  const preview = flow.preview;
  const isDownloading = flow.kind === "downloading";
  const isFinished = flow.kind === "finished";
  const isFailed = flow.kind === "failed";

  const maxHeight = plan?.max_height ?? 1080;

  const videoOptions = useMemo(
    () => selectVideoFormats(preview.formats, maxHeight),
    [preview.formats, maxHeight],
  );
  const audioOptions = useMemo(
    () => selectAudioFormats(preview.formats),
    [preview.formats],
  );

  return (
    <article className="overflow-hidden rounded-3xl border border-border bg-surface shadow-[0_24px_64px_-32px_rgba(139,92,246,0.35)]">
      <div className="flex flex-col sm:flex-row">
        <div className="relative w-full sm:w-72 aspect-video sm:aspect-auto bg-background">
          {preview.thumbnail ? (
            <Image
              src={preview.thumbnail}
              alt={preview.title}
              fill
              sizes="(max-width: 640px) 100vw, 288px"
              className="object-cover"
              unoptimized
              priority
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-muted text-sm">
              sem thumbnail
            </div>
          )}
          <div className="absolute bottom-2 right-2 rounded-md bg-black/70 px-2 py-0.5 text-xs font-mono">
            {formatDuration(preview.duration_seconds)}
          </div>
        </div>

        <div className="flex-1 p-6 flex flex-col gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.15em] text-muted">
              {preview.extractor}
              {preview.uploader ? ` · ${preview.uploader}` : ""}
              {plan ? (
                <span className="ml-2 text-accent-strong">
                  plano {plan.name} · até {plan.max_height}p
                </span>
              ) : null}
            </p>
            <h2 className="mt-2 text-xl font-semibold leading-tight line-clamp-2">
              {preview.title}
            </h2>
          </div>

          {flow.kind === "ready" ? (
            <ReadyBlock
              preview={flow.preview}
              url={flow.url}
              videoOptions={videoOptions}
              audioOptions={audioOptions}
              plan={plan}
              onDownload={onDownload}
              onReset={onReset}
            />
          ) : null}

          {isDownloading ? <ProgressBlock event={flow.event} /> : null}

          {isFinished ? (
            <FinishedBlock
              downloadUrl={flow.result.download_url}
              filename={flow.result.filename}
              onReset={onReset}
            />
          ) : null}

          {isFailed ? <FailedBlock error={flow.error} onReset={onReset} /> : null}
        </div>
      </div>
    </article>
  );
}

function ReadyBlock({
  preview,
  url,
  videoOptions,
  audioOptions,
  plan,
  onDownload,
  onReset,
}: {
  preview: PreviewResponse;
  url: string;
  videoOptions: VideoFormatOption[];
  audioOptions: ReturnType<typeof selectAudioFormats>;
  plan: PlanInfo | null;
  onDownload: Props["onDownload"];
  onReset: () => void;
}) {
  const hasVideo = videoOptions.length > 0;
  const hasAudio = audioOptions.length > 0;
  const allowAudioPreset = plan ? plan.allowed_presets.includes("mp3") : true;

  const [selected, setSelected] = useState<string>(AUTO_VALUE);

  const handleDownload = () => {
    if (selected === AUTO_VALUE) {
      onDownload(preview, url, { preset: "smart_1080" });
      return;
    }
    if (selected === AUDIO_ONLY_VALUE) {
      const preset = allowAudioPreset ? "mp3" : "audio";
      onDownload(preview, url, { preset });
      return;
    }
    onDownload(preview, url, { formatId: selected, preset: "smart_1080" });
  };

  const topHeight = videoOptions[0]?.height ?? 0;
  const smartHint =
    topHeight >= 1080
      ? "Smart 1080p"
      : topHeight > 0
        ? `Smart (auto · até ${topHeight}p)`
        : "Smart";

  return (
    <div className="mt-auto flex flex-col gap-3">
      {hasVideo || hasAudio ? (
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-[0.12em] text-muted">
            Qualidade
          </label>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="h-11 rounded-xl bg-surface-strong border border-border px-3 text-sm focus:border-accent focus:ring-2 focus:ring-accent/40 outline-none"
          >
            <option value={AUTO_VALUE}>{smartHint} (recomendado)</option>
            {videoOptions.length > 0 ? (
              <optgroup label="Vídeo">
                {videoOptions.map((opt) => (
                  <option key={opt.entry.format_id} value={opt.entry.format_id}>
                    {formatLabel(opt)}
                    {opt.filesize
                      ? ` · ${formatBytes(opt.filesize)}`
                      : ""}
                    {opt.isAdaptive ? "" : " · muxed"}
                  </option>
                ))}
              </optgroup>
            ) : null}
            {hasAudio ? (
              <option value={AUDIO_ONLY_VALUE}>
                Só áudio ({allowAudioPreset ? "MP3 192 kbps" : "formato original"})
              </option>
            ) : null}
          </select>
          {!hasVideo ? (
            <p className="text-xs text-muted">
              Sem streams de vídeo adaptativos dentro do limite do plano —
              Smart usará a melhor opção disponível.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-col sm:flex-row gap-2">
        <button
          onClick={handleDownload}
          className="h-12 flex-1 rounded-xl px-5 font-medium bg-accent text-white hover:bg-accent-strong transition flex items-center justify-center gap-2"
        >
          Baixar
        </button>
        <button
          onClick={onReset}
          className="h-12 rounded-xl px-5 font-medium bg-surface-strong text-muted hover:text-foreground border border-border transition"
        >
          Analisar outro
        </button>
      </div>
    </div>
  );
}

function ProgressBlock({ event }: { event: SseProgressEvent | null }) {
  const status = event?.status ?? "queued";
  const percent: number | null = event?.percent ?? null;
  const downloaded = event?.downloaded_bytes;
  const total = event?.total_bytes;
  const eta = formatEta(event?.eta_seconds);

  return (
    <div className="mt-auto flex flex-col gap-3">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-muted">
          <span className="h-2 w-2 rounded-full bg-accent snap-pulse" />
          {statusLabel(status)}
        </span>
        <span className="font-mono tabular-nums text-muted">
          {percent == null ? "…" : `${percent.toFixed(1)}%`}
        </span>
      </div>

      <div className="relative h-2 w-full overflow-hidden rounded-full bg-surface-strong">
        {percent == null ? (
          <div className="absolute inset-y-0 left-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-accent to-transparent snap-indeterminate-bar" />
        ) : (
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300"
            style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
          />
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted font-mono">
        <span>
          {downloaded != null && total != null
            ? `${formatBytes(downloaded)} / ${formatBytes(total)}`
            : downloaded != null
              ? formatBytes(downloaded)
              : ""}
        </span>
        {eta ? <span>ETA {eta}</span> : null}
      </div>
    </div>
  );
}

function FinishedBlock({
  downloadUrl,
  filename,
  onReset,
}: {
  downloadUrl: string;
  filename: string;
  onReset: () => void;
}) {
  return (
    <div className="mt-auto flex flex-col gap-3">
      <div className="flex items-center gap-2 text-sm text-accent-strong">
        <CheckIcon />
        <span>Pronto: {filename}</span>
      </div>
      <div className="flex flex-col sm:flex-row gap-2">
        <a
          href={downloadUrl}
          download={filename}
          target="_blank"
          rel="noopener"
          className="h-12 rounded-xl px-5 font-medium bg-accent text-white hover:bg-accent-strong transition flex items-center justify-center gap-2"
        >
          Salvar ficheiro
        </a>
        <button
          onClick={onReset}
          className="h-12 rounded-xl px-5 font-medium bg-surface-strong text-muted hover:text-foreground border border-border transition"
        >
          Analisar outro
        </button>
      </div>
      <p className="text-xs text-muted">
        O link é assinado e expira em ~1 hora. Não é compartilhável publicamente.
      </p>
    </div>
  );
}

function FailedBlock({ error, onReset }: { error: string; onReset: () => void }) {
  return (
    <div className="mt-auto flex flex-col gap-3">
      <div className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
        {error}
      </div>
      <button
        onClick={onReset}
        className="h-12 rounded-xl px-5 font-medium bg-surface-strong text-foreground hover:bg-border border border-border transition"
      >
        Tentar de novo
      </button>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden
    >
      <path
        d="m5 10 3.5 3.5L15 6.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function statusLabel(status: ProgressStatus): string {
  switch (status) {
    case "queued":
      return "Na fila";
    case "extracting":
      return "Analisando metadados";
    case "downloading":
      return "Baixando";
    case "merging":
      return "Mesclando áudio e vídeo";
    case "postprocessing":
      return "Pós-processando";
    case "uploading":
      return "Publicando";
    case "finished":
      return "Concluído";
    case "error":
      return "Erro";
    case "retrying":
      return "Tentando novamente";
    default:
      return status;
  }
}
