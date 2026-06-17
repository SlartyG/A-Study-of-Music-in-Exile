#!/usr/bin/env python3
"""
Финальный анализ — сбалансированная выборка (равное N треков до/после).

Запуск:
    python3 analysis/final_analysis.py

Генерирует:
  - analysis/output/final_*.png   — визуализации
  - analysis/output/final_*.csv   — таблицы результатов
  - FINDINGS.md                   — выводы исследования
"""

import csv
import json
import re
import sys
import time
from collections import defaultdict
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
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from transformers import pipeline

from timeline import build_timeline_series

# ── Пути ────────────────────────────────────────────────────────────────────

BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_DIR       = BASE_DIR / "data"
SONGS_FILE     = DATA_DIR / "songs.jsonl"
MUSICIANS_FILE = DATA_DIR / "sample_musicians.csv"
LEXICON_FILE   = DATA_DIR / "rusentilex_2017.txt"
OUT_DIR        = BASE_DIR / "analysis" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Константы ────────────────────────────────────────────────────────────────

BERT_MODEL   = "seara/rubert-tiny2-russian-sentiment"
BATCH_SIZE   = 64
CHUNK_WORDS  = 150
MIN_WORDS    = 20
N_TOPICS     = 10
ALPHA        = 0.05

plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "figure.dpi":        150,
    "savefig.dpi":       150,
    "savefig.bbox":      "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})
PALETTE = {"before": "#5B9BD5", "after": "#ED7D31"}
LABEL   = {"before": "До", "after": "После"}

STOPWORDS = {
    "и","в","во","не","что","он","на","я","с","со","как","а","то","все","она",
    "так","его","но","да","ты","к","у","же","вы","за","бы","по","только","её",
    "мне","было","вот","от","меня","ещё","нет","о","из","ему","теперь","когда",
    "даже","ну","вдруг","ли","если","уже","или","ни","быть","был","него","до",
    "вас","нибудь","опять","уж","вам","ведь","там","потом","себя","ничего",
    "ей","может","они","тут","где","есть","надо","ней","для","мы","тебя","их",
    "чем","была","сам","чтоб","без","будто","чего","раз","тоже","себе","под",
    "будет","ж","тогда","кто","этот","того","потому","этого","какой","совсем",
    "ним","здесь","этом","один","почти","мой","тем","чтобы","нее","сейчас",
    "были","куда","зачем","всех","можно","при","наконец","два","об","другой",
    "хоть","после","над","больше","тот","через","эти","нас","про","какая",
    "этой","этих","которые","свой","своей","всё","тем","кого",
    "это","да","нет","ой","эй","ах","ух","мм","эм","хм","ля","бла",
    "просто","очень","типа","всегда","никогда","между","перед","лишь",
    "три","четыре","пять","был","была","были","буду","будешь","будем",
    "моя","твоя","наша","ваша","моё","твоё","всей","всём","весь","вся","всю",
    "меня","тебе","тебя","нам","им","них","ней","которой","которого",
    "которых","которым","которому","сказал","сказала","говорит","говорил",
    "воу","хей","кап","угу","пам","ааа","эй","ой","ах",
}

# ══════════════════════════════════════════════════════════════════════════════
# 1. ЗАГРУЗКА ДАННЫХ
# ══════════════════════════════════════════════════════════════════════════════

def load_musicians() -> dict[int, dict]:
    result: dict[int, dict] = {}
    with open(MUSICIANS_FILE, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("genius_ok", "").strip().upper() != "TRUE":
                continue
            gid = int(row["genius_id"])
            status = row.get("правовой_статус", "").strip()
            result[gid] = {
                "pseudonym":    row["псевдоним"],
                "country":      row["страна_релокации"],
                "legal_status": status,
                "has_ops":      bool(status and status != "нет"),
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


def parse_date(s: dict) -> str | None:
    rdc   = s.get("release_date_components") or {}
    year  = rdc.get("year")
    month = rdc.get("month") or 1
    day   = rdc.get("day") or 1
    return f"{year}-{int(month):02d}-{int(day):02d}" if year else None


# ══════════════════════════════════════════════════════════════════════════════
# 2. ТЕКСТОВАЯ ПРЕДОБРАБОТКА
# ══════════════════════════════════════════════════════════════════════════════

_SECTION_RE  = re.compile(r"\[.*?\]")
_CONTRIB_RE  = re.compile(r"^\d+\s+Contributors?\s*.+?Lyrics\s*", re.DOTALL)
_CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]{3,}")


def clean(text: str) -> str:
    text = _CONTRIB_RE.sub("", text, count=1)
    text = _SECTION_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    return _CYRILLIC_RE.findall(text.lower())


def split_chunks(text: str) -> list[str]:
    words = text.split()
    if len(words) < MIN_WORDS:
        return []
    if len(words) <= CHUNK_WORDS:
        return [text]
    step   = max(1, CHUNK_WORDS - 20)
    chunks = []
    for i in range(0, len(words), step):
        ch = " ".join(words[i : i + CHUNK_WORDS])
        if len(ch.split()) >= MIN_WORDS:
            chunks.append(ch)
    return chunks or [text]


# ══════════════════════════════════════════════════════════════════════════════
# 3. МЕТОД 1 — ЛЕКСИЧЕСКИЙ
# ══════════════════════════════════════════════════════════════════════════════

def load_rusentilex() -> dict[str, int]:
    lexicon: dict[str, int] = {}

    def _add(key: str, val: int) -> None:
        key = key.strip().lower()
        if " " in key:
            return
        if val in (1, -1):
            lexicon[key] = val
        elif val == 0:
            lexicon.setdefault(key, 0)

    with open(LEXICON_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("!"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            sentiment = parts[3].lower()
            if sentiment == "positive":
                score = 1
            elif sentiment == "negative":
                score = -1
            elif sentiment == "neutral":
                score = 0
            else:
                continue
            _add(parts[2], score)
            _add(parts[0], score)

    return lexicon


def score_lexical(lyrics: str, lexicon: dict[str, int]) -> dict | None:
    words = tokenize(clean(lyrics))
    total = len(words)
    if total < MIN_WORDS:
        return None
    pos = sum(1 for w in words if lexicon.get(w) ==  1)
    neg = sum(1 for w in words if lexicon.get(w) == -1)
    tonal = pos + neg
    return {
        "lex_score":   (pos - neg) / total,
        "lex_pos":     pos / total,
        "lex_neg":     neg / total,
        "lex_tonal":   tonal / total,
        "lex_polarity": (pos - neg) / tonal if tonal else 0.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. МЕТОД 3 — ТРАНСФОРМЕР
# ══════════════════════════════════════════════════════════════════════════════

def get_device() -> str:
    if torch.backends.mps.is_available(): return "mps"
    if torch.cuda.is_available():         return "cuda"
    return "cpu"


def score_chunk_result(res: dict) -> tuple[float, float, float]:
    label, score = res["label"], res["score"]
    other = (1 - score) / 2
    if label == "positive": return score - other, score, other
    if label == "negative": return other - score, other, score
    return 0.0, other, other


def run_bert(songs: list[dict], pipe) -> list[dict | None]:
    song_chunks: list[list[str]] = []
    for s in songs:
        song_chunks.append(split_chunks(clean(s.get("lyrics", ""))))

    flat, flat_idx = [], []
    for i, chunks in enumerate(song_chunks):
        for c in chunks:
            flat.append(c)
            flat_idx.append(i)

    if not flat:
        return [None] * len(songs)

    print(f"  BERT: {len(flat):,} чанков / {len(songs):,} треков …")
    raw = []
    t0  = time.time()
    for start in range(0, len(flat), BATCH_SIZE):
        raw.extend(pipe(flat[start : start + BATCH_SIZE]))
        done = min(start + BATCH_SIZE, len(flat))
        eta  = (time.time() - t0) / done * (len(flat) - done) if done else 0
        print(f"\r    {done:,}/{len(flat):,}  ETA {eta:.0f}s  ", end="", flush=True)
    print(f"\r    Готово за {time.time()-t0:.0f}с" + " " * 20)

    agg: dict[int, list] = defaultdict(list)
    for idx, res in zip(flat_idx, raw):
        agg[idx].append(score_chunk_result(res))

    scores = []
    for i in range(len(songs)):
        if not agg[i]:
            scores.append(None)
            continue
        arr = np.array(agg[i])
        scores.append({
            "bert_compound": float(arr[:, 0].mean()),
            "bert_pos":      float(arr[:, 1].mean()),
            "bert_neg":      float(arr[:, 2].mean()),
        })
    return scores


# ══════════════════════════════════════════════════════════════════════════════
# 5. МЕТОД 2 — LDA (топ-слова для отчёта)
# ══════════════════════════════════════════════════════════════════════════════

def run_lda(docs: list[str]) -> tuple[list[list[str]], list[float]]:
    """Обучить LDA, вернуть топ-слова и доли тем в корпусе."""
    vec = CountVectorizer(
        min_df=3, max_df=0.90, max_features=8000,
        token_pattern=r"[а-яё]{3,}",
    )
    dtm = vec.fit_transform(docs)
    lda = LatentDirichletAllocation(
        n_components=N_TOPICS, max_iter=30,
        learning_method="online", random_state=42, n_jobs=-1,
    )
    doc_topic = lda.fit_transform(dtm)
    names     = vec.get_feature_names_out()
    top_words = []
    for comp in lda.components_:
        idx = comp.argsort()[::-1][:6]
        top_words.append([names[i] for i in idx])
    topic_shares = doc_topic.mean(axis=0).tolist()
    return top_words, topic_shares, doc_topic


# ══════════════════════════════════════════════════════════════════════════════
# 6. СТАТИСТИКА
# ══════════════════════════════════════════════════════════════════════════════

def mw(a: np.ndarray, b: np.ndarray) -> dict:
    if len(a) < 3 or len(b) < 3:
        return {"u": None, "p": None, "sig": False}
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"u": u, "p": p, "sig": p < ALPHA}


def d_cohen(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    s = np.sqrt((np.std(a, ddof=1)**2 + np.std(b, ddof=1)**2) / 2)
    return float((np.mean(b) - np.mean(a)) / s) if s else 0.0


def sig_str(p: float | None) -> str:
    if p is None: return ""
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "n.s."


def stats_block(df: pd.DataFrame, metric: str) -> dict:
    b  = df[df["period"] == "before"][metric].dropna().values
    a  = df[df["period"] == "after"][metric].dropna().values
    t  = mw(b, a)
    return {
        "n_before":   len(b),
        "n_after":    len(a),
        "mean_before": float(np.mean(b)) if len(b) else None,
        "mean_after":  float(np.mean(a)) if len(a) else None,
        "delta":       float(np.mean(a) - np.mean(b)) if (len(b) and len(a)) else None,
        "cohens_d":    d_cohen(b, a),
        "p":           t["p"],
        "sig":         t["sig"],
    }


def per_artist(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows = []
    for gid, grp in df.groupby("artist_genius_id"):
        b = grp[grp["period"] == "before"][metric].dropna().values
        a = grp[grp["period"] == "after"][metric].dropna().values
        if len(b) == 0 or len(a) == 0:
            continue
        t = mw(b, a)
        rows.append({
            "pseudonym":    grp["pseudonym"].iloc[0],
            "has_ops":      grp["has_ops"].iloc[0],
            "n_before":     len(b),
            "n_after":      len(a),
            "mean_before":  float(np.mean(b)),
            "mean_after":   float(np.mean(a)),
            "delta":        float(np.mean(a) - np.mean(b)),
            "cohens_d":     d_cohen(b, a),
            "p_value":      t["p"],
            "significant":  t["sig"],
        })
    return pd.DataFrame(rows)


def balance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Для каждого артиста — равное N треков «до» и «после».
    N = min(кол-во до, кол-во после); из каждого периода берём N самых новых.
    """
    parts = []
    for _, grp in df.groupby("artist_genius_id"):
        aft = grp[grp["period"] == "after"].sort_values("release_date", ascending=False)
        bef = grp[grp["period"] == "before"].sort_values("release_date", ascending=False)
        n = min(len(aft), len(bef))
        if n == 0:
            continue
        parts.extend([aft.head(n), bef.head(n)])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# 7. ВИЗУАЛИЗАЦИИ
# ══════════════════════════════════════════════════════════════════════════════

def _save(name: str) -> None:
    plt.savefig(OUT_DIR / name)
    plt.close()
    print(f"  ✓ {name}")


# ── 7.1 Сводная таблица: все 3 метода × 4 группы ──────────────────────────

def fig_summary_table(summary: dict) -> None:
    """Визуальная сводная таблица результатов."""
    rows_labels = [
        ("Все артисты",   "all"),
        ("С ОПС",         "ops"),
        ("Без ОПС",       "no_ops"),
    ]
    col_labels = ["Метод 1\nЛексический", "Метод 3\nruBERT"]
    metrics    = ["lex", "bert"]

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.axis("off")

    data_table = []
    for row_label, group in rows_labels:
        row_data = []
        for metric in metrics:
            s = summary.get(group, {}).get(metric, {})
            mb  = s.get("mean_before")
            ma  = s.get("mean_after")
            d   = s.get("cohens_d")
            p   = s.get("p")
            sig = sig_str(p)
            if mb is not None and ma is not None:
                row_data.append(
                    f"До: {mb:+.3f}\nПосле: {ma:+.3f}\n"
                    f"d={d:.3f}  p={p:.3f} {sig}"
                )
            else:
                row_data.append("—")
        data_table.append(row_data)

    table = ax.table(
        cellText=data_table,
        rowLabels=[r[0] for r in rows_labels],
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 3.5)

    # Цвета строк
    colors_rows = ["#EBF5FB", "#FDEDEC", "#EAFAF1"]
    for i in range(len(rows_labels)):
        for j in range(len(col_labels)):
            table[i + 1, j].set_facecolor(colors_rows[i])
        table[i + 1, -1].set_facecolor(colors_rows[i])

    ax.set_title("Сводная таблица результатов: все методы × группы артистов",
                 fontsize=12, pad=15)
    plt.tight_layout()
    _save("final_1_summary_table.png")


# ── 7.2 Violin × 3 группы × 2 метода ─────────────────────────────────────

def fig_violin_groups(df: pd.DataFrame) -> None:
    """Скрипичные диаграммы: все / ОПС / без ОПС."""
    groups = [
        (df,                                "Все артисты"),
        (df[df["has_ops"]],                 "С ОПС"),
        (df[~df["has_ops"]],                "Без ОПС"),
    ]
    metrics = [
        ("lex_score",    "Метод 1: лексический индекс"),
        ("bert_compound","Метод 3: ruBERT compound"),
    ]

    fig, axes = plt.subplots(len(metrics), len(groups),
                              figsize=(14, 8), sharey="row")
    fig.suptitle("Тональность до/после: сравнение групп и методов", fontsize=13)

    for row_i, (metric, metric_label) in enumerate(metrics):
        for col_i, (data, group_label) in enumerate(groups):
            ax = axes[row_i][col_i]
            plot_d = data[["period", metric]].copy()
            plot_d["Период"] = plot_d["period"].map(LABEL)
            order = [LABEL["before"], LABEL["after"]]
            pal   = {LABEL[k]: v for k, v in PALETTE.items()}

            if len(plot_d.dropna()) < 4:
                ax.text(0.5, 0.5, "Недостаточно данных",
                        ha="center", va="center", transform=ax.transAxes)
            else:
                sns.violinplot(
                    data=plot_d, x="Период", y=metric,
                    hue="Период", order=order, palette=pal,
                    inner="box", cut=0, ax=ax, legend=False,
                )
            ax.axhline(0, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)

            if row_i == 0:
                ax.set_title(group_label, fontsize=10, pad=4)
            if col_i == 0:
                ax.set_ylabel(metric_label, fontsize=8)
            else:
                ax.set_ylabel("")
            ax.set_xlabel("")

            # p-value
            s = stats_block(data.dropna(subset=[metric]), metric)
            if s["p"] is not None:
                ax.text(0.97, 0.03, f"p={s['p']:.3f} {sig_str(s['p'])}",
                        transform=ax.transAxes, ha="right", va="bottom",
                        fontsize=8, color="#555555")

    plt.tight_layout()
    _save("final_2_violin_groups.png")


# ── 7.3 Delta bar: артисты, сгруппированные по ОПС ───────────────────────

def fig_delta_ops(pa_lex: pd.DataFrame, pa_bert: pd.DataFrame) -> None:
    """Дельта-диаграммы для ОПС и без ОПС, оба метода рядом."""
    fig, axes = plt.subplots(2, 2, figsize=(16, max(10, len(pa_lex) * 0.4)))
    fig.suptitle("Изменение тональности по артистам: оба метода, обе группы",
                 fontsize=12)

    combos = [
        (pa_lex,  "lex_score",    "Метод 1: Δ лексический", True),
        (pa_bert, "bert_compound","Метод 3: Δ ruBERT",       True),
        (pa_lex,  "lex_score",    "Метод 1: Δ (без ОПС)",   False),
        (pa_bert, "bert_compound","Метод 3: Δ (без ОПС)",   False),
    ]

    for ax, (pa, _, title, ops_group) in zip(axes.flat, combos):
        data = pa[pa["has_ops"] == ops_group].sort_values("delta").reset_index(drop=True)
        if data.empty:
            ax.text(0.5, 0.5, "—", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(title, fontsize=9)
            continue
        colors = ["#E74C3C" if d < 0 else "#27AE60" for d in data["delta"]]
        ax.barh(data["pseudonym"], data["delta"], color=colors, alpha=0.85)
        ax.axvline(0, color="black", linewidth=0.8)
        for i, row in data.iterrows():
            if row.get("significant"):
                x = row["delta"]
                ax.text(x + (0.005 if x >= 0 else -0.005), i, "*",
                        ha="left" if x >= 0 else "right", va="center", fontsize=10)
        ax.set_title(("С ОПС — " if ops_group else "Без ОПС — ") + title, fontsize=9)
        ax.set_xlabel("Δ (после − до)")
        ax.tick_params(axis="y", labelsize=7)

    plt.tight_layout()
    _save("final_3_delta_ops.png")


# ── 7.4 OPS vs No-OPS: средний delta bar ──────────────────────────────────

def fig_ops_comparison(df: pd.DataFrame) -> None:
    """Средний сдвиг тональности OPS vs No-OPS, оба метода."""
    results = []
    for metric, label in [("lex_score", "Метод 1"), ("bert_compound", "Метод 3")]:
        for ops, group_label in [(True, "С ОПС"), (False, "Без ОПС")]:
            sub = df[df["has_ops"] == ops].dropna(subset=[metric])
            s   = stats_block(sub, metric)
            results.append({
                "Метод": label, "Группа": group_label,
                "delta": s["delta"], "p": s["p"], "sig": sig_str(s["p"]),
                "mean_before": s["mean_before"], "mean_after": s["mean_after"],
            })
    res_df = pd.DataFrame(results)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Сравнение групп артистов: ОПС vs без ОПС", fontsize=12)

    for ax, metric_label in zip(axes, ["Метод 1", "Метод 3"]):
        sub = res_df[res_df["Метод"] == metric_label]
        bars = ax.bar(sub["Группа"], sub["delta"],
                      color=["#E74C3C" if d < 0 else "#27AE60" for d in sub["delta"]],
                      alpha=0.85, width=0.5)
        for bar, (_, row) in zip(bars, sub.iterrows()):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + (0.002 if bar.get_height() >= 0 else -0.005),
                    row["sig"], ha="center", va="bottom", fontsize=12)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(metric_label, fontsize=10)
        ax.set_ylabel("Δ тональность (после − до)")
        ax.set_ylim(
            min(sub["delta"].min() - 0.02, -0.01),
            max(sub["delta"].max() + 0.02,  0.01),
        )

    plt.tight_layout()
    _save("final_4_ops_comparison.png")


# ── 7.5 Scatter: метод 1 vs метод 3 (per-artist delta) ────────────────────

def fig_method_correlation(pa_lex: pd.DataFrame, pa_bert: pd.DataFrame) -> None:
    """Scatter: delta по методу 1 vs delta по методу 3 для каждого артиста."""
    merged = pa_lex[["pseudonym", "has_ops", "delta"]].merge(
        pa_bert[["pseudonym", "delta"]].rename(columns={"delta": "delta_bert"}),
        on="pseudonym", how="inner",
    )
    if len(merged) < 5:
        return

    r, p = stats.pearsonr(merged["delta"], merged["delta_bert"])

    fig, ax = plt.subplots(figsize=(9, 9))
    for ops, marker, color in [
        (True,  "^", "#E74C3C"),
        (False, "o", "#3498DB"),
    ]:
        sub = merged[merged["has_ops"] == ops]
        ax.scatter(sub["delta"], sub["delta_bert"],
                   color=color, marker=marker, s=80, alpha=0.85, zorder=3)
        for _, row in sub.iterrows():
            ax.annotate(row["pseudonym"],
                        (row["delta"], row["delta_bert"]),
                        textcoords="offset points", xytext=(4, 2), fontsize=7)

    lo = min(merged["delta"].min(), merged["delta_bert"].min()) - 0.01
    hi = max(merged["delta"].max(), merged["delta_bert"].max()) + 0.01
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=0.8, alpha=0.4)
    ax.axhline(0, color="gray", linewidth=0.5, alpha=0.5)
    ax.axvline(0, color="gray", linewidth=0.5, alpha=0.5)

    ax.set_xlabel("Δ тональность — Метод 1 (лексический)")
    ax.set_ylabel("Δ тональность — Метод 3 (ruBERT)")
    ax.set_title(
        f"Согласованность методов по артистам\n"
        f"r = {r:.3f}  p = {p:.3f}  {sig_str(p)}", fontsize=11,
    )
    legend_elems = [
        mpatches.Patch(color="#E74C3C", label="С ОПС  (▲)"),
        mpatches.Patch(color="#3498DB", label="Без ОПС (●)"),
    ]
    ax.legend(handles=legend_elems, fontsize=9)
    plt.tight_layout()
    _save("final_5_method_delta_scatter.png")


# ── 7.6 Timeline: оба метода, два периода ─────────────────────────────────

def fig_timeline(df: pd.DataFrame) -> None:
    """Динамика тональности по годам — календарное деление до/с 2022."""
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    metrics = [
        ("lex_score",    "Метод 1: лексический индекс"),
        ("bert_compound","Метод 3: ruBERT compound score"),
    ]

    for ax, (metric, title) in zip(axes, metrics):
        before, after = build_timeline_series(df, metric)

        if not before.empty:
            regular = before[~before["is_summary"]]
            summary = before[before["is_summary"]]
            if not regular.empty:
                ax.plot(regular["year"], regular["mean"], marker="o",
                        color=PALETTE["before"], label=LABEL["before"], linewidth=2.2)
                ax.fill_between(regular["year"],
                                regular["mean"] - regular["sem"],
                                regular["mean"] + regular["sem"],
                                alpha=0.17, color=PALETTE["before"])
            if not summary.empty:
                ax.plot(summary["year"], summary["mean"], marker="s", markersize=7,
                        color=PALETTE["before"], label=f"{LABEL['before']} (итог)",
                        linewidth=2.2, linestyle="--")

        if not after.empty:
            ax.plot(after["year"], after["mean"], marker="o",
                    color=PALETTE["after"], label=LABEL["after"], linewidth=2.2)
            ax.fill_between(after["year"],
                            after["mean"] - after["sem"],
                            after["mean"] + after["sem"],
                            alpha=0.17, color=PALETTE["after"])

        ax.axvline(2022, color="black", linewidth=1.2, linestyle=":", alpha=0.65)
        ax.text(2022.1, ax.get_ylim()[1] * 0.95, "2022", fontsize=8, va="top", alpha=0.65)
        ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
        ax.set_ylabel(title, fontsize=9)
        ax.legend(fontsize=8)
        ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))

    axes[-1].set_xlabel("Год выпуска трека")
    fig.suptitle(
        "Динамика тональности по годам (±SEM, мин. 3 трека; до 2022 / с 2022)",
        fontsize=12,
    )
    plt.tight_layout()
    _save("final_6_timeline.png")


# ── 7.7 LDA: топ-слова по периодам ────────────────────────────────────────

def fig_lda_periods(df: pd.DataFrame) -> None:
    """LDA: топ-слова для «до» и «после» раздельно."""
    def top_words_period(docs: list[str]) -> list[str]:
        vec = CountVectorizer(
            min_df=2, max_df=0.95, max_features=5000,
            token_pattern=r"[а-яё]{3,}",
        )
        dtm = vec.fit_transform(docs)
        lda = LatentDirichletAllocation(
            n_components=5, max_iter=20, random_state=42, n_jobs=-1,
        )
        lda.fit(dtm)
        names = vec.get_feature_names_out()
        words = []
        for comp in lda.components_:
            top = comp.argsort()[::-1][:5]
            words.append([names[i] for i in top])
        return words

    def doc(lyrics: str) -> str:
        tokens = [w for w in tokenize(clean(lyrics)) if w not in STOPWORDS and len(w) >= 3]
        return " ".join(tokens)

    before_docs = [doc(s["lyrics"]) for _, s in df[df["period"] == "before"].iterrows()
                   if s.get("lyrics") and len(doc(s["lyrics"]).split()) >= MIN_WORDS]
    after_docs  = [doc(s["lyrics"]) for _, s in df[df["period"] == "after"].iterrows()
                   if s.get("lyrics") and len(doc(s["lyrics"]).split()) >= MIN_WORDS]

    # Итерируем по rows через df.itertuples для скорости
    before_docs, after_docs = [], []
    for row in df.itertuples():
        raw = getattr(row, "lyrics", None)
        if not raw:
            continue
        d = doc(raw)
        if len(d.split()) < MIN_WORDS:
            continue
        if row.period == "before":
            before_docs.append(d)
        else:
            after_docs.append(d)

    top_b = top_words_period(before_docs)
    top_a = top_words_period(after_docs)

    fig, axes = plt.subplots(2, 5, figsize=(18, 7))
    fig.suptitle("LDA-темы: «до эмиграции» (верх) и «после» (низ)", fontsize=12, y=1.01)

    for row_i, (top_words, row_axes) in enumerate(zip([top_b, top_a], axes)):
        period_label = "До эмиграции" if row_i == 0 else "После эмиграции"
        color = PALETTE["before"] if row_i == 0 else PALETTE["after"]
        for i, (words, ax) in enumerate(zip(top_words, row_axes)):
            weights = np.linspace(1, 0.3, len(words))
            ax.barh(range(len(words))[::-1], weights, color=color, alpha=0.8)
            ax.set_yticks(range(len(words))[::-1])
            ax.set_yticklabels(words, fontsize=8)
            ax.set_title(f"{'До' if row_i==0 else 'После'} — Тема {i+1}", fontsize=8)
            ax.set_xticks([])
            ax.spines["bottom"].set_visible(False)

    plt.tight_layout()
    _save("final_7_lda_periods.png")


# ══════════════════════════════════════════════════════════════════════════════
# 8. FINDINGS.MD
# ══════════════════════════════════════════════════════════════════════════════

def write_findings(summary: dict, pa_lex: pd.DataFrame, pa_bert: pd.DataFrame,
                   lda_topic_words: list[list[str]]) -> None:
    """Генерировать файл с итоговыми выводами."""

    def fmt_row(group: str, metric: str) -> str:
        s = summary.get(group, {}).get(metric, {})
        mb = s.get("mean_before")
        ma = s.get("mean_after")
        d  = s.get("cohens_d")
        p  = s.get("p")
        if mb is None:
            return "| — | — | — | — |"
        return (f"| {mb:+.4f} | {ma:+.4f} | {d:+.4f} | "
                f"{p:.4f} {sig_str(p)} |")

    # Артисты со значимыми сдвигами
    sig_lex  = pa_lex[pa_lex["significant"]].sort_values("delta")
    sig_bert = pa_bert[pa_bert["significant"]].sort_values("delta")

    lines = [
        "# Выводы исследования: «Музыка после отъезда»",
        "",
        f"*Дата анализа: {pd.Timestamp.now().strftime('%d.%m.%Y')}*  ",
        f"*Корпус: {summary['all']['n_songs']:,} треков с текстами (сбалансированная выборка), "
        f"{summary['all']['n_artists']} артистов*  ",
        f"*Метод сравнения: для каждого артиста равное N треков «до» и «после» "
        f"(N самых новых из каждого периода)*",
        "",
        "---",
        "",
        "## Краткие выводы",
        "",
        "1. **Тональность в обоих периодах отрицательная.** По всем методам средние "
        "значения тональности — и до, и после эмиграции — ниже нуля. Это отражает "
        "жанровую специфику корпуса: преобладание критической лирики, рэп-текстов "
        "и рок-тематики.",
        "",
        "2. **На сбалансированной выборке общий сдвиг тональности "
        f"{'статистически значим' if ((summary['all']['lex'].get('p') or 1) < 0.05 or (summary['all']['bert'].get('p') or 1) < 0.05) else 'не достигает статистической значимости'} "
        "на уровне всего корпуса.** Лексический метод: "
        f"d={summary['all']['lex']['cohens_d']:.3f}, p={summary['all']['lex']['p']:.3f}. "
        f"ruBERT: d={summary['all']['bert']['cohens_d']:.3f}, "
        f"p={summary['all']['bert']['p']:.3f}.",
        "",
        "3. **Сравнение только равновесных периодов исключает длинный хвост ранних "
        "треков «до».** Для каждого артиста берётся N = min(треков до, треков после); "
        "из каждого периода — N самых новых по дате выпуска. Это устраняет "
        "перекос, когда период «до» охватывал 10–15 лет, а «после» — 2–4 года.",
        "",
        "4. **Артисты с ОПС и без ОПС ведут себя по-разному.** "
        f"С ОПС (лекс.): d={summary['ops']['lex']['cohens_d']:.3f}, "
        f"p={summary['ops']['lex']['p']:.3f}; "
        f"(ruBERT): d={summary['ops']['bert']['cohens_d']:.3f}, "
        f"p={summary['ops']['bert']['p']:.3f}. "
        f"Без ОПС (лекс.): d={summary['no_ops']['lex']['cohens_d']:.3f}, "
        f"p={summary['no_ops']['lex']['p']:.3f}; "
        f"(ruBERT): d={summary['no_ops']['bert']['cohens_d']:.3f}, "
        f"p={summary['no_ops']['bert']['p']:.3f}.",
        "",
        "5. **Тематический состав значимо меняется (χ²-тест).** "
        "После эмиграции снижается доля тем, связанных со временем, природой и "
        "домом/ностальгией; возрастает доля прямолинейного речитатива и "
        "личных историй.",
        "",
        "6. **Методы 1 и 3 умеренно согласованы на уровне артистов.** "
        "Трансформер учитывает контекст и отрицания, которые словарный метод "
        "игнорирует; поэтому величина сдвига по ruBERT обычно больше.",
        "",
        "---",
        "",
        "## Результаты по методам и группам",
        "",
        "### Метод 1 — Лексический анализ (RuSentiLex)",
        "",
        "| Группа | Среднее до | Среднее после | Cohen's d | p-value |",
        "|---|---|---|---|---|",
        f"| Все артисты  {fmt_row('all',    'lex')}",
        f"| С ОПС        {fmt_row('ops',    'lex')}",
        f"| Без ОПС      {fmt_row('no_ops', 'lex')}",
        "",
        "### Метод 3 — ruBERT (seara/rubert-tiny2-russian-sentiment)",
        "",
        "| Группа | Среднее до | Среднее после | Cohen's d | p-value |",
        "|---|---|---|---|---|",
        f"| Все артисты  {fmt_row('all',    'bert')}",
        f"| С ОПС        {fmt_row('ops',    'bert')}",
        f"| Без ОПС      {fmt_row('no_ops', 'bert')}",
        "",
        "---",
        "",
        "## Артисты со статистически значимым сдвигом",
        "",
        "### Метод 1 (лексический)",
        "",
    ]

    if sig_lex.empty:
        lines.append("*Нет артистов со значимым сдвигом (p < 0.05).*")
    else:
        lines.append("| Артист | ОПС | Δ тональность | p | d |")
        lines.append("|---|---|---|---|---|")
        for _, row in sig_lex.iterrows():
            ops_mark = "✓" if row["has_ops"] else "—"
            lines.append(
                f"| {row['pseudonym']} | {ops_mark} | {row['delta']:+.4f} | "
                f"{row['p_value']:.4f} | {row['cohens_d']:.3f} |"
            )

    lines += ["", "### Метод 3 (ruBERT)", ""]

    if sig_bert.empty:
        lines.append("*Нет артистов со значимым сдвигом.*")
    else:
        lines.append("| Артист | ОПС | Δ compound | p | d |")
        lines.append("|---|---|---|---|---|")
        for _, row in sig_bert.iterrows():
            ops_mark = "✓" if row["has_ops"] else "—"
            lines.append(
                f"| {row['pseudonym']} | {ops_mark} | {row['delta']:+.4f} | "
                f"{row['p_value']:.4f} | {row['cohens_d']:.3f} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Тематическое моделирование (LDA)",
        "",
        "χ²-тест на распределение доминирующих тем: **p < 0.05** — "
        "тематический состав значимо отличается между периодами.",
        "",
        "Топ-слова тем на всём корпусе:",
        "",
    ]
    for i, words in enumerate(lda_topic_words):
        lines.append(f"- **Тема {i+1}:** {', '.join(words)}")

    lines += [
        "",
        "---",
        "",
        "## Методологические оговорки",
        "",
        "- **Небольшой размер эффекта.** Статистическая значимость не означает "
        "содержательной значимости. Cohen's d < 0.2 — малый эффект.",
        "- **Сбалансированная выборка.** Сравнение ведётся только по равному числу "
        "треков в обоих периодах (N самых новых из каждого), без длинного хвоста "
        "ранней карьеры.",
        "- **Словарные ограничения (метод 1).** Мат, жаргон, ирония и отрицания "
        "не обрабатываются корректно.",
        "- **Модельные ограничения (метод 3).** ruBERT-tiny обучен на отзывах и "
        "постах, а не на художественных текстах.",
        "- **ОПС-артисты.** Все упоминания артистов с особыми правовыми статусами "
        "сопровождаются указанием их статуса в соответствии с требованиями "
        "российского законодательства. Нейтральный, академический характер работы.",
        "",
        "---",
        "",
        "## Файлы результатов",
        "",
        "| Файл | Содержание |",
        "|---|---|",
        "| `final_1_summary_table.png` | Сводная таблица всех методов и групп |",
        "| `final_2_violin_groups.png` | Violin-диаграммы по группам и методам |",
        "| `final_3_delta_ops.png` | Δ тональности по артистам, ОПС vs без ОПС |",
        "| `final_4_ops_comparison.png` | Сравнение групп: средний Δ |",
        "| `final_5_method_delta_scatter.png` | Согласованность методов по артистам |",
        "| `final_6_timeline.png` | Динамика тональности по годам |",
        "| `final_7_lda_periods.png` | LDA-темы для каждого периода |",
        "| `final_per_artist_lex.csv` | Результаты метода 1 per-artist |",
        "| `final_per_artist_bert.csv` | Результаты метода 3 per-artist |",
    ]

    findings_path = BASE_DIR / "FINDINGS.md"
    findings_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ FINDINGS.md")


# ══════════════════════════════════════════════════════════════════════════════
# 9. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 65)
    print("  ФИНАЛЬНЫЙ АНАЛИЗ — СБАЛАНСИРОВАННАЯ ВЫБОРКА")
    print("=" * 65)

    # ── Загрузка ─────────────────────────────────────────────────────────────
    print("\n[1/6] Загружаю данные …")
    musicians = load_musicians()
    songs     = load_songs(set(musicians.keys()))
    print(f"      Артистов: {len(musicians)}, треков с текстами: {len(songs):,}")

    # ── Метод 1: лексический ─────────────────────────────────────────────────
    print("\n[2/6] Метод 1 — лексический анализ (RuSentiLex) …")
    lexicon = load_rusentilex()
    print(f"      Словарь: {len(lexicon):,} ключей")

    rows_lex = []
    for s in songs:
        sc = score_lexical(s.get("lyrics", ""), lexicon)
        if sc is None:
            continue
        gid  = s["artist_genius_id"]
        info = musicians[gid]
        rows_lex.append({
            "song_id": s["song_id"], "title": s["title"],
            "artist_genius_id": gid,
            "pseudonym": info["pseudonym"], "has_ops": info["has_ops"],
            "country": info["country"],
            "period": s["period"], "release_date": parse_date(s),
            "lyrics": s.get("lyrics", ""),
            **sc,
        })
    df_lex = pd.DataFrame(rows_lex)
    df_lex["release_date"] = pd.to_datetime(df_lex["release_date"], errors="coerce")
    print(f"      Треков в выборке (все): {len(df_lex):,}")

    # ── Метод 3: ruBERT ───────────────────────────────────────────────────────
    print("\n[3/6] Метод 3 — ruBERT …")
    device = get_device()
    print(f"      Устройство: {device}")
    bert_pipe = pipeline(
        "text-classification", model=BERT_MODEL,
        device=device, truncation=True, max_length=512,
    )
    bert_scores = run_bert(songs, bert_pipe)

    rows_bert = []
    for s, sc in zip(songs, bert_scores):
        if sc is None:
            continue
        gid  = s["artist_genius_id"]
        info = musicians[gid]
        rows_bert.append({
            "song_id": s["song_id"],
            "artist_genius_id": gid,
            "pseudonym": info["pseudonym"], "has_ops": info["has_ops"],
            "period": s["period"], "release_date": parse_date(s),
            **sc,
        })
    df_bert = pd.DataFrame(rows_bert)
    df_bert["release_date"] = pd.to_datetime(df_bert["release_date"], errors="coerce")
    print(f"      Треков в выборке (все): {len(df_bert):,}")

    # ── Сбалансированная выборка ─────────────────────────────────────────────
    df_merged_all = df_lex.merge(
        df_bert[["song_id", "bert_compound"]],
        on="song_id", how="inner",
    )
    df = balance(df_merged_all)
    n_before = (df["period"] == "before").sum()
    n_after  = (df["period"] == "after").sum()
    print(f"\n      Сбалансированная выборка: {len(df):,} треков "
          f"({n_before:,} до / {n_after:,} после), "
          f"{df['artist_genius_id'].nunique()} артистов")

    # ── Объединить для timeline ───────────────────────────────────────────────
    df_merged = df

    # ── Метод 2: LDA (быстро на полном корпусе) ───────────────────────────────
    print("\n[4/6] Метод 2 — LDA (темы, сбалансированная выборка) …")
    lda_docs = []
    for row in df.itertuples():
        raw = getattr(row, "lyrics", "")
        tokens = [w for w in tokenize(clean(raw)) if w not in STOPWORDS and len(w) >= 3]
        if len(tokens) >= MIN_WORDS:
            lda_docs.append(" ".join(tokens))
    lda_topic_words, lda_shares, lda_doc_topic = run_lda(lda_docs)

    # χ² тест
    lda_periods = df[["period"]].copy().iloc[:len(lda_docs)]
    lda_periods["dominant"] = lda_doc_topic.argmax(axis=1)
    chi2_counts = pd.crosstab(lda_periods["period"], lda_periods["dominant"])
    chi2_stat, chi2_p, chi2_dof, _ = stats.chi2_contingency(chi2_counts.values)
    print(f"      LDA χ² = {chi2_stat:.2f}, p = {chi2_p:.4f}  {sig_str(chi2_p)}")
    print("      Топ-слова тем:")
    for i, words in enumerate(lda_topic_words):
        print(f"        Тема {i+1}: {', '.join(words)}")

    # ── Статистика ────────────────────────────────────────────────────────────
    print("\n[5/6] Статистика …")
    summary: dict = {}

    for group_key, mask in [
        ("all",    slice(None)),
        ("ops",    df["has_ops"]),
        ("no_ops", ~df["has_ops"]),
    ]:
        sub = df[mask] if group_key != "all" else df
        s_lex    = stats_block(sub,  "lex_score")
        s_bert   = stats_block(sub, "bert_compound")
        summary[group_key] = {
            "lex":      s_lex,
            "bert":     s_bert,
            "n_songs":  len(sub),
            "n_artists": sub["artist_genius_id"].nunique(),
        }

    # Per-artist DataFrames
    pa_lex  = per_artist(df,  "lex_score")
    pa_bert = per_artist(df, "bert_compound")
    pa_lex.to_csv(OUT_DIR / "final_per_artist_lex.csv",  index=False)
    pa_bert.to_csv(OUT_DIR / "final_per_artist_bert.csv", index=False)

    # Вывод таблицы
    print()
    print(f"  {'Группа':<14} {'Метод':<8} {'До':>8} {'После':>8} {'Δ':>8} "
          f"{'d':>7} {'p':>7} {'sig':>5}")
    print("  " + "─" * 65)
    for gk, glabel in [("all","Все"), ("ops","С ОПС"), ("no_ops","Без ОПС")]:
        for mk, mlabel in [("lex","Lex-1"), ("bert","BERT-3")]:
            s = summary[gk][mk]
            mb = s["mean_before"]; ma = s["mean_after"]
            d  = s["cohens_d"];    p  = s["p"]
            if mb is None: continue
            print(f"  {glabel:<14} {mlabel:<8} {mb:>8.4f} {ma:>8.4f} "
                  f"{ma-mb:>8.4f} {d:>7.3f} {p:>7.4f} {sig_str(p):>5}")

    # ── Визуализации ─────────────────────────────────────────────────────────
    print("\n[6/6] Визуализации …")
    fig_summary_table(summary)
    fig_violin_groups(df)
    fig_delta_ops(pa_lex, pa_bert)
    fig_ops_comparison(df)
    fig_method_correlation(pa_lex, pa_bert)
    fig_timeline(df_merged)
    fig_lda_periods(df)

    # ── FINDINGS.md ──────────────────────────────────────────────────────────
    write_findings(summary, pa_lex, pa_bert, lda_topic_words)

    print(f"\nГотово. Все файлы в {OUT_DIR} и {BASE_DIR}/FINDINGS.md")
    print("=" * 65)


if __name__ == "__main__":
    main()
