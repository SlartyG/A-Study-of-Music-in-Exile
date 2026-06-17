#!/usr/bin/env python3
"""
Метод 2: Тематическое моделирование (LDA).

Алгоритм:
  1. Загрузить тексты треков (те же фильтры, что в методе 1).
  2. Очистить, токенизировать, удалить стоп-слова.
  3. Обучить LDA (sklearn) на полном корпусе.
  4. Присвоить каждому треку доминирующую тему и вектор распределения.
  5. Сравнить тематический состав периодов «до» и «после»:
       A. Balanced — равное N треков на артиста.
       B. All      — все имеющиеся.
  6. Визуализировать результаты (9 графиков).
  7. Сохранить CSV с тематическими распределениями.

Запуск:
    python3 analysis/topic_modeling.py
"""

import csv
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from wordcloud import WordCloud

# ── Пути ────────────────────────────────────────────────────────────────────

BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_DIR       = BASE_DIR / "data"
SONGS_FILE     = DATA_DIR / "songs.jsonl"
MUSICIANS_FILE = DATA_DIR / "sample_musicians.csv"
OUT_DIR        = BASE_DIR / "analysis" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Параметры LDA ────────────────────────────────────────────────────────────

N_TOPICS        = 10      # число тем; можно менять
N_TOP_WORDS     = 15      # топ-слов на тему для отображения
MAX_ITER        = 30
RANDOM_STATE    = 42
MIN_DOC_FREQ    = 3       # слово должно встречаться хотя бы в N документах
MAX_DF_RATIO    = 0.90    # игнорировать слова, встречающиеся в >90% текстов
MIN_WORDS       = 20      # минимум слов в треке

# ── Русские стоп-слова ───────────────────────────────────────────────────────

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
    "хоть","после","над","больше","тот","через","эти","нас","про","него","какая",
    "этой","этих","которые","свой","своей","всё","её","тем","кого","что",
    "это","это","да","нет","ой","эй","ах","ух","мм","эм","хм","ля","бла",
    "ну","вот","просто","очень","чтоли","типа","ещё","уже","всегда","никогда",
    "между","перед","лишь","лучше","хорошо","плохо","три","четыре","пять",
    "был","была","были","буду","будешь","будем","будете","будут","быть",
    "стал","стала","стали","стать","стану","станет",
    "моя","твоя","наша","ваша","моё","твоё",
    "всей","всём","весь","вся","всю",
    "меня","тебе","тебя","нам","им","них","ней",
    "которой","которого","которых","которым","которому",
    "сказал","сказала","говорит","говорил",
}


# ── Очистка текста ───────────────────────────────────────────────────────────

_SECTION_RE  = re.compile(r"\[.*?\]")
_CONTRIB_RE  = re.compile(r"^\d+\s+Contributors?\s*.+?Lyrics\s*", re.DOTALL)
_CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]{3,}")   # минимум 3 буквы


def clean_and_tokenize(text: str) -> list[str]:
    text = _CONTRIB_RE.sub("", text, count=1)
    text = _SECTION_RE.sub(" ", text)
    words = _CYRILLIC_RE.findall(text.lower())
    return [w for w in words if w not in STOPWORDS]


def doc_string(text: str) -> str:
    return " ".join(clean_and_tokenize(text))


# ── Загрузка данных ──────────────────────────────────────────────────────────

def load_musicians() -> dict[int, dict]:
    result: dict[int, dict] = {}
    with open(MUSICIANS_FILE, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("genius_ok", "").strip().upper() != "TRUE":
                continue
            gid = int(row["genius_id"])
            result[gid] = {
                "pseudonym":  row["псевдоним"],
                "country":    row["страна_релокации"],
                "reloc_date": row["дата_релокации"],
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


def build_records(songs: list[dict], musicians: dict[int, dict]) -> pd.DataFrame:
    rows = []
    for s in songs:
        doc = doc_string(s.get("lyrics", ""))
        if len(doc.split()) < MIN_WORDS:
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
            "period":           s["period"],
            "release_date":     rel_date,
            "doc":              doc,
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


# ── LDA ──────────────────────────────────────────────────────────────────────

def fit_lda(docs: list[str]) -> tuple[LatentDirichletAllocation, CountVectorizer, np.ndarray]:
    """Обучить LDA. Возвращает модель, векторайзер и матрицу doc-topic."""
    vec = CountVectorizer(
        min_df=MIN_DOC_FREQ,
        max_df=MAX_DF_RATIO,
        max_features=8000,
        token_pattern=r"[а-яё]{3,}",
    )
    dtm = vec.fit_transform(docs)

    lda = LatentDirichletAllocation(
        n_components=N_TOPICS,
        max_iter=MAX_ITER,
        learning_method="online",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    doc_topic = lda.fit_transform(dtm)
    return lda, vec, doc_topic


def get_top_words(lda: LatentDirichletAllocation, vec: CountVectorizer,
                  n: int = N_TOP_WORDS) -> list[list[str]]:
    feature_names = vec.get_feature_names_out()
    topics = []
    for comp in lda.components_:
        idx = comp.argsort()[::-1][:n]
        topics.append([feature_names[i] for i in idx])
    return topics


def topic_label(words: list[str], n: int = 4) -> str:
    return " / ".join(words[:n])


# ── Статистика ───────────────────────────────────────────────────────────────

def topic_prevalence(df: pd.DataFrame) -> pd.DataFrame:
    """Средняя доля каждой темы в каждом периоде."""
    topic_cols = [c for c in df.columns if c.startswith("topic_")]
    result = (
        df.groupby("period")[topic_cols]
        .mean()
        .T
        .rename(columns={"before": "mean_before", "after": "mean_after"})
        .reset_index()
        .rename(columns={"index": "topic"})
    )
    result["delta"] = result["mean_after"] - result["mean_before"]
    return result


def chi2_topic_shift(df: pd.DataFrame) -> dict:
    """
    Хи-квадрат тест: отличается ли распределение доминирующих тем
    между периодами?
    """
    topic_cols = [c for c in df.columns if c.startswith("topic_")]
    before = df[df["period"] == "before"]["dominant_topic"].value_counts()
    after  = df[df["period"] == "after"]["dominant_topic"].value_counts()
    all_topics = sorted(set(before.index) | set(after.index))
    b_arr = np.array([before.get(t, 0) for t in all_topics])
    a_arr = np.array([after.get(t, 0) for t in all_topics])
    # contingency table
    table = np.vstack([b_arr, a_arr])
    chi2, p, dof, _ = stats.chi2_contingency(table)
    return {"chi2": chi2, "p": p, "dof": dof}


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


def fig1_top_words(top_words: list[list[str]], labels: list[str]) -> None:
    """Топ-слова каждой темы — горизонтальные бары."""
    n   = len(top_words)
    cols = min(5, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.5, rows * 3))
    axes = np.array(axes).flatten()

    for i, (words, label) in enumerate(zip(top_words, labels)):
        ax = axes[i]
        # Условные «веса» для отображения (убывающие)
        weights = np.linspace(1, 0.3, len(words))
        ax.barh(range(len(words))[::-1], weights, color="#4472C4", alpha=0.75)
        ax.set_yticks(range(len(words))[::-1])
        ax.set_yticklabels(words, fontsize=8)
        ax.set_title(f"Тема {i+1}\n{label}", fontsize=8, pad=3)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)

    for ax in axes[n:]:
        ax.set_visible(False)

    fig.suptitle("Тематическая структура корпуса — топ-слова", fontsize=13, y=1.01)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_1_topic_words.png")
    plt.close()
    print("  ✓ tm_1_topic_words.png")


def fig2_prevalence_bars(prevalence: pd.DataFrame, labels: list[str]) -> None:
    """Средняя доля каждой темы до/после."""
    x  = np.arange(len(prevalence))
    w  = 0.38
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(x - w/2, prevalence["mean_before"], w,
           label=LABEL["before"], color=PALETTE["before"], alpha=0.88)
    ax.bar(x + w/2, prevalence["mean_after"], w,
           label=LABEL["after"],  color=PALETTE["after"],  alpha=0.88)

    short_labels = [f"Т{i+1}: {lab[:20]}…" if len(lab) > 20 else f"Т{i+1}: {lab}"
                    for i, lab in enumerate(labels)]
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Средняя доля темы в треке")
    ax.set_title("Тематическое распределение до и после эмиграции", fontsize=12)
    ax.legend(fontsize=10)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_2_topic_prevalence.png")
    plt.close()
    print("  ✓ tm_2_topic_prevalence.png")


def fig3_delta_topics(prevalence: pd.DataFrame, labels: list[str]) -> None:
    """Изменение доли каждой темы (после − до)."""
    pv = prevalence.copy()
    pv["label"] = [f"Т{i+1}: {lab[:22]}" for i, lab in enumerate(labels)]
    pv = pv.sort_values("delta")
    colors = ["#E74C3C" if d < 0 else "#27AE60" for d in pv["delta"]]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(pv["label"], pv["delta"], color=colors, alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Δ средняя доля темы (после − до)")
    ax.set_title(
        "Изменение тематического состава после эмиграции\n"
        "Зелёный = тема стала популярнее, красный = реже",
        fontsize=10,
    )
    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_3_topic_delta.png")
    plt.close()
    print("  ✓ tm_3_topic_delta.png")


def fig4_dominant_topic_dist(df: pd.DataFrame, labels: list[str]) -> None:
    """Доля треков с каждой доминирующей темой — столбчатые диаграммы."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=False)

    for ax, (period, title) in zip(axes, [
        ("before", LABEL["before"]),
        ("after",  LABEL["after"]),
    ]):
        sub = df[df["period"] == period]["dominant_topic"].value_counts().sort_index()
        bars = ax.bar(
            [f"Т{i+1}" for i in sub.index],
            sub.values,
            color=PALETTE[period], alpha=0.85,
        )
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Тема")
        ax.set_ylabel("Число треков")

        # Подписи
        for bar, idx in zip(bars, sub.index):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + 0.5,
                    f"Т{idx+1}",
                    ha="center", va="bottom", fontsize=7)

    fig.suptitle("Распределение доминирующих тем по периодам", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_4_dominant_dist.png")
    plt.close()
    print("  ✓ tm_4_dominant_dist.png")


def fig5_artist_heatmap(df: pd.DataFrame, labels: list[str], period: str) -> None:
    """Тепловая карта: артист × доля каждой темы (один период)."""
    topic_cols = [c for c in df.columns if c.startswith("topic_")]
    sub = df[df["period"] == period].groupby("pseudonym")[topic_cols].mean()
    if sub.empty:
        return

    sub.columns = [f"Т{i+1}" for i in range(len(topic_cols))]

    fig, ax = plt.subplots(figsize=(max(8, len(topic_cols) * 0.9),
                                    max(5, len(sub) * 0.4)))
    sns.heatmap(
        sub, annot=True, fmt=".2f", cmap="YlOrRd",
        linewidths=0.3, ax=ax,
        cbar_kws={"label": "Средняя доля темы"},
    )
    period_label = LABEL[period]
    ax.set_title(f"Тематический профиль артистов — {period_label}", fontsize=11)
    ax.set_xlabel("Тема")
    ax.set_ylabel("")

    plt.tight_layout()
    fn = f"tm_5_artist_heatmap_{period}.png"
    plt.savefig(OUT_DIR / fn)
    plt.close()
    print(f"  ✓ {fn}")


def fig6_topic_shift_scatter(df: pd.DataFrame, labels: list[str]) -> None:
    """
    Scatter per-artist: насколько изменился тематический профиль?
    Ось X — расстояние Йенсена–Шэннона между распределением тем до/после.
    Ось Y — разница доминирующей темы (смена ≠ 0).
    """
    from scipy.spatial.distance import jensenshannon

    topic_cols = [c for c in df.columns if c.startswith("topic_")]
    rows = []
    for gid, grp in df.groupby("artist_genius_id"):
        b = grp[grp["period"] == "before"][topic_cols].mean().values.copy().astype(float)
        a = grp[grp["period"] == "after"][topic_cols].mean().values.copy().astype(float)
        if np.all(b == 0) or np.all(a == 0):
            continue
        # нормализовать в распределения
        b /= b.sum() + 1e-9
        a /= a.sum() + 1e-9
        jsd = float(jensenshannon(b, a))
        dom_b = int(np.argmax(b))
        dom_a = int(np.argmax(a))
        rows.append({
            "pseudonym": grp["pseudonym"].iloc[0],
            "jsd":       jsd,
            "dom_before": dom_b,
            "dom_after":  dom_a,
            "topic_changed": dom_b != dom_a,
        })

    if not rows:
        return

    pa = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(10, 7))
    for _, row in pa.iterrows():
        color = "#E74C3C" if row["topic_changed"] else "#3498DB"
        ax.scatter(row["jsd"], 0, color=color, s=80, alpha=0.7)   # placeholder
    ax.cla()

    for _, row in pa.iterrows():
        color = "#E74C3C" if row["topic_changed"] else "#3498DB"
        ax.scatter(row["jsd"], row["dom_after"] - row["dom_before"],
                   color=color, s=70, alpha=0.85, zorder=3)
        ax.annotate(row["pseudonym"],
                    (row["jsd"], row["dom_after"] - row["dom_before"]),
                    textcoords="offset points", xytext=(4, 2), fontsize=7)

    ax.axhline(0, color="gray", linewidth=0.6, linestyle="--")
    ax.axvline(0, color="gray", linewidth=0.6, linestyle="--")
    ax.set_xlabel("Расстояние Дженсена–Шэннона\n(0 = идентичный тематический профиль)")
    ax.set_ylabel("Сдвиг доминирующей темы (индекс «после» − «до»)")
    ax.set_title(
        "Тематический сдвиг по артистам\nКрасные = смена доминирующей темы",
        fontsize=11,
    )
    import matplotlib.patches as mpatches
    legend_elems = [
        mpatches.Patch(color="#E74C3C", label="Доминирующая тема изменилась"),
        mpatches.Patch(color="#3498DB", label="Доминирующая тема та же"),
    ]
    ax.legend(handles=legend_elems, fontsize=9)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_6_topic_shift_scatter.png")
    plt.close()
    print("  ✓ tm_6_topic_shift_scatter.png")


def fig7_wordclouds(top_words: list[list[str]], labels: list[str]) -> None:
    """Облака слов для каждой темы (2 × 5 или 2 × 4)."""
    n    = len(top_words)
    cols = min(5, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 2.5))
    axes = np.array(axes).flatten()

    for i, (words, label) in enumerate(zip(top_words, labels)):
        freq = {w: (N_TOP_WORDS - j) for j, w in enumerate(words)}
        wc = WordCloud(
            width=400, height=250,
            background_color="white",
            colormap="Blues",
            prefer_horizontal=0.8,
            font_path=None,
            max_words=N_TOP_WORDS,
        ).generate_from_frequencies(freq)
        axes[i].imshow(wc, interpolation="bilinear")
        axes[i].axis("off")
        axes[i].set_title(f"Тема {i+1}: {label[:28]}", fontsize=8, pad=3)

    for ax in axes[n:]:
        ax.set_visible(False)

    fig.suptitle("Облака слов тем", fontsize=13, y=1.01)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_7_wordclouds.png")
    plt.close()
    print("  ✓ tm_7_wordclouds.png")


def fig8_stacked_periods(df: pd.DataFrame, labels: list[str]) -> None:
    """Stacked bar: состав периода «до» и «после» по темам."""
    topic_cols = [c for c in df.columns if c.startswith("topic_")]
    agg = df.groupby("period")[topic_cols].mean()
    # Нормализовать в доли
    agg = agg.div(agg.sum(axis=1), axis=0)

    cmap   = matplotlib.colormaps.get_cmap("tab10")
    colors = [cmap(i / N_TOPICS) for i in range(N_TOPICS)]

    fig, ax = plt.subplots(figsize=(7, 5))
    bottom = np.zeros(2)
    period_order = ["before", "after"]
    xtick_labels = [LABEL[p] for p in period_order]

    for i, col in enumerate(topic_cols):
        vals = [agg.loc[p, col] if p in agg.index else 0 for p in period_order]
        ax.bar(xtick_labels, vals, bottom=bottom,
               color=colors[i], label=f"Т{i+1}: {labels[i][:20]}", alpha=0.88)
        bottom += np.array(vals)

    ax.set_ylabel("Доля темы в корпусе")
    ax.set_title("Тематическая структура периодов", fontsize=12)
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=7)
    ax.set_ylim(0, 1.01)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_8_stacked_periods.png")
    plt.close()
    print("  ✓ tm_8_stacked_periods.png")


def fig9_timeline(df: pd.DataFrame) -> None:
    """Доля доминирующей темы №1 по годам — временной ряд."""
    df2 = df.copy()
    df2["year"] = df2["release_date"].dt.year
    topic_cols  = [c for c in df2.columns if c.startswith("topic_")]

    # Берём топ-3 темы по суммарной доле в «после»
    after_mean = df2[df2["period"] == "after"][topic_cols].mean().sort_values(ascending=False)
    top3 = list(after_mean.index[:3])

    agg = (
        df2.groupby(["year", "period"])[top3]
        .mean()
        .reset_index()
    )
    agg = agg[(agg["year"] >= 2014) & (agg["year"] <= 2026)]

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    cmap = matplotlib.colormaps.get_cmap("tab10")

    for ax, col in zip(axes, top3):
        topic_idx = topic_cols.index(col)
        for period in ("before", "after"):
            sub = agg[agg["period"] == period].sort_values("year")
            if sub.empty:
                continue
            ax.plot(sub["year"], sub[col], marker="o",
                    color=PALETTE[period], label=LABEL[period], linewidth=2)
        ax.axvline(2022, color="black", linewidth=1, linestyle=":", alpha=0.6)
        ax.set_ylabel("Средняя доля")
        ax.set_title(f"Тема {topic_idx + 1}", fontsize=9)
        ax.legend(fontsize=8)
        ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1))

    axes[-1].set_xlabel("Год выпуска")
    fig.suptitle("Динамика топ-3 тем по годам", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "tm_9_timeline_topics.png")
    plt.close()
    print("  ✓ tm_9_timeline_topics.png")


# ── Главная функция ──────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Тематическое моделирование (LDA)")
    print("=" * 60)

    # Данные
    print("\n[1/5] Загружаю данные …")
    musicians = load_musicians()
    songs     = load_songs(set(musicians.keys()))
    print(f"      Музыкантов: {len(musicians)}, треков: {len(songs):,}")

    df = build_records(songs, musicians)
    df = balance_periods(df)
    print(f"      Сбалансированная выборка: {len(df):,} треков")
    print(f"      до/после: {df['period'].value_counts().to_dict()}")

    # LDA на сбалансированном корпусе
    print(f"\n[2/5] Обучаю LDA (K={N_TOPICS}, iter={MAX_ITER}) …")
    docs = df["doc"].tolist()
    lda, vec, doc_topic = fit_lda(docs)
    print(f"      Словарь TF-IDF: {len(vec.get_feature_names_out()):,} слов")
    print(f"      Perplexity: {lda.perplexity(vec.transform(docs)):.1f}")

    # Добавить топики в df_bal
    for i in range(N_TOPICS):
        df[f"topic_{i}"] = doc_topic[:, i]
    df["dominant_topic"] = doc_topic.argmax(axis=1)

    top_words = get_top_words(lda, vec)
    labels    = [topic_label(w) for w in top_words]

    print("\n  Топ-слова тем:")
    for i, (w, lb) in enumerate(zip(top_words, labels)):
        print(f"    Тема {i+1:2d}: {lb}")

    # Статистика
    print("\n[3/5] Статистика …")
    prevalence = topic_prevalence(df)

    chi = chi2_topic_shift(df)
    print(f"\n  χ² тест на сдвиг распределения тем:")
    print(f"    χ² = {chi['chi2']:.2f},  df = {chi['dof']},  p = {chi['p']:.4f}")
    sig = "значимо *" if chi["p"] < 0.05 else "n.s."
    print(f"    → {sig}")

    print("\n  Изменение долей тем (после − до):")
    for _, row in prevalence.sort_values("delta", ascending=False).iterrows():
        idx = int(row["topic"].replace("topic_", ""))
        arrow = "↑" if row["delta"] > 0 else "↓"
        print(f"    Тема {idx+1:2d} {arrow}  Δ = {row['delta']:+.4f}  ({labels[idx]})")

    # Сохранить CSV
    save_cols = ["song_id", "title", "pseudonym", "period", "release_date",
                 "dominant_topic"] + [f"topic_{i}" for i in range(N_TOPICS)]
    df[save_cols].to_csv(OUT_DIR / "topic_scores.csv", index=False, encoding="utf-8")
    prevalence.to_csv(OUT_DIR / "topic_prevalence.csv", index=False, encoding="utf-8")

    # Топ-слова
    with open(OUT_DIR / "topic_top_words.txt", "w", encoding="utf-8") as fh:
        for i, words in enumerate(top_words):
            fh.write(f"Тема {i+1}: {labels[i]}\n")
            fh.write("  " + ", ".join(words) + "\n\n")

    # Визуализации
    print("\n[4/5] Создаю визуализации …")
    fig1_top_words(top_words, labels)
    fig2_prevalence_bars(prevalence, labels)
    fig3_delta_topics(prevalence, labels)
    fig4_dominant_topic_dist(df, labels)
    fig5_artist_heatmap(df, labels, "before")
    fig5_artist_heatmap(df, labels, "after")
    fig6_topic_shift_scatter(df, labels)
    fig7_wordclouds(top_words, labels)
    fig8_stacked_periods(df, labels)
    fig9_timeline(df)

    print(f"\n[5/5] Все файлы сохранены в: {OUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
