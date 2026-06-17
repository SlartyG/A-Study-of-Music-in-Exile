#!/usr/bin/env python3
"""
Метод 1: Лексический анализ тональности текстов российских музыкантов в эмиграции.

Алгоритм:
  1. Загрузить тексты треков из data/songs.jsonl (только has_lyrics=True,
     только артисты с genius_ok=TRUE из data/sample_musicians.csv).
  2. Очистить тексты и лемматизировать с pymorphy2.
  3. Сопоставить леммы со словарём тональности RuSentiLex.
  4. Вычислить метрики тональности для каждого трека.
  5. Сравнить периоды "до" и "после" на сбалансированной выборке
       (равное N треков на артиста, N самых новых из каждого периода).
  6. Провести статистические тесты (Mann–Whitney U, Cohen's d).
  7. Сохранить результаты в CSV и визуализации в analysis/output/.

Запуск:
    python3 analysis/lexical_sentiment.py
"""

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

from timeline import build_timeline_series

try:
    import pymorphy2
    _MORPH = pymorphy2.MorphAnalyzer()
    HAS_PYMORPHY = True
except Exception:
    HAS_PYMORPHY = False


# ── Пути ────────────────────────────────────────────────────────────────────

BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_DIR       = BASE_DIR / "data"
SONGS_FILE     = DATA_DIR / "songs.jsonl"
MUSICIANS_FILE = DATA_DIR / "sample_musicians.csv"
LEXICON_FILE   = DATA_DIR / "rusentilex_2017.txt"
OUT_DIR        = BASE_DIR / "analysis" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUSENTILEX_URL = "http://www.labinform.ru/pub/rusentilex/rusentilex_2017.txt"

# Основная метрика, выводимая на осях графиков
PRIMARY_METRIC       = "sentiment_ratio"
PRIMARY_METRIC_LABEL = "Индекс тональности  (pos − neg) / total_words"


# ── 1. Словарь тональности ─────────────────────────────────────────────────

def _download_rusentilex() -> None:
    if LEXICON_FILE.exists():
        return
    print(f"Скачиваю RuSentiLex → {LEXICON_FILE} …")
    urllib.request.urlretrieve(RUSENTILEX_URL, LEXICON_FILE)
    print("  готово.")


def load_rusentilex() -> dict[str, int]:
    """
    Загрузить RuSentiLex 2017.
    Формат строк: слово/словосочетание, ЧастьРечи, лемма, тональность, источник[, ...]
    Строки, начинающиеся на '!', — комментарии.

    Возвращает словарь {форма: +1 / -1 / 0}.
    Добавляем и лемму, и исходную форму — так повышаем покрытие без
    отдельного морфологического анализатора (pymorphy2). Слова с меткой
    positive/negative пропускаются как контекстно-неоднозначные.
    """
    _download_rusentilex()
    lexicon: dict[str, int] = {}

    def _add(key: str, val: int) -> None:
        key = key.strip().lower()
        if " " in key:           # многословные выражения пропускаем
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
            term      = parts[0]
            lemma     = parts[2]
            sentiment = parts[3].lower()
            if sentiment == "positive":
                score = 1
            elif sentiment == "negative":
                score = -1
            elif sentiment == "neutral":
                score = 0
            else:
                continue    # "positive/negative" — неоднозначно
            _add(lemma, score)
            _add(term,  score)

    return lexicon


# ── 2. Очистка и лемматизация ──────────────────────────────────────────────

# Заголовки секций на Genius: [Куплет 1], [Припев], [Verse 1], ...
_SECTION_RE     = re.compile(r"\[.*?\]")
# Строка "N Contributors<ТрекTitle> Lyrics" в начале
_CONTRIB_RE     = re.compile(r"^\d+\s+Contributors?\s*.+?Lyrics\s*", re.DOTALL)
# Только кириллические слова
_CYRILLIC_RE    = re.compile(r"[а-яёА-ЯЁ]+")


def clean_lyrics(text: str) -> str:
    text = _CONTRIB_RE.sub("", text, count=1)
    text = _SECTION_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def lemmatize(words: list[str]) -> list[str]:
    if HAS_PYMORPHY:
        return [_MORPH.parse(w)[0].normal_form for w in words]
    return [w.lower() for w in words]


def tokenize_and_lemmatize(text: str) -> list[str]:
    words = _CYRILLIC_RE.findall(text.lower())
    return lemmatize(words)


# ── 3. Тональный скор трека ────────────────────────────────────────────────

def score_song(lyrics: str, lexicon: dict[str, int]) -> dict | None:
    """
    Вычислить метрики тональности для одного трека.
    Возвращает None, если текст слишком короткий (< 20 слов).
    """
    text   = clean_lyrics(lyrics)
    lemmas = tokenize_and_lemmatize(text)
    total  = len(lemmas)
    if total < 20:
        return None

    pos = sum(1 for l in lemmas if lexicon.get(l) ==  1)
    neg = sum(1 for l in lemmas if lexicon.get(l) == -1)
    tonal = pos + neg

    return {
        "total_words":     total,
        "pos_count":       pos,
        "neg_count":       neg,
        "tonal_count":     tonal,
        # Основной показатель: относительный перевес тональных слов
        "sentiment_ratio": (pos - neg) / total,
        # Полярность только по тональным словам
        "polarity":        (pos - neg) / tonal if tonal else 0.0,
        # Доли позитивных / негативных слов
        "pos_ratio":       pos / total,
        "neg_ratio":       neg / total,
        # Насыщенность тональными словами
        "tonal_density":   tonal / total,
    }


# ── 4. Загрузка данных ─────────────────────────────────────────────────────

def load_musicians() -> dict[int, dict]:
    """Музыканты с genius_ok=TRUE. Ключ — genius_id (int)."""
    result: dict[int, dict] = {}
    with open(MUSICIANS_FILE, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("genius_ok", "").strip().upper() != "TRUE":
                continue
            gid = int(row["genius_id"])
            result[gid] = {
                "pseudonym":    row["псевдоним"],
                "real_name":    row["реальное_имя"],
                "reloc_date":   row["дата_релокации"],
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


# ── 5. Построение DataFrame с тональностью ─────────────────────────────────

def build_df(songs: list[dict], musicians: dict[int, dict],
             lexicon: dict[str, int]) -> pd.DataFrame:
    records = []
    for s in songs:
        score = score_song(s.get("lyrics", ""), lexicon)
        if score is None:
            continue

        rdc   = s.get("release_date_components") or {}
        year  = rdc.get("year")
        month = rdc.get("month") or 1
        day   = rdc.get("day") or 1
        rel_date = f"{year}-{int(month):02d}-{int(day):02d}" if year else None

        gid  = s["artist_genius_id"]
        info = musicians[gid]
        records.append({
            "song_id":         s["song_id"],
            "title":           s["title"],
            "artist_genius_id": gid,
            "pseudonym":       info["pseudonym"],
            "country":         info["country"],
            "legal_status":    info["legal_status"],
            "period":          s["period"],
            "release_date":    rel_date,
            "reloc_date":      s.get("reloc_date"),
            **score,
        })

    df = pd.DataFrame(records)
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    return df


# ── 6. Балансировка периодов ───────────────────────────────────────────────

def balance_periods(df: pd.DataFrame) -> pd.DataFrame:
    """
    Для каждого артиста — равное N треков «до» и «после».
    N = min(кол-во до, кол-во после); из каждого периода берём N самых новых.
    """
    parts = []
    for _, grp in df.groupby("artist_genius_id"):
        after  = grp[grp["period"] == "after"].sort_values("release_date", ascending=False)
        before = grp[grp["period"] == "before"].sort_values("release_date", ascending=False)
        n = min(len(after), len(before))
        if n == 0:
            continue
        parts.extend([after.head(n), before.head(n)])
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


# ── 7. Статистика ──────────────────────────────────────────────────────────

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


def compute_results(df: pd.DataFrame, label: str) -> dict:
    """Агрегированные и пер-артистные результаты."""
    m = PRIMARY_METRIC

    bef = df[df["period"] == "before"][m].dropna().values
    aft = df[df["period"] == "after"][m].dropna().values

    overall = {
        "n_before":      len(bef),
        "n_after":       len(aft),
        "mean_before":   float(np.mean(bef)) if len(bef) else None,
        "mean_after":    float(np.mean(aft)) if len(aft) else None,
        "median_before": float(np.median(bef)) if len(bef) else None,
        "median_after":  float(np.median(aft)) if len(aft) else None,
        "cohens_d":      cohens_d(bef, aft),
        **mw_test(bef, aft),
    }

    per_artist_rows = []
    for gid, grp in df.groupby("artist_genius_id"):
        b = grp[grp["period"] == "before"][m].dropna().values
        a = grp[grp["period"] == "after"][m].dropna().values
        if len(b) == 0 or len(a) == 0:
            continue
        test = mw_test(b, a)
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
            "p_value":          test["p"],
            "significant":      test["sig"],
        })

    per_artist = pd.DataFrame(per_artist_rows)
    per_artist.to_csv(OUT_DIR / "per_artist.csv", index=False, encoding="utf-8")
    return {"overall": overall, "per_artist": per_artist}


# ── 8. Визуализации ────────────────────────────────────────────────────────

PALETTE = {"before": "#5B9BD5", "after": "#ED7D31"}
LABEL   = {"before": "До эмиграции", "after": "После эмиграции"}

plt.rcParams.update({
    "font.family":   "DejaVu Sans",
    "figure.dpi":    150,
    "savefig.dpi":   150,
    "savefig.bbox":  "tight",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})


def _sig_stars(p: float | None) -> str:
    if p is None:
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def fig1_violin(df: pd.DataFrame, res: dict) -> None:
    """Скрипичная диаграмма: сбалансированное сравнение до/после."""
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle("Тональность текстов до и после эмиграции\n(сбалансированная выборка)", fontsize=13, y=1.02)

    plot_data = df[df["period"].isin(["before", "after"])].copy()
    plot_data["Период"] = plot_data["period"].map(LABEL)
    order = [LABEL["before"], LABEL["after"]]
    pal   = {LABEL[k]: v for k, v in PALETTE.items()}

    sns.violinplot(
        data=plot_data, x="Период", y=PRIMARY_METRIC,
        hue="Период", order=order, palette=pal,
        inner="box", cut=0, ax=ax, legend=False,
    )
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel("")
    ax.set_ylabel(PRIMARY_METRIC_LABEL)

    o = res["overall"]
    d_str = f"{o['cohens_d']:.3f}" if o["cohens_d"] is not None else "—"
    ax.text(
        0.97, 0.03,
        f"p = {o['p']:.3f}  {_sig_stars(o['p'])}\nd = {d_str}",
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=9, color="#555555",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.7),
    )

    plt.tight_layout()
    plt.savefig(OUT_DIR / "1_violin_overall.png")
    plt.close()
    print("  ✓ 1_violin_overall.png")


def fig2_artist_bars(res: dict) -> None:
    """Горизонтальные бары: среднее до/после по каждому артисту."""
    pa = res["per_artist"].sort_values("mean_before").reset_index(drop=True)
    if pa.empty:
        return

    fig, ax = plt.subplots(figsize=(11, max(5, len(pa) * 0.38)))
    y = np.arange(len(pa))

    ax.barh(y - 0.2, pa["mean_before"], 0.38,
            color=PALETTE["before"], label=LABEL["before"], alpha=0.88)
    ax.barh(y + 0.2, pa["mean_after"],  0.38,
            color=PALETTE["after"],  label=LABEL["after"],  alpha=0.88)

    ax.set_yticks(y)
    ax.set_yticklabels(pa["pseudonym"], fontsize=8)
    ax.axvline(0, color="black", linewidth=0.7)
    ax.set_xlabel(PRIMARY_METRIC_LABEL)
    ax.set_title("Тональность до и после эмиграции — по артистам\n(сбалансированная выборка)", fontsize=11)
    ax.legend(loc="lower right", fontsize=9)

    # Звёздочки для статистически значимых изменений
    for i, row in pa.iterrows():
        if row.get("significant"):
            x_max = max(row["mean_before"], row["mean_after"]) + 0.003
            ax.text(x_max, i, "*", va="center", fontsize=11, color="red")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "2_artist_bars.png")
    plt.close()
    print("  ✓ 2_artist_bars.png")


def fig3_scatter(res: dict) -> None:
    """Scatter: до vs после. Точки выше диагонали — позитивнее после."""
    pa = res["per_artist"]
    if pa.empty:
        return

    fig, ax = plt.subplots(figsize=(9, 9))

    for _, row in pa.iterrows():
        c = "#E74C3C" if row.get("significant") else "#3498DB"
        ax.scatter(row["mean_before"], row["mean_after"],
                   color=c, s=70, alpha=0.85, zorder=3)
        ax.annotate(
            row["pseudonym"],
            (row["mean_before"], row["mean_after"]),
            textcoords="offset points", xytext=(5, 2),
            fontsize=7, alpha=0.9,
        )

    # Диагональ y = x
    all_vals = pd.concat([pa["mean_before"], pa["mean_after"]])
    lo, hi   = all_vals.min() - 0.01, all_vals.max() + 0.01
    ax.plot([lo, hi], [lo, hi], "k--", linewidth=1, alpha=0.45, zorder=1)

    ax.axhline(0, color="gray", linewidth=0.5, alpha=0.5)
    ax.axvline(0, color="gray", linewidth=0.5, alpha=0.5)
    ax.set_xlabel(f"Тональность ДО эмиграции")
    ax.set_ylabel(f"Тональность ПОСЛЕ эмиграции")
    ax.set_title(
        "Сдвиг тональности по артистам\n"
        "Выше диагонали = позитивнее после. Красные = статистически значимо.",
        fontsize=10,
    )

    legend_elems = [
        mpatches.Patch(color="#E74C3C", label="Значимо (p < 0.05)"),
        mpatches.Patch(color="#3498DB", label="Незначимо"),
    ]
    ax.legend(handles=legend_elems, fontsize=9)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "3_scatter_before_after.png")
    plt.close()
    print("  ✓ 3_scatter_before_after.png")


def fig4_kde(df: pd.DataFrame) -> None:
    """KDE: распределения тональности в двух периодах."""
    fig, ax = plt.subplots(figsize=(10, 5))

    for period in ("before", "after"):
        vals = df[df["period"] == period][PRIMARY_METRIC].dropna()
        vals.plot.kde(ax=ax, label=LABEL[period], color=PALETTE[period], linewidth=2)
        ax.axvline(vals.median(), color=PALETTE[period],
                   linestyle=":", linewidth=1, alpha=0.7)

    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.set_xlabel(PRIMARY_METRIC_LABEL)
    ax.set_ylabel("Плотность вероятности")
    ax.set_title("Распределение тональности текстов до и после эмиграции", fontsize=12)
    ax.legend(fontsize=10)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "4_kde_distribution.png")
    plt.close()
    print("  ✓ 4_kde_distribution.png")


def fig5_delta(res: dict) -> None:
    """Дельта-диаграмма: изменение тональности, отсортированное."""
    pa = res["per_artist"].sort_values("delta").reset_index(drop=True)
    if pa.empty:
        return

    colors = ["#E74C3C" if d < 0 else "#27AE60" for d in pa["delta"]]
    fig, ax = plt.subplots(figsize=(10, max(5, len(pa) * 0.38)))

    ax.barh(pa["pseudonym"], pa["delta"], color=colors, alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Δ тональность  (после − до)")
    ax.set_title(
        "Изменение тональности после эмиграции (сбалансированная выборка)\n"
        "Зелёный = позитивнее, красный = негативнее. * — значимо (p < 0.05)",
        fontsize=10,
    )

    for i, row in pa.iterrows():
        if row.get("significant"):
            x = row["delta"]
            offset = 0.002 if x >= 0 else -0.002
            ax.text(x + offset, i, "*",
                    ha="left" if x >= 0 else "right",
                    va="center", fontsize=12)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "5_delta.png")
    plt.close()
    print("  ✓ 5_delta.png")


def fig6_timeline(df: pd.DataFrame) -> None:
    """Временной ряд: календарное деление до/с 2022, итог в точке 2022."""
    before, after = build_timeline_series(df, PRIMARY_METRIC)

    fig, ax = plt.subplots(figsize=(12, 5))

    if not before.empty:
        regular = before[~before["is_summary"]]
        summary = before[before["is_summary"]]
        if not regular.empty:
            ax.plot(regular["year"], regular["mean"],
                    marker="o", color=PALETTE["before"],
                    label=LABEL["before"], linewidth=2.2)
            ax.fill_between(regular["year"],
                            regular["mean"] - regular["sem"],
                            regular["mean"] + regular["sem"],
                            alpha=0.18, color=PALETTE["before"])
        if not summary.empty:
            ax.plot(summary["year"], summary["mean"],
                    marker="s", markersize=8, color=PALETTE["before"],
                    label=f"{LABEL['before']} (итог)", linewidth=2.2, linestyle="--")

    if not after.empty:
        ax.plot(after["year"], after["mean"],
                marker="o", color=PALETTE["after"],
                label=LABEL["after"], linewidth=2.2)
        ax.fill_between(after["year"],
                        after["mean"] - after["sem"],
                        after["mean"] + after["sem"],
                        alpha=0.18, color=PALETTE["after"])

    ax.axvline(2022, color="black", linewidth=1.2, linestyle=":", alpha=0.7)
    ax.text(2022.1, ax.get_ylim()[1] * 0.97, "2022",
            fontsize=8, va="top", color="black", alpha=0.7)
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.set_xlabel("Год выпуска трека")
    ax.set_ylabel(PRIMARY_METRIC_LABEL)
    ax.set_title(
        "Динамика тональности по годам (±SEM, треки ≥ 3 в год; до 2022 / с 2022)",
        fontsize=12,
    )
    ax.legend(fontsize=9)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))

    plt.tight_layout()
    plt.savefig(OUT_DIR / "6_timeline.png")
    plt.close()
    print("  ✓ 6_timeline.png")


def fig7_heatmap(df: pd.DataFrame) -> None:
    """Тепловая карта: артист × метрика × период."""
    metrics = {
        "sentiment_ratio": "Индекс тональности",
        "pos_ratio":       "Доля позитивных слов",
        "neg_ratio":       "Доля негативных слов",
        "tonal_density":   "Тональная насыщенность",
    }

    pivot_rows = []
    for gid, grp in df.groupby("artist_genius_id"):
        row = {"Артист": grp["pseudonym"].iloc[0]}
        for col, _ in metrics.items():
            for period, suffix in [("before", " до"), ("after", " после")]:
                vals = grp[grp["period"] == period][col].dropna()
                row[f"{col}{suffix}"] = float(vals.mean()) if len(vals) else np.nan
        pivot_rows.append(row)

    pivot = pd.DataFrame(pivot_rows).set_index("Артист").sort_index()

    # Только sentiment_ratio для наглядности
    cols_sr = ["sentiment_ratio до", "sentiment_ratio после"]
    hm_data = pivot[cols_sr].rename(columns={
        "sentiment_ratio до":    "До",
        "sentiment_ratio после": "После",
    })

    fig, ax = plt.subplots(figsize=(5, max(6, len(hm_data) * 0.38)))
    sns.heatmap(
        hm_data, annot=True, fmt=".3f", cmap="RdYlGn",
        center=0, linewidths=0.4, ax=ax,
        cbar_kws={"label": "Индекс тональности"},
    )
    ax.set_title("Средний индекс тональности по артистам (сбалансированная выборка)", fontsize=11)
    ax.set_xlabel("")
    ax.set_ylabel("")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "7_heatmap.png")
    plt.close()
    print("  ✓ 7_heatmap.png")


# ── 9. Главная функция ─────────────────────────────────────────────────────

def main() -> None:

    print("=" * 60)
    print("  Лексический анализ тональности")
    print("=" * 60)

    # Словарь
    print("\n[1/5] Загружаю RuSentiLex …")
    lexicon = load_rusentilex()
    print(f"      Слов в словаре: {len(lexicon):,}")

    # Данные
    print("[2/5] Загружаю данные …")
    musicians = load_musicians()
    print(f"      Музыкантов (genius_ok=TRUE): {len(musicians)}")
    songs = load_songs(set(musicians.keys()))
    print(f"      Треков с текстами: {len(songs):,}")

    # Тональность (полный скоринг → сбалансированная выборка)
    print("[3/5] Вычисляю тональность треков …")
    df_full = build_df(songs, musicians, lexicon)
    df = balance_periods(df_full)
    n_before = (df["period"] == "before").sum()
    n_after  = (df["period"] == "after").sum()
    print(f"      Сбалансированная выборка: {len(df):,} треков "
          f"({n_before:,} до / {n_after:,} после)")
    print(f"      Артистов: {df['artist_genius_id'].nunique()}")

    df.to_csv(OUT_DIR / "sentiment_scores.csv", index=False, encoding="utf-8")

    # Статистика
    print("[4/5] Статистика …")
    res = compute_results(df, "balanced")

    o = res["overall"]
    print(f"\n      mean до:    {o['mean_before']:+.4f}")
    print(f"      mean после: {o['mean_after']:+.4f}")
    print(f"      Cohen's d:  {o['cohens_d']:+.4f}")
    print(f"      p-value:    {o['p']:.4f}  {_sig_stars(o['p'])}")

    # Визуализации
    print("\n[5/5] Создаю визуализации …")
    fig1_violin(df, res)
    fig2_artist_bars(res)
    fig3_scatter(res)
    fig4_kde(df)
    fig5_delta(res)
    fig6_timeline(df)
    fig7_heatmap(df)

    print(f"\nВсе файлы сохранены в: {OUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
