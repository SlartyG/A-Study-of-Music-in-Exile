#!/usr/bin/env python3
"""
Метод 3: Тональность через трансформерные модели (ruBERT).

Алгоритм:
  1. Загрузить тексты треков (те же фильтры, что в методах 1–2).
  2. Очистить тексты.
  3. Разбить длинные тексты на чанки ≤ MAX_TOKENS токенов.
  4. Прогнать через предобученную модель rubert-tiny2-russian-sentiment.
  5. Агрегировать скоры по чанкам трека (взвешенное среднее).
  6. Сравнить периоды «до» и «после» на сбалансированной выборке.
  7. Сопоставить с результатами метода 1 (корреляция).
  8. Визуализировать (9 графиков).

Модель: seara/rubert-tiny2-russian-sentiment
  Метки:  positive (1), neutral (0), negative (-1)
  Размер: ~28 MB — скачивается автоматически при первом запуске.

Запуск:
    python3 analysis/transformer_sentiment.py
"""

import csv
import json
import re
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from scipy import stats
from transformers import pipeline

from timeline import build_timeline_series

# ── Пути ────────────────────────────────────────────────────────────────────

BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_DIR       = BASE_DIR / "data"
SONGS_FILE     = DATA_DIR / "songs.jsonl"
MUSICIANS_FILE = DATA_DIR / "sample_musicians.csv"
OUT_DIR        = BASE_DIR / "analysis" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# CSV метода 1 (если существует — для корреляционного анализа)
LEXICAL_CSV = OUT_DIR / "sentiment_scores.csv"

# ── Параметры ────────────────────────────────────────────────────────────────

MODEL_NAME  = "seara/rubert-tiny2-russian-sentiment"
BATCH_SIZE  = 64          # треков за один forward pass
MAX_TOKENS  = 512         # лимит токенов модели
CHUNK_WORDS = 150         # слов в одном чанке (~ 200 токенов)
MIN_WORDS   = 20          # минимум слов в треке

# Маппинг меток модели → числовой скор
LABEL_SCORE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

# ── Устройство ───────────────────────────────────────────────────────────────

def get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ── Очистка текста ───────────────────────────────────────────────────────────

_SECTION_RE = re.compile(r"\[.*?\]")
_CONTRIB_RE = re.compile(r"^\d+\s+Contributors?\s*.+?Lyrics\s*", re.DOTALL)


def clean_lyrics(text: str) -> str:
    text = _CONTRIB_RE.sub("", text, count=1)
    text = _SECTION_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_into_chunks(text: str, chunk_words: int = CHUNK_WORDS) -> list[str]:
    """Разбить текст на чанки по N слов с небольшим перекрытием."""
    words = text.split()
    if len(words) < MIN_WORDS:
        return []
    if len(words) <= chunk_words:
        return [text]
    step    = max(1, chunk_words - 20)   # перекрытие 20 слов
    chunks  = []
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_words])
        if len(chunk.split()) >= MIN_WORDS:
            chunks.append(chunk)
    return chunks or [text]


# ── Загрузка данных ──────────────────────────────────────────────────────────

def load_musicians() -> dict[int, dict]:
    result: dict[int, dict] = {}
    with open(MUSICIANS_FILE, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("genius_ok", "").strip().upper() != "TRUE":
                continue
            gid = int(row["genius_id"])
            result[gid] = {
                "pseudonym":    row["псевдоним"],
                "country":      row["страна_релокации"],
                "legal_status": row["правовой_статус"],
            }
    return result


def load_songs(valid_ids: set[int]) -> list[dict]:
    songs = []
    with open(SONGS_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                s = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not s.get("has_lyrics"):
                continue
            if s.get("artist_genius_id") not in valid_ids:
                continue
            if s.get("period") not in ("before", "after"):
                continue
            songs.append(s)
    return songs


# ── Инференс ─────────────────────────────────────────────────────────────────

def build_pipeline(device: str):
    """Загрузить pipeline трансформера."""
    print(f"  Загружаю модель {MODEL_NAME} на устройстве «{device}» …")
    return pipeline(
        "text-classification",
        model=MODEL_NAME,
        device=device,
        truncation=True,
        max_length=MAX_TOKENS,
    )


def score_chunk(result: dict) -> tuple[float, float, float]:
    """
    Из вывода pipeline → (compound, pos_prob, neg_prob).
    Для модели с top_k=None возвращает все три вероятности.
    """
    label = result["label"]
    score = result["score"]
    # Приближение: вероятность предсказанного класса; остальное делим поровну
    other = (1 - score) / 2
    if label == "positive":
        pos, neu, neg = score, other, other
    elif label == "negative":
        pos, neu, neg = other, other, score
    else:
        pos, neu, neg = other, score, other
    compound = pos - neg
    return compound, pos, neg


def run_inference(pipe, songs: list[dict]) -> list[dict | None]:
    """
    Прогнать все треки через модель.
    Длинные тексты разбиваются на чанки; результат усредняется.
    Возвращает список скоров (или None для треков без текста).
    """
    # Подготовить чанки
    song_chunks: list[list[str]] = []
    for s in songs:
        text   = clean_lyrics(s.get("lyrics", ""))
        chunks = split_into_chunks(text)
        song_chunks.append(chunks)

    # Построить плоский список всех чанков с индексом трека
    flat_chunks  = []
    flat_indices = []
    for i, chunks in enumerate(song_chunks):
        for c in chunks:
            flat_chunks.append(c)
            flat_indices.append(i)

    if not flat_chunks:
        return [None] * len(songs)

    # Батчевый инференс
    print(f"  Инференс: {len(flat_chunks):,} чанков из {len(songs):,} треков …")
    raw_results: list[dict] = []
    t0 = time.time()
    for start in range(0, len(flat_chunks), BATCH_SIZE):
        batch = flat_chunks[start : start + BATCH_SIZE]
        raw_results.extend(pipe(batch))
        done = min(start + BATCH_SIZE, len(flat_chunks))
        elapsed = time.time() - t0
        eta = elapsed / done * (len(flat_chunks) - done) if done else 0
        print(f"\r    {done:,}/{len(flat_chunks):,}  ETA {eta:.0f}s   ", end="", flush=True)
    print()

    # Агрегировать по трекам (среднее по чанкам)
    from collections import defaultdict
    song_scores: dict[int, list[tuple]] = defaultdict(list)
    for idx, res in zip(flat_indices, raw_results):
        compound, pos, neg = score_chunk(res)
        song_scores[idx].append((compound, pos, neg))

    scores = []
    for i in range(len(songs)):
        if not song_scores[i]:
            scores.append(None)
            continue
        arr = np.array(song_scores[i])  # shape (n_chunks, 3)
        scores.append({
            "compound":  float(arr[:, 0].mean()),
            "pos_prob":  float(arr[:, 1].mean()),
            "neg_prob":  float(arr[:, 2].mean()),
            "n_chunks":  len(song_scores[i]),
        })
    return scores


# ── Построение DataFrame ──────────────────────────────────────────────────────

def build_df(songs: list[dict], musicians: dict[int, dict],
             scores: list[dict | None]) -> pd.DataFrame:
    rows = []
    for s, score in zip(songs, scores):
        if score is None:
            continue
        rdc   = s.get("release_date_components") or {}
        year  = rdc.get("year")
        month = rdc.get("month") or 1
        day   = rdc.get("day") or 1
        rel_date = f"{year}-{int(month):02d}-{int(day):02d}" if year else None
        gid  = s["artist_genius_id"]
        info = musicians[gid]
        rows.append({
            "song_id":          s["song_id"],
            "title":            s["title"],
            "artist_genius_id": gid,
            "pseudonym":        info["pseudonym"],
            "country":          info["country"],
            "legal_status":     info["legal_status"],
            "period":           s["period"],
            "release_date":     rel_date,
            **score,
        })
    df = pd.DataFrame(rows)
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    return df


# ── Балансировка ─────────────────────────────────────────────────────────────

def balance_periods(df: pd.DataFrame) -> pd.DataFrame:
    """Равное N треков в обоих периодах (N самых новых из каждого)."""
    parts = []
    for _, grp in df.groupby("artist_genius_id"):
        after  = grp[grp["period"] == "after"].sort_values("release_date", ascending=False)
        before = grp[grp["period"] == "before"].sort_values("release_date", ascending=False)
        n = min(len(after), len(before))
        if n == 0:
            continue
        parts.extend([after.head(n), before.head(n)])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# ── Статистика ────────────────────────────────────────────────────────────────

PRIMARY = "compound"

def mw_test(a: np.ndarray, b: np.ndarray) -> dict:
    if len(a) < 3 or len(b) < 3:
        return {"u": None, "p": None, "sig": None}
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"u": u, "p": p, "sig": p < 0.05}


def cohens_d(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    s = np.sqrt((np.std(a, ddof=1) ** 2 + np.std(b, ddof=1) ** 2) / 2)
    return float((np.mean(b) - np.mean(a)) / s) if s else 0.0


def _sig_stars(p: float | None) -> str:
    if p is None:
        return ""
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "n.s."


def compute_results(df: pd.DataFrame, label: str) -> dict:
    bef = df[df["period"] == "before"][PRIMARY].dropna().values
    aft = df[df["period"] == "after"][PRIMARY].dropna().values
    test = mw_test(bef, aft)
    overall = {
        "n_before":      len(bef),
        "n_after":       len(aft),
        "mean_before":   float(np.mean(bef)) if len(bef) else None,
        "mean_after":    float(np.mean(aft)) if len(aft) else None,
        "median_before": float(np.median(bef)) if len(bef) else None,
        "median_after":  float(np.median(aft)) if len(aft) else None,
        "cohens_d":      cohens_d(bef, aft),
        **test,
    }

    per_artist_rows = []
    for gid, grp in df.groupby("artist_genius_id"):
        b = grp[grp["period"] == "before"][PRIMARY].dropna().values
        a = grp[grp["period"] == "after"][PRIMARY].dropna().values
        if len(b) == 0 or len(a) == 0:
            continue
        t = mw_test(b, a)
        per_artist_rows.append({
            "artist_genius_id": gid,
            "pseudonym":        grp["pseudonym"].iloc[0],
            "country":          grp["country"].iloc[0],
            "n_before":         len(b),
            "n_after":          len(a),
            "mean_before":      float(np.mean(b)),
            "mean_after":       float(np.mean(a)),
            "delta":            float(np.mean(a) - np.mean(b)),
            "cohens_d":         cohens_d(b, a),
            "p_value":          t["p"],
            "significant":      t["sig"],
        })

    per_artist = pd.DataFrame(per_artist_rows)
    per_artist.to_csv(OUT_DIR / "bert_per_artist.csv", index=False)
    return {"overall": overall, "per_artist": per_artist}


# ── Визуализации ─────────────────────────────────────────────────────────────

PALETTE = {"before": "#5B9BD5", "after": "#ED7D31"}
LABEL   = {"before": "До эмиграции", "after": "После эмиграции"}

plt.rcParams.update({
    "font.family":        "DejaVu Sans",
    "figure.dpi":         150,
    "savefig.dpi":        150,
    "savefig.bbox":       "tight",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
})


def fig1_violin(df: pd.DataFrame, res: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle("ruBERT: тональность до и после эмиграции\n(сбалансированная выборка)", fontsize=13, y=1.02)

    plot_data = df.copy()
    plot_data["Период"] = plot_data["period"].map(LABEL)
    order = [LABEL["before"], LABEL["after"]]
    pal   = {LABEL[k]: v for k, v in PALETTE.items()}

    sns.violinplot(
        data=plot_data, x="Период", y=PRIMARY,
        hue="Период", order=order, palette=pal,
        inner="box", cut=0, ax=ax, legend=False,
    )
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel("")
    ax.set_ylabel("Compound score (pos − neg)  ∈ [−1, 1]")

    o = res["overall"]
    d_str = f"{o['cohens_d']:.3f}" if o["cohens_d"] is not None else "—"
    ax.text(
        0.97, 0.03,
        f"p = {o['p']:.3f}  {_sig_stars(o['p'])}\nd = {d_str}",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
        color="#555555",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.7),
    )
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_1_violin.png")
    plt.close()
    print("  ✓ bert_1_violin.png")


def fig2_artist_bars(res: dict) -> None:
    pa = res["per_artist"].sort_values("mean_before").reset_index(drop=True)
    if pa.empty:
        return
    y = np.arange(len(pa))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, max(5, len(pa) * 0.38)))
    ax.barh(y - w/2, pa["mean_before"], w,
            color=PALETTE["before"], label=LABEL["before"], alpha=0.88)
    ax.barh(y + w/2, pa["mean_after"], w,
            color=PALETTE["after"],  label=LABEL["after"],  alpha=0.88)
    ax.set_yticks(y)
    ax.set_yticklabels(pa["pseudonym"], fontsize=8)
    ax.axvline(0, color="black", linewidth=0.7)
    ax.set_xlabel("Compound score (pos − neg)")
    ax.set_title("ruBERT: тональность по артистам (сбалансированная выборка)", fontsize=11)
    ax.legend(fontsize=9)

    for i, row in pa.iterrows():
        if row.get("significant"):
            x_max = max(row["mean_before"], row["mean_after"]) + 0.01
            ax.text(x_max, i, "*", va="center", fontsize=11, color="red")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_2_artist_bars.png")
    plt.close()
    print("  ✓ bert_2_artist_bars.png")


def fig3_scatter(res: dict) -> None:
    pa = res["per_artist"]
    if pa.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 9))
    for _, row in pa.iterrows():
        c = "#E74C3C" if row.get("significant") else "#3498DB"
        ax.scatter(row["mean_before"], row["mean_after"], color=c, s=70, alpha=0.85, zorder=3)
        ax.annotate(row["pseudonym"], (row["mean_before"], row["mean_after"]),
                    textcoords="offset points", xytext=(5, 2), fontsize=7, alpha=0.9)
    all_v = pd.concat([pa["mean_before"], pa["mean_after"]])
    lo, hi = all_v.min() - 0.03, all_v.max() + 0.03
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, alpha=0.45)
    ax.axhline(0, color="gray", linewidth=0.5, alpha=0.5)
    ax.axvline(0, color="gray", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("Compound score ДО эмиграции")
    ax.set_ylabel("Compound score ПОСЛЕ эмиграции")
    ax.set_title(
        "ruBERT: сдвиг тональности по артистам\nВыше диагонали = позитивнее после. Красные = значимо.",
        fontsize=10,
    )
    legend_elems = [
        mpatches.Patch(color="#E74C3C", label="Значимо (p < 0.05)"),
        mpatches.Patch(color="#3498DB", label="Незначимо"),
    ]
    ax.legend(handles=legend_elems, fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_3_scatter.png")
    plt.close()
    print("  ✓ bert_3_scatter.png")


def fig4_kde(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for period in ("before", "after"):
        vals = df[df["period"] == period][PRIMARY].dropna()
        vals.plot.kde(ax=ax, label=LABEL[period], color=PALETTE[period], linewidth=2)
        ax.axvline(vals.median(), color=PALETTE[period], linestyle=":", linewidth=1, alpha=0.7)
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Compound score  (pos − neg)")
    ax.set_ylabel("Плотность вероятности")
    ax.set_title("ruBERT: распределение тональности до и после эмиграции", fontsize=12)
    ax.legend(fontsize=10)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_4_kde.png")
    plt.close()
    print("  ✓ bert_4_kde.png")


def fig5_delta(res: dict) -> None:
    pa = res["per_artist"].sort_values("delta").reset_index(drop=True)
    if pa.empty:
        return
    colors = ["#E74C3C" if d < 0 else "#27AE60" for d in pa["delta"]]
    fig, ax = plt.subplots(figsize=(10, max(5, len(pa) * 0.38)))
    ax.barh(pa["pseudonym"], pa["delta"], color=colors, alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Δ compound score  (после − до)")
    ax.set_title(
        "ruBERT: изменение тональности после эмиграции (сбалансированная выборка)\n"
        "Зелёный = позитивнее, красный = негативнее. * — значимо",
        fontsize=10,
    )
    for i, row in pa.iterrows():
        if row.get("significant"):
            x = row["delta"]
            offset = 0.005 if x >= 0 else -0.005
            ax.text(x + offset, i, "*",
                    ha="left" if x >= 0 else "right", va="center", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_5_delta.png")
    plt.close()
    print("  ✓ bert_5_delta.png")


def fig6_timeline(df: pd.DataFrame) -> None:
    before, after = build_timeline_series(df, PRIMARY)

    fig, ax = plt.subplots(figsize=(12, 5))

    if not before.empty:
        regular = before[~before["is_summary"]]
        summary = before[before["is_summary"]]
        if not regular.empty:
            ax.plot(regular["year"], regular["mean"], marker="o",
                    color=PALETTE["before"], label=LABEL["before"], linewidth=2.2)
            ax.fill_between(regular["year"],
                            regular["mean"] - regular["sem"],
                            regular["mean"] + regular["sem"],
                            alpha=0.18, color=PALETTE["before"])
        if not summary.empty:
            ax.plot(summary["year"], summary["mean"], marker="s", markersize=8,
                    color=PALETTE["before"], label=f"{LABEL['before']} (итог)",
                    linewidth=2.2, linestyle="--")

    if not after.empty:
        ax.plot(after["year"], after["mean"], marker="o",
                color=PALETTE["after"], label=LABEL["after"], linewidth=2.2)
        ax.fill_between(after["year"],
                        after["mean"] - after["sem"],
                        after["mean"] + after["sem"],
                        alpha=0.18, color=PALETTE["after"])

    ax.axvline(2022, color="black", linewidth=1.2, linestyle=":", alpha=0.7)
    ax.text(2022.1, ax.get_ylim()[1] * 0.97, "2022", fontsize=8, va="top", alpha=0.7)
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.set_xlabel("Год выпуска")
    ax.set_ylabel("Compound score (±SEM)")
    ax.set_title("ruBERT: динамика тональности по годам (до 2022 / с 2022)", fontsize=12)
    ax.legend(fontsize=9)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_6_timeline.png")
    plt.close()
    print("  ✓ bert_6_timeline.png")


def fig7_label_breakdown(df: pd.DataFrame) -> None:
    """Доли positive / neutral / negative по периодам."""
    def dominant_label(row: pd.Series) -> str:
        pos, neg = row["pos_prob"], row["neg_prob"]
        neu = 1 - pos - neg
        if pos >= neg and pos >= neu: return "positive"
        if neg >= pos and neg >= neu: return "negative"
        return "neutral"

    df2 = df.copy()
    df2["label"] = df2.apply(dominant_label, axis=1)

    order   = ["negative", "neutral", "positive"]
    colors_ = {"negative": "#E74C3C", "neutral": "#95A5A6", "positive": "#27AE60"}

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, period in zip(axes, ("before", "after")):
        sub    = df2[df2["period"] == period]["label"].value_counts()
        total  = sub.sum()
        fracs  = [sub.get(l, 0) / total for l in order]
        colors = [colors_[l] for l in order]
        ax.pie(fracs, labels=order, colors=colors, autopct="%1.1f%%",
               startangle=90, textprops={"fontsize": 9})
        ax.set_title(f"{LABEL[period]}\n({total} треков)", fontsize=10)

    fig.suptitle("ruBERT: доля треков по классу тональности", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_7_label_breakdown.png")
    plt.close()
    print("  ✓ bert_7_label_breakdown.png")


def fig8_method_correlation(df_bert: pd.DataFrame) -> None:
    """Корреляция compound (ruBERT) vs sentiment_ratio (метод 1)."""
    if not LEXICAL_CSV.exists():
        print("  ⚠  lexical CSV не найден, пропускаю корреляционный график.")
        return

    lex = pd.read_csv(LEXICAL_CSV, encoding="utf-8")[["song_id", "sentiment_ratio"]]
    merged = df_bert.merge(lex, on="song_id", how="inner")
    if len(merged) < 10:
        print("  ⚠  Слишком мало пересечений, пропускаю.")
        return

    r, p = stats.pearsonr(merged["sentiment_ratio"], merged["compound"])

    fig, ax = plt.subplots(figsize=(8, 8))
    for period in ("before", "after"):
        sub = merged[merged["period"] == period]
        ax.scatter(sub["sentiment_ratio"], sub["compound"],
                   color=PALETTE[period], label=LABEL[period],
                   alpha=0.35, s=25, rasterized=True)

    # Линия тренда
    z = np.polyfit(merged["sentiment_ratio"], merged["compound"], 1)
    xs = np.linspace(merged["sentiment_ratio"].min(), merged["sentiment_ratio"].max(), 200)
    ax.plot(xs, np.poly1d(z)(xs), "k-", linewidth=1.5, alpha=0.6)

    ax.set_xlabel("Метод 1: лексический индекс (sentiment_ratio)")
    ax.set_ylabel("Метод 3: ruBERT compound score")
    ax.set_title(
        f"Согласованность методов 1 и 3\nr = {r:.3f},  p = {p:.4f}",
        fontsize=11,
    )
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_8_method_correlation.png")
    plt.close()
    print(f"  ✓ bert_8_method_correlation.png  (r = {r:.3f})")


def fig9_heatmap(res: dict) -> None:
    """Тепловая карта: артист × compound до/после."""
    pa = res["per_artist"].set_index("pseudonym").sort_index()
    hm = pa[["mean_before", "mean_after"]].rename(
        columns={"mean_before": "До", "mean_after": "После"}
    )
    fig, ax = plt.subplots(figsize=(5, max(5, len(hm) * 0.38)))
    sns.heatmap(hm, annot=True, fmt=".3f", cmap="RdYlGn",
                center=0, linewidths=0.4, ax=ax,
                cbar_kws={"label": "Compound score"})
    ax.set_title("ruBERT: средний compound score по артистам", fontsize=11)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "bert_9_heatmap.png")
    plt.close()
    print("  ✓ bert_9_heatmap.png")


# ── Главная функция ──────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Трансформерный анализ тональности (ruBERT)")
    print("=" * 60)

    # Данные
    print("\n[1/5] Загружаю данные …")
    musicians = load_musicians()
    songs     = load_songs(set(musicians.keys()))
    print(f"      Музыкантов: {len(musicians)}, треков: {len(songs):,}")

    # Модель
    print("\n[2/5] Загружаю модель …")
    device = get_device()
    pipe   = build_pipeline(device)

    # Инференс
    print("\n[3/5] Инференс …")
    t_start = time.time()
    scores  = run_inference(pipe, songs)
    elapsed = time.time() - t_start
    valid   = sum(1 for s in scores if s is not None)
    print(f"      Готово за {elapsed:.0f}с.  Треков с результатом: {valid:,}")

    df_full = build_df(songs, musicians, scores)
    df = balance_periods(df_full)
    n_before = (df["period"] == "before").sum()
    n_after  = (df["period"] == "after").sum()
    print(f"      Сбалансированная выборка: {len(df):,} треков "
          f"({n_before:,} до / {n_after:,} после)")

    df.to_csv(OUT_DIR / "bert_scores.csv", index=False, encoding="utf-8")

    # Статистика
    print("\n[4/5] Статистика …")
    res = compute_results(df, "balanced")
    o = res["overall"]
    print(f"\n      mean до:    {o['mean_before']:+.4f}")
    print(f"      mean после: {o['mean_after']:+.4f}")
    print(f"      Cohen's d:  {o['cohens_d']:+.4f}")
    print(f"      p-value:    {o['p']:.4f}  {_sig_stars(o['p'])}")

    pa = res["per_artist"].sort_values("delta", key=abs, ascending=False)
    print("\n  Артисты с наибольшим сдвигом тональности:")
    for _, row in pa.head(5).iterrows():
        sig = "*" if row.get("significant") else ""
        print(f"    {row['pseudonym']:<22}  Δ = {row['delta']:+.4f}  {sig}")

    # Визуализации
    print("\n[5/5] Создаю визуализации …")
    fig1_violin(df, res)
    fig2_artist_bars(res)
    fig3_scatter(res)
    fig4_kde(df)
    fig5_delta(res)
    fig6_timeline(df)
    fig7_label_breakdown(df)
    fig8_method_correlation(df)
    fig9_heatmap(res)

    print(f"\nВсе файлы сохранены в: {OUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
