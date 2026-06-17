"""
Календарная логика для графиков timeline.

До 2022 года (год выпуска < 2022) → «до»; с 2022 → «после».
В точке 2022: синяя линия — итог всего периода «до», оранжевая — среднее за 2022.
"""

from __future__ import annotations

import pandas as pd

PIVOT_YEAR = 2022


def _agg_series(vals: pd.Series, min_count: int) -> dict | None:
    if len(vals) < min_count:
        return None
    return {
        "mean":  float(vals.mean()),
        "sem":   float(vals.sem()),
        "count": int(len(vals)),
    }


def build_timeline_series(
    df: pd.DataFrame,
    metric: str,
    *,
    min_count: int = 3,
    year_min: int = 2014,
    year_max: int = 2026,
    pivot: int = PIVOT_YEAR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
  Вернуть (before_df, after_df) для построения timeline.

  before: годовые точки < pivot; в pivot — итог всех треков с годом < pivot.
  after: годовые точки >= pivot.
    """
    df2 = df.dropna(subset=[metric, "release_date"]).copy()
    df2["year"] = pd.to_datetime(df2["release_date"]).dt.year
    df2 = df2[(df2["year"] >= year_min) & (df2["year"] <= year_max)]

    before_rows: list[dict] = []
    after_rows: list[dict] = []

    for y in range(year_min, pivot):
        stats = _agg_series(df2.loc[df2["year"] == y, metric], min_count)
        if stats:
            before_rows.append({"year": y, "is_summary": False, **stats})

    pre = df2.loc[df2["year"] < pivot, metric]
    stats = _agg_series(pre, min_count)
    if stats:
        before_rows.append({"year": pivot, "is_summary": True, **stats})

    for y in range(pivot, year_max + 1):
        stats = _agg_series(df2.loc[df2["year"] == y, metric], min_count)
        if stats:
            after_rows.append({"year": y, "is_summary": False, **stats})

    return pd.DataFrame(before_rows), pd.DataFrame(after_rows)
