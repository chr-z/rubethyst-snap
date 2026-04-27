import type { FormatEntry } from "./types";

export interface VideoFormatOption {
  entry: FormatEntry;
  height: number;
  fps: number | null;
  tbrKbps: number | null;
  vcodec: string | null;
  ext: string | null;
  filesize: number | null;
  isAdaptive: boolean;
}

export interface AudioFormatOption {
  entry: FormatEntry;
  abrKbps: number | null;
  acodec: string | null;
  ext: string | null;
  filesize: number | null;
}

const IGNORED_VCODECS = new Set(["none", "", null, undefined]);
const IGNORED_ACODECS = new Set(["none", "", null, undefined]);

function hasVideo(f: FormatEntry): boolean {
  return !IGNORED_VCODECS.has(f.vcodec as string | null | undefined);
}

function hasAudio(f: FormatEntry): boolean {
  return !IGNORED_ACODECS.has(f.acodec as string | null | undefined);
}

export function selectVideoFormats(
  formats: FormatEntry[],
  maxHeight: number,
): VideoFormatOption[] {
  const candidates: VideoFormatOption[] = [];
  const bestPerBucket = new Map<string, VideoFormatOption>();

  for (const f of formats) {
    if (!hasVideo(f)) continue;
    const height = f.height ?? 0;
    if (!height || height > maxHeight) continue;

    const fps = f.fps ?? null;
    const tbr = pickBitrateKbps(f);
    const opt: VideoFormatOption = {
      entry: f,
      height,
      fps,
      tbrKbps: tbr,
      vcodec: simpleCodec(f.vcodec),
      ext: f.ext,
      filesize: f.filesize,
      isAdaptive: !hasAudio(f),
    };

    const bucket = `${height}@${Math.round(fps ?? 30)}`;
    const prev = bestPerBucket.get(bucket);
    if (!prev || (tbr ?? 0) > (prev.tbrKbps ?? 0)) {
      bestPerBucket.set(bucket, opt);
    }
    candidates.push(opt);
  }

  const best = Array.from(bestPerBucket.values());
  best.sort((a, b) => {
    if (b.height !== a.height) return b.height - a.height;
    const fa = Math.round(a.fps ?? 0);
    const fb = Math.round(b.fps ?? 0);
    if (fb !== fa) return fb - fa;
    return (b.tbrKbps ?? 0) - (a.tbrKbps ?? 0);
  });
  return best;
}

export function selectAudioFormats(formats: FormatEntry[]): AudioFormatOption[] {
  const out: AudioFormatOption[] = [];
  for (const f of formats) {
    if (hasVideo(f)) continue;
    if (!hasAudio(f)) continue;
    out.push({
      entry: f,
      abrKbps: pickBitrateKbps(f),
      acodec: simpleCodec(f.acodec),
      ext: f.ext,
      filesize: f.filesize,
    });
  }
  out.sort((a, b) => (b.abrKbps ?? 0) - (a.abrKbps ?? 0));
  return out;
}

export function pickBitrateKbps(f: FormatEntry): number | null {
  const tbr = f.tbr;
  if (tbr != null && Number.isFinite(tbr) && tbr > 0) return Math.round(tbr);
  const vbr = f.vbr ?? 0;
  const abr = f.abr ?? 0;
  const total = vbr + abr;
  if (total > 0) return Math.round(total);
  return null;
}

function simpleCodec(codec: string | null): string | null {
  if (!codec) return null;
  const main = codec.split(".")[0]?.toLowerCase() ?? codec;
  if (main.startsWith("avc")) return "h264";
  if (main.startsWith("hev") || main.startsWith("hvc")) return "h265";
  return main;
}

export function formatLabel(opt: VideoFormatOption): string {
  const height = `${opt.height}p`;
  const fps = opt.fps && opt.fps > 30 ? `${Math.round(opt.fps)}` : null;
  const tbr = opt.tbrKbps ? `${opt.tbrKbps.toLocaleString("pt-BR")} kbps` : null;
  const codec = opt.vcodec ? opt.vcodec.toUpperCase() : null;
  const parts = [height + (fps ? fps : ""), codec, tbr].filter(Boolean);
  return parts.join(" · ");
}
