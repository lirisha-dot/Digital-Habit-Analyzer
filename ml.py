"""Machine-learning module: K-Means Clustering + Decision Tree."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, silhouette_score

LEISURE = {"Social Media", "Entertainment", "Gaming"}
PRODUCTIVE = {"Education", "Productivity"}
FEATURES = ["total", "leisure", "productive", "night"]
LABELS = ["Healthy", "Moderate", "Unhealthy"]


def daily_features(df):
    """One row per day: total, leisure, productive and night minutes."""
    if df.empty:
        return pd.DataFrame(columns=FEATURES)
    d = df.copy()
    d["day"] = d["activity_date"].dt.date
    g = pd.DataFrame({
        "total": d.groupby("day")["duration_min"].sum(),
        "leisure": d[d["category"].isin(LEISURE)].groupby("day")["duration_min"].sum(),
        "productive": d[d["category"].isin(PRODUCTIVE)].groupby("day")["duration_min"].sum(),
        "night": d[d["time_slot"] == "Night"].groupby("day")["duration_min"].sum(),
    }).fillna(0).astype(int)
    return g.sort_index()


# ------------------------------------------------------------------
# ALGORITHM 1 : K-MEANS CLUSTERING  (groups days into habit patterns)
# ------------------------------------------------------------------
def run_kmeans(feat):
    n = len(feat)
    if n < 4:
        return None
    k = 3 if n >= 9 else 2
    X = StandardScaler().fit_transform(feat[FEATURES])
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)

    f = feat.copy()
    f["cluster"] = km.labels_
    # name clusters: lowest (leisure + night) = most productive
    score = (f.groupby("cluster")["leisure"].mean() + f.groupby("cluster")["night"].mean()).sort_values()
    names = ["Productive Days", "Balanced Days", "Distracted Days"] if k == 3 else ["Balanced Days", "Distracted Days"]
    mapping = {c: names[i] for i, c in enumerate(score.index)}
    f["pattern"] = f["cluster"].map(mapping)

    try:
        sil = round(float(silhouette_score(X, km.labels_)), 3)
    except Exception:
        sil = None

    summary = []
    for name in names:
        sub = f[f["pattern"] == name]
        if sub.empty:
            continue
        summary.append({
            "pattern": name, "days": int(len(sub)),
            "total": int(sub["total"].mean()), "leisure": int(sub["leisure"].mean()),
            "productive": int(sub["productive"].mean()), "night": int(sub["night"].mean()),
        })
    days = [{"date": str(i), "pattern": r["pattern"], "total": int(r["total"]),
             "leisure": int(r["leisure"]), "productive": int(r["productive"]), "night": int(r["night"])}
            for i, r in f.iterrows()]
    return {"k": k, "silhouette": sil, "summary": summary, "days": days}


# ------------------------------------------------------------------
# ALGORITHM 2 : DECISION TREE  (classifies a day as Healthy / Moderate / Unhealthy)
# ------------------------------------------------------------------
def rule_label(total, leisure, night):
    """Digital-wellbeing guideline used to label training data (0=Healthy,1=Moderate,2=Unhealthy)."""
    s = 2 if total > 360 else 1 if total > 240 else 0
    s += 2 if leisure > 180 else 1 if leisure > 90 else 0
    s += 2 if night > 120 else 1 if night > 60 else 0
    return 0 if s <= 1 else 1 if s <= 3 else 2


def _baseline_data(n=600, seed=42):
    rng = np.random.default_rng(seed)
    total = rng.integers(20, 600, n)
    leisure = (total * rng.uniform(0.05, 0.9, n)).astype(int)
    productive = ((total - leisure) * rng.uniform(0, 1, n)).astype(int)
    night = (total * rng.uniform(0, 0.5, n)).astype(int)
    df = pd.DataFrame({"total": total, "leisure": leisure, "productive": productive, "night": night})
    df["label"] = [rule_label(t, l, nt) for t, l, nt in zip(df.total, df.leisure, df.night)]
    return df


_BASE = _baseline_data()


def _fit(train_df):
    return DecisionTreeClassifier(max_depth=5, random_state=42).fit(train_df[FEATURES], train_df["label"])


_GLOBAL_TREE = _fit(_BASE)


def predict_day(total, leisure, productive, night):
    X = pd.DataFrame([[total, leisure, productive, night]], columns=FEATURES)
    return LABELS[int(_GLOBAL_TREE.predict(X)[0])]


def run_tree(feat):
    if feat.empty:
        return None
    # accuracy on hold-out baseline data
    X_tr, X_te, y_tr, y_te = train_test_split(_BASE[FEATURES], _BASE["label"], test_size=0.25, random_state=42)
    acc = accuracy_score(y_te, DecisionTreeClassifier(max_depth=5, random_state=42).fit(X_tr, y_tr).predict(X_te))

    user = feat.copy()
    user["label"] = [rule_label(r.total, r.leisure, r.night) for r in user.itertuples()]
    clf = _fit(pd.concat([_BASE, user[FEATURES + ["label"]]], ignore_index=True))

    preds = clf.predict(user[FEATURES])
    days = [{"date": str(idx), "label": LABELS[int(p)], "total": int(r["total"]), "leisure": int(r["leisure"]),
             "productive": int(r["productive"]), "night": int(r["night"])}
            for (idx, r), p in zip(user.iterrows(), preds)]
    dist = {l: 0 for l in LABELS}
    for d in days:
        dist[d["label"]] += 1
    imp = sorted([{"feature": f, "value": round(float(v), 3)} for f, v in zip(FEATURES, clf.feature_importances_)],
                 key=lambda x: -x["value"])
    return {"days": days, "distribution": dist, "importance": imp,
            "rules": export_text(clf, feature_names=FEATURES, max_depth=4),
            "accuracy": round(float(acc) * 100, 1)}
