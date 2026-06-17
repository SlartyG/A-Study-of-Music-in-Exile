#!/usr/bin/env python3
"""
Export web-ready JSON files from analysis CSVs.
Usage: python3 analysis/export_for_web.py
Outputs: web/public/data/*.json
"""
from __future__ import annotations
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
ANALYSIS = ROOT / "analysis" / "output"
DATA_DIR = ROOT / "data"
OUT = ROOT / "web" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)

# ── Human topic names ─────────────────────────────────────────────────────────
TOPIC_NAMES = {
    0: "Диалог и близость",
    1: "Повседневность",
    2: "Любовь и желание",
    3: "Мир и конец",
    4: "Рэп-стиль",
    5: "Тупик",
    6: "Улица и политика",
    7: "Деньги и жизнь",
    8: "Семья и люди",
    9: "Слово и тело",
}

# Stage-name overrides for display in artist cards
DISPLAY_NAMES = {
    "Шура Би-2": "Би-2",
    "Анастасия Креслина": "IC3PEAK",
    "Кирилл Иванов": "СБПЧ",
    "Айгель Гайсина": "Айгель",
    "Виктор Ужаков": "Ploho",
    "Вера Мусаелян": "АлоэВера",
    "Лу (Louna)": "Лу / Louna",
}

RU_MONTHS = {
    1: "ЯНВ", 2: "ФЕВ", 3: "МАР", 4: "АПР",
    5: "МАЙ", 6: "ИЮН", 7: "ИЮЛ", 8: "АВГ",
    9: "СЕН", 10: "ОКТ", 11: "НОЯ", 12: "ДЕК",
}


def fmt_date(d: str) -> str:
    """'2022-03-01' → 'МАР 2022'"""
    try:
        import datetime
        dt = datetime.date.fromisoformat(str(d)[:10])
        return f"{RU_MONTHS[dt.month]} {dt.year}"
    except Exception:
        return str(d)[:7]


def safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    except Exception:
        return None


def to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def sem(series: pd.Series) -> float:
    vals = series.dropna()
    n = len(vals)
    if n < 2:
        return 0.0
    return float(vals.std(ddof=1) / math.sqrt(n))


# ── Load source data ──────────────────────────────────────────────────────────
print("Loading source data...")
musicians = pd.read_csv(DATA_DIR / "sample_musicians.csv")
lex = pd.read_csv(ANALYSIS / "final_per_artist_lex.csv")
bert = pd.read_csv(ANALYSIS / "final_per_artist_bert.csv")
scores = pd.read_csv(ANALYSIS / "sentiment_scores.csv", parse_dates=["release_date"])
topic_scores = pd.read_csv(ANALYSIS / "topic_scores.csv", parse_dates=["release_date"])
topic_prev = pd.read_csv(ANALYSIS / "topic_prevalence.csv")

# Fix boolean columns
for df in [lex, bert]:
    df["has_ops"] = df["has_ops"].apply(to_bool)
    df["significant"] = df["significant"].apply(to_bool)

# Parse topic top words from txt
topic_words: dict[int, list[str]] = {}
current_topic: int | None = None
with open(ANALYSIS / "topic_top_words.txt", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if line.startswith("Тема"):
            num = int(line.split(":")[0].replace("Тема", "").strip()) - 1
            current_topic = num
        elif line.strip() and current_topic is not None and not line.startswith("Тема"):
            words = [w.strip() for w in line.strip().split(",")]
            topic_words[current_topic] = words

# ── Build balanced track set ──────────────────────────────────────────────────
print("Building balanced track set...")
balanced_ids: set = set()
for _, row in lex.iterrows():
    pseudonym = row["pseudonym"]
    n_bal = int(row["n_before"])
    artist_scores = scores[scores["pseudonym"] == pseudonym].copy()
    for period in ("before", "after"):
        period_tracks = (
            artist_scores[artist_scores["period"] == period]
            .sort_values("release_date", ascending=False)
            .head(n_bal)
        )
        balanced_ids.update(period_tracks["song_id"].tolist())

scores_bal = scores[scores["song_id"].isin(balanced_ids)].copy()
topic_bal = topic_scores[topic_scores["song_id"].isin(balanced_ids)].copy()

# ── 1. corpus_summary.json ────────────────────────────────────────────────────
summary = {
    "artists": int(len(lex)),
    "tracks": int(len(scores_bal)),
    "period": "2022–2026",
}
(OUT / "corpus_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"  corpus_summary.json: {summary['artists']} artists, {summary['tracks']} tracks")

# ── 2. artists_meta.json ──────────────────────────────────────────────────────
mus_lookup: dict[str, pd.Series] = {
    row["псевдоним"]: row
    for _, row in musicians.iterrows()
}

merged = lex.merge(bert, on="pseudonym", suffixes=("_lex", "_bert"))
topic_cols = [f"topic_{i}" for i in range(10)]

artists_meta = []
for _, row in merged.iterrows():
    pseudo = row["pseudonym"]
    m = mus_lookup.get(pseudo, pd.Series(dtype=object))

    def top3(period: str) -> list[dict]:
        subset = topic_bal[
            (topic_bal["pseudonym"] == pseudo) & (topic_bal["period"] == period)
        ][topic_cols]
        if subset.empty:
            return []
        means = subset.mean()
        return [
            {
                "topic_id": int(c.split("_")[1]),
                "name": TOPIC_NAMES[int(c.split("_")[1])],
                "share": round(float(v), 4),
            }
            for c, v in means.nlargest(3).items()
        ]

    reloc_raw = str(m.get("дата_релокации", ""))[:10] if not m.empty else ""

    entry = {
        "pseudonym": pseudo,
        "display_name": DISPLAY_NAMES.get(pseudo, pseudo),
        "real_name": str(m.get("реальное_имя", pseudo)) if not m.empty else pseudo,
        "group": str(m.get("основная_группа", "")) if not m.empty else "",
        "country": str(m.get("страна_релокации", "")) if not m.empty else "",
        "city": str(m.get("город_релокации", "")) if not m.empty else "",
        "reloc_date": fmt_date(reloc_raw) if reloc_raw else "",
        "has_ops": bool(row["has_ops_lex"]),
        "ops_label": "ИНОСТРАННЫЙ АГЕНТ" if bool(row["has_ops_lex"]) else None,
        "n": int(row["n_before_lex"]),
        "lex": {
            "mean_before": safe_float(row["mean_before_lex"]),
            "mean_after": safe_float(row["mean_after_lex"]),
            "delta": safe_float(row["delta_lex"]),
            "d": safe_float(row["cohens_d_lex"]),
            "p": safe_float(row["p_value_lex"]),
            "significant": bool(row["significant_lex"]),
        },
        "bert": {
            "mean_before": safe_float(row["mean_before_bert"]),
            "mean_after": safe_float(row["mean_after_bert"]),
            "delta": safe_float(row["delta_bert"]),
            "d": safe_float(row["cohens_d_bert"]),
            "p": safe_float(row["p_value_bert"]),
            "significant": bool(row["significant_bert"]),
        },
        "top3_before": top3("before"),
        "top3_after": top3("after"),
    }
    artists_meta.append(entry)

(OUT / "artists_meta.json").write_text(
    json.dumps(artists_meta, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"  artists_meta.json: {len(artists_meta)} artists")

# ── 3. sentiment_tracks.json ──────────────────────────────────────────────────
track_records = [
    {
        "pseudonym": str(row["pseudonym"]),
        "period": str(row["period"]),
        "year": int(str(row["release_date"])[:4]),
        "sentiment_ratio": round(float(row["sentiment_ratio"]), 6),
    }
    for _, row in scores_bal.iterrows()
]
(OUT / "sentiment_tracks.json").write_text(
    json.dumps(track_records, ensure_ascii=False), encoding="utf-8"
)
print(f"  sentiment_tracks.json: {len(track_records)} tracks")

# ── 4. timeline.json ──────────────────────────────────────────────────────────
scores_yr = scores.copy()
scores_yr["year"] = scores_yr["release_date"].dt.year

timeline_records = []
for year in sorted(scores_yr["year"].dropna().unique()):
    year = int(year)
    subset = scores_yr[scores_yr["year"] == year]["sentiment_ratio"].dropna()
    if len(subset) < 3:
        continue
    timeline_records.append({
        "year": year,
        "period_cal": "before" if year < 2022 else "after",
        "mean_lex": round(float(subset.mean()), 6),
        "sem_lex": round(sem(subset), 6),
        "n": int(len(subset)),
    })

(OUT / "timeline.json").write_text(
    json.dumps(timeline_records, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"  timeline.json: {len(timeline_records)} years")

# ── 5. topics.json ────────────────────────────────────────────────────────────
topic_records = []
for _, row in topic_prev.iterrows():
    topic_id = int(str(row["topic"]).replace("topic_", ""))
    topic_records.append({
        "topic_id": topic_id,
        "name": TOPIC_NAMES.get(topic_id, f"Тема {topic_id + 1}"),
        "top_words": topic_words.get(topic_id, []),
        "share_before": round(float(row["mean_before"]), 6),
        "share_after": round(float(row["mean_after"]), 6),
        "delta": round(float(row["delta"]), 6),
    })

topic_records.sort(key=lambda x: x["delta"], reverse=True)

(OUT / "topics.json").write_text(
    json.dumps(topic_records, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"  topics.json: {len(topic_records)} topics")

print(f"\nAll files written to {OUT}")
