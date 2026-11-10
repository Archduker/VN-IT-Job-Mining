"""Descriptive EDA over the selected staging frame; no imputation or disk writes."""

import numpy as np
import pandas as pd


def _count_skills(value):
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return len([item for item in value if str(item).strip()])
    if value is None or pd.isna(value):
        return np.nan
    text = str(value).strip()
    return len([item for item in text.split(",") if item.strip()]) if text else np.nan


def exploration(frame, cities):
    def numeric(column):
        values = frame[column] if column in frame else pd.Series(index=frame.index, dtype=float)
        return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)

    salary = pd.concat([numeric("salary_min_vnd"), numeric("salary_max_vnd")], axis=1)
    salary = salary.where(salary > 0).mean(axis=1) / 1e6
    skill_column = next((c for c in ("skills_std", "skills_clean", "skills_list") if c in frame), None)
    skill_count = (frame[skill_column].map(_count_skills).astype(float)
                   if skill_column else pd.Series(np.nan, index=frame.index))
    description_column = next((c for c in ("description_clean", "raw_description_text") if c in frame), None)
    description_words = (frame[description_column].map(
        lambda value: len(str(value).split()) if pd.notna(value) and str(value).strip() else np.nan
    ).astype(float) if description_column else pd.Series(np.nan, index=frame.index))
    exp_min = numeric("exp_min_years").where(lambda s: s >= 0)
    numeric_frame = pd.DataFrame({
        "Lương min (triệu VND)": numeric("salary_min_vnd").where(lambda s: s > 0) / 1e6,
        "Lương max (triệu VND)": numeric("salary_max_vnd").where(lambda s: s > 0) / 1e6,
        "Lương giữa (triệu VND)": salary,
        "Kinh nghiệm min (năm)": exp_min,
        "Kinh nghiệm max (năm)": numeric("exp_max_years").where(lambda s: s >= 0),
        "Số lượng tuyển": numeric("headcount").where(lambda s: s > 0),
        "Số kỹ năng nhận diện": skill_count,
        "Độ dài mô tả (số từ)": description_words,
    })
    pairs = numeric_frame[["Kinh nghiệm min (năm)", "Lương giữa (triệu VND)"]].dropna()
    scatter = [{"experience": float(row.iloc[0]), "salary": float(row.iloc[1])}
               for _, row in pairs.head(1000).iterrows()]
    boxes = []
    for label in cities.value_counts().head(8).index:
        values = salary[cities.eq(label).fillna(False)].dropna()
        if len(values) < 4:
            continue
        q1, median, q3 = values.quantile([.25, .5, .75])
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        inside = values[values.between(lower, upper)]
        boxes.append({"label": str(label), "count": len(values),
                      "q1": float(q1), "median": float(median), "q3": float(q3),
                      "low": float(inside.min()), "high": float(inside.max()),
                      "lower_fence": float(lower), "upper_fence": float(upper),
                      "outliers": int((~values.between(lower, upper)).sum())})
    salary_counts = salary.dropna().value_counts().sort_index()
    cumulative = salary_counts.cumsum() / salary_counts.sum() * 100 if len(salary_counts) else salary_counts
    curve = [{"salary": float(k), "cumulative_pct": float(v)} for k, v in cumulative.items()]
    correlation = []
    for x in numeric_frame:
        for y in numeric_frame:
            pair = numeric_frame[[x, y]].dropna() if x != y else numeric_frame[[x]].dropna()
            count = len(pair)
            value = None
            if count >= 3 and all(pair[c].nunique() > 1 for c in pair):
                value = float(pair.iloc[:, 0].corr(pair.iloc[:, -1]))
            correlation.append({"x": x, "y": y, "value": value, "count": count})
    heatmap = []
    if "seniority" in frame:
        levels = frame["seniority"].astype("string").str.strip().replace("", pd.NA)
        top_levels = levels.value_counts().head(6).index
        for city in cities.value_counts().head(8).index:
            for level in top_levels:
                heatmap.append({"x": str(level), "y": str(city),
                                "value": int((cities.eq(city) & levels.eq(level)).fillna(False).sum())})
    return {"scatter": scatter, "scatter_total": len(pairs), "scatter_limit": 1000,
            "boxes": boxes, "salary_curve": curve, "correlation": correlation,
            "heatmap": heatmap}
