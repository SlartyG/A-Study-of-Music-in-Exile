import fs from "fs";
import path from "path";

const DATA = path.join(process.cwd(), "public/data");

function readJson<T>(filename: string): T {
  const raw = fs.readFileSync(path.join(DATA, filename), "utf-8");
  return JSON.parse(raw) as T;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CorpusSummary {
  artists: number;
  tracks: number;
  period: string;
}

export interface TopicRef {
  topic_id: number;
  name: string;
  share: number;
}

export interface MethodStats {
  mean_before: number | null;
  mean_after: number | null;
  delta: number | null;
  d: number | null;
  p: number | null;
  significant: boolean;
}

export interface ArtistMeta {
  pseudonym: string;
  display_name: string;
  real_name: string;
  photo?: string;
  group: string;
  country: string;
  city: string;
  reloc_date: string;
  has_ops: boolean;
  ops_label: string | null;
  n: number;
  lex: MethodStats;
  bert: MethodStats;
  top3_before: TopicRef[];
  top3_after: TopicRef[];
}

export interface SentimentTrack {
  pseudonym: string;
  period: "before" | "after";
  year: number;
  sentiment_ratio: number;
}

export interface TimelinePoint {
  year: number;
  period_cal: "before" | "after";
  mean_lex: number;
  sem_lex: number;
  n: number;
}

export interface Topic {
  topic_id: number;
  name: string;
  top_words: string[];
  share_before: number;
  share_after: number;
  delta: number;
}

// ── Loaders ───────────────────────────────────────────────────────────────────

export function loadCorpusSummary(): CorpusSummary {
  return readJson("corpus_summary.json");
}

export function loadArtists(): ArtistMeta[] {
  return readJson("artists_meta.json");
}

export function loadTracks(): SentimentTrack[] {
  return readJson("sentiment_tracks.json");
}

export function loadTimeline(): TimelinePoint[] {
  return readJson("timeline.json");
}

export function loadTopics(): Topic[] {
  return readJson("topics.json");
}

export function loadAllData() {
  return {
    corpus: loadCorpusSummary(),
    artists: loadArtists(),
    tracks: loadTracks(),
    timeline: loadTimeline(),
    topics: loadTopics(),
  };
}
