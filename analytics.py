"""Daily / weekly habit analysis helpers."""
import pandas as pd
from datetime import date, timedelta
from db import query

CATEGORIES = ["Social Media", "Entertainment", "Gaming", "Education", "Productivity", "Communication", "Other"]
SLOTS = ["Morning", "Afternoon", "Evening", "Night"]
COLS = ["id", "activity_date", "category", "app_name", "duration_min", "time_slot", "notes"]


def load_df(uid, start=None, end=None):
    sql = "SELECT id, activity_date, category, app_name, duration_min, time_slot, notes FROM activities WHERE user_id=%s"
    p = [uid]
    if start:
        sql += " AND activity_date>=%s"
        p.append(start)
    if end:
        sql += " AND activity_date<=%s"
        p.append(end)
    rows = query(sql + " ORDER BY activity_date", p)
    if not rows:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame(rows)
    df["activity_date"] = pd.to_datetime(df["activity_date"])
    df["duration_min"] = df["duration_min"].astype(int)
    return df


def _per_day(df):
    if df.empty:
        return {}
    return {k: int(v) for k, v in df.groupby(df["activity_date"].dt.date)["duration_min"].sum().items()}


def daily_series(df, start, end):
    from ml import LEISURE, PRODUCTIVE
    tot = _per_day(df)
    lei = _per_day(df[df["category"].isin(LEISURE)]) if not df.empty else {}
    pro = _per_day(df[df["category"].isin(PRODUCTIVE)]) if not df.empty else {}
    out = {"labels": [], "total": [], "leisure": [], "productive": []}
    for i in range((end - start).days + 1):
        d = start + timedelta(days=i)
        out["labels"].append(d.strftime("%d %b"))
        out["total"].append(tot.get(d, 0))
        out["leisure"].append(lei.get(d, 0))
        out["productive"].append(pro.get(d, 0))
    return out


def weekly_totals(df):
    if df.empty:
        return []
    d = df.copy()
    d["week"] = d["activity_date"].dt.to_period("W").apply(lambda p: p.start_time.date())
    g = d.groupby("week").agg(minutes=("duration_min", "sum"), days=("activity_date", lambda s: s.dt.date.nunique()))
    return [{"week": str(w), "minutes": int(r.minutes), "days": int(r.days), "avg": int(r.minutes / r.days)}
            for w, r in g.iterrows()]


def category_totals(df):
    if df.empty:
        return []
    g = df.groupby("category")["duration_min"].sum().sort_values(ascending=False)
    return [{"category": c, "minutes": int(m)} for c, m in g.items()]


def slot_totals(df):
    g = df.groupby("time_slot")["duration_min"].sum().to_dict() if not df.empty else {}
    return [{"slot": s, "minutes": int(g.get(s, 0))} for s in SLOTS]


def summary(df):
    if df.empty:
        return dict(total=0, days=0, avg=0, top_cat="—", top_pct=0, peak_slot="—")
    cat = df.groupby("category")["duration_min"].sum().sort_values(ascending=False)
    slot = df.groupby("time_slot")["duration_min"].sum().sort_values(ascending=False)
    days = int(df["activity_date"].dt.date.nunique())
    total = int(df["duration_min"].sum())
    return dict(total=total, days=days, avg=round(total / days), top_cat=str(cat.index[0]),
                top_pct=round(int(cat.iloc[0]) * 100 / total), peak_slot=str(slot.index[0]))


def goal_progress(goal, uid):
    today = date.today()
    start, end = goal["start_date"], min(goal["end_date"], today)
    base = {"pct": 0, "days_total": 0, "days_met": 0, "today": 0}
    if end < start:
        return {**base, "status": "Not started"}
    df = load_df(uid, start, end)
    if goal["category"] != "All" and not df.empty:
        df = df[df["category"] == goal["category"]]
    per = _per_day(df)
    days = (end - start).days + 1
    met = 0
    for i in range(days):
        m = per.get(start + timedelta(days=i), 0)
        if (goal["goal_type"] == "max" and m <= goal["target_min"]) or \
           (goal["goal_type"] == "min" and m >= goal["target_min"]):
            met += 1
    pct = round(met * 100 / days)
    if goal["end_date"] < today:
        status = "Achieved" if pct >= 80 else "Missed"
    else:
        status = "On track" if pct >= 70 else "Needs attention"
    return {"pct": pct, "days_total": days, "days_met": met, "today": per.get(today, 0), "status": status}


def insights(sm, weekly, tree):
    if not sm["days"]:
        return ["No data yet. Add some activities (or load sample data) to see personalised insights."]
    out = [f"Most of your time ({sm['top_pct']}%) goes to {sm['top_cat']}.",
           f"You are most active online during the {sm['peak_slot'].lower()}."]
    if len(weekly) >= 2 and weekly[-2]["avg"] > 0:
        ch = round((weekly[-1]["avg"] - weekly[-2]["avg"]) * 100 / weekly[-2]["avg"])
        out.append(f"Your daily average this week is {'up' if ch > 0 else 'down'} {abs(ch)}% compared to last week.")
    if tree:
        bad, n = tree["distribution"]["Unhealthy"], len(tree["days"])
        if bad:
            out.append(f"The Decision Tree flagged {bad} of {n} days as Unhealthy. Try reducing night-time and leisure usage.")
        else:
            out.append("The Decision Tree found no unhealthy days in this period. Keep it up!")
    return out
