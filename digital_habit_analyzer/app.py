import csv
import io
import random
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, Response, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import analytics as an
import ml
from config import SECRET_KEY
from db import execute_many, query

app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.template_filter("hm")
def hm(m):
    m = int(m or 0)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"


def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if "user_id" not in session:
            flash("Please log in first.", "warn")
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrap


def parse_date(s, default):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ A. USER MANAGEMENT
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["full_name"].strip()
        email = request.form["email"].strip().lower()
        pw, pw2 = request.form["password"], request.form["confirm"]
        if not name or not email:
            flash("Name and email are required.", "error")
        elif len(pw) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif pw != pw2:
            flash("Passwords do not match.", "error")
        elif query("SELECT id FROM users WHERE email=%s", (email,), one=True):
            flash("This email is already registered.", "error")
        else:
            query("INSERT INTO users(full_name,email,password_hash) VALUES(%s,%s,%s)",
                  (name, email, generate_password_hash(pw)), commit=True)
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        u = query("SELECT * FROM users WHERE email=%s", (email,), one=True)
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session["user_id"], session["name"] = u["id"], u["full_name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid = session["user_id"]
    if request.method == "POST":
        if request.form.get("action") == "info":
            age = request.form.get("age") or None
            query("UPDATE users SET full_name=%s, age=%s, occupation=%s WHERE id=%s",
                  (request.form["full_name"].strip(), age, request.form.get("occupation", "").strip(), uid), commit=True)
            session["name"] = request.form["full_name"].strip()
            flash("Profile updated.", "success")
        else:
            u = query("SELECT password_hash FROM users WHERE id=%s", (uid,), one=True)
            new = request.form["new_password"]
            if not check_password_hash(u["password_hash"], request.form["old_password"]):
                flash("Current password is incorrect.", "error")
            elif len(new) < 6 or new != request.form["confirm"]:
                flash("New password must be 6+ characters and match the confirmation.", "error")
            else:
                query("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(new), uid), commit=True)
                flash("Password changed.", "success")
        return redirect(url_for("profile"))
    user = query("SELECT * FROM users WHERE id=%s", (uid,), one=True)
    return render_template("profile.html", user=user)


# ------------------------------------------------------------------ D. DASHBOARD
@app.route("/dashboard")
@login_required
def dashboard():
    uid, today = session["user_id"], date.today()
    df30 = an.load_df(uid, today - timedelta(days=29), today)
    df7 = df30[df30["activity_date"].dt.date >= today - timedelta(days=6)] if not df30.empty else df30
    tree = ml.run_tree(ml.daily_features(df30))
    today_status = None
    if tree and tree["days"] and tree["days"][-1]["date"] == str(today):
        today_status = tree["days"][-1]["label"]
    goals = query("SELECT * FROM goals WHERE user_id=%s AND end_date>=%s ORDER BY end_date LIMIT 3", (uid, today))
    for g in goals:
        g["prog"] = an.goal_progress(g, uid)
    data = {
        "week": an.daily_series(df7, today - timedelta(days=6), today),
        "categories": an.category_totals(df30),
        "slots": an.slot_totals(df30),
    }
    today_min = int(df30[df30["activity_date"].dt.date == today]["duration_min"].sum()) if not df30.empty else 0
    sm = an.summary(df30)
    return render_template("dashboard.html", data=data, sm=sm, today_min=today_min, today_status=today_status,
                           goals=goals, insights=an.insights(sm, an.weekly_totals(df30), tree), has_data=not df30.empty)


# ------------------------------------------------------------------ B. ACTIVITY TRACKING
@app.route("/activity", methods=["GET", "POST"])
@login_required
def activity():
    uid = session["user_id"]
    if request.method == "POST":
        try:
            dur = int(request.form["duration_min"])
            assert 1 <= dur <= 1440
            query("INSERT INTO activities(user_id,activity_date,category,app_name,duration_min,time_slot,notes) "
                  "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                  (uid, request.form["activity_date"], request.form["category"], request.form["app_name"].strip(),
                   dur, request.form["time_slot"], request.form.get("notes", "").strip()), commit=True)
            flash("Activity added.", "success")
        except (ValueError, AssertionError, KeyError):
            flash("Please enter valid details (duration 1-1440 minutes).", "error")
        return redirect(url_for("activity"))
    start = parse_date(request.args.get("start"), date.today() - timedelta(days=30))
    end = parse_date(request.args.get("end"), date.today())
    rows = query("SELECT * FROM activities WHERE user_id=%s AND activity_date BETWEEN %s AND %s "
                 "ORDER BY activity_date DESC, id DESC LIMIT 300", (uid, start, end))
    return render_template("activity.html", rows=rows, cats=an.CATEGORIES, slots=an.SLOTS,
                           today=date.today().isoformat(), start=start, end=end)


@app.route("/activity/delete/<int:aid>", methods=["POST"])
@login_required
def activity_delete(aid):
    query("DELETE FROM activities WHERE id=%s AND user_id=%s", (aid, session["user_id"]), commit=True)
    flash("Activity deleted.", "success")
    return redirect(request.referrer or url_for("activity"))


@app.route("/activity/sample", methods=["POST"])
@login_required
def activity_sample():
    uid, today, rows = session["user_id"], date.today(), []
    apps = {"Social Media": ["Instagram", "Facebook", "TikTok"], "Entertainment": ["YouTube", "Netflix"],
            "Gaming": ["PUBG", "Free Fire"], "Education": ["Coursera", "Khan Academy", "PDF Notes"],
            "Productivity": ["VS Code", "Google Docs"], "Communication": ["WhatsApp", "Messenger"], "Other": ["Browser"]}
    moods = {
        "study": ({"Education": 4, "Productivity": 3, "Communication": 1, "Social Media": 1, "Entertainment": 1}, (4, 5), (15, 70), [4, 4, 2, 0.3]),
        "balanced": ({"Education": 2, "Productivity": 2, "Communication": 2, "Social Media": 2, "Entertainment": 2, "Gaming": 1}, (4, 6), (15, 80), [2, 3, 3, 1]),
        "lazy": ({"Social Media": 4, "Entertainment": 4, "Gaming": 3, "Communication": 1, "Education": 0.3}, (5, 7), (30, 120), [0.5, 1, 3, 5]),
    }
    for i in range(30):
        d = today - timedelta(days=i)
        mood = random.choice(["study", "study", "balanced", "balanced", "lazy"] + (["lazy"] * 2 if d.weekday() >= 5 else []))
        weights, (lo, hi), (dmin, dmax), slot_w = moods[mood]
        for _ in range(random.randint(lo, hi)):
            cat = random.choices(list(weights), weights=list(weights.values()))[0]
            rows.append((uid, d, cat, random.choice(apps[cat]), random.randint(dmin, dmax),
                         random.choices(an.SLOTS, weights=slot_w)[0], "Sample data"))
    execute_many("INSERT INTO activities(user_id,activity_date,category,app_name,duration_min,time_slot,notes) "
                 "VALUES(%s,%s,%s,%s,%s,%s,%s)", rows)
    flash("30 days of sample data added.", "success")
    return redirect(url_for("dashboard"))


@app.route("/activity/clear", methods=["POST"])
@login_required
def activity_clear():
    query("DELETE FROM activities WHERE user_id=%s", (session["user_id"],), commit=True)
    flash("All your activities were deleted.", "success")
    return redirect(url_for("activity"))


# ------------------------------------------------------------------ C. DAILY & WEEKLY ANALYSIS (+ ML)
@app.route("/analysis")
@login_required
def analysis():
    uid, today = session["user_id"], date.today()
    days = request.args.get("days", 30, type=int)
    days = days if days in (14, 30, 60, 90) else 30
    start = today - timedelta(days=days - 1)
    df = an.load_df(uid, start, today)
    feat = ml.daily_features(df)
    km, tree, weekly = ml.run_kmeans(feat), ml.run_tree(feat), an.weekly_totals(df)
    sm = an.summary(df)
    daily = an.daily_series(df, start, today)
    return render_template("analysis.html", days=days, sm=sm, weekly=weekly, km=km, tree=tree, daily=daily,
                           cats=an.category_totals(df), has_data=not df.empty,
                           insights=an.insights(sm, weekly, tree), n_days=len(feat))


@app.route("/api/predict", methods=["POST"])
@login_required
def api_predict():
    j = request.get_json(force=True)
    try:
        t, l, p, n = (max(0, int(j.get(k, 0))) for k in ("total", "leisure", "productive", "night"))
    except (TypeError, ValueError):
        return jsonify(error="Invalid numbers"), 400
    return jsonify(label=ml.predict_day(t, l, p, n))


# ------------------------------------------------------------------ F. GOALS
@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    uid = session["user_id"]
    if request.method == "POST":
        try:
            start, end = date.fromisoformat(request.form["start_date"]), date.fromisoformat(request.form["end_date"])
            target = int(request.form["target_min"])
            assert end >= start and target > 0
            query("INSERT INTO goals(user_id,title,category,goal_type,target_min,start_date,end_date) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                  (uid, request.form["title"].strip(), request.form["category"], request.form["goal_type"], target, start, end),
                  commit=True)
            flash("Goal created.", "success")
        except (ValueError, AssertionError, KeyError):
            flash("Please enter valid goal details (end date must be after start date).", "error")
        return redirect(url_for("goals"))
    rows = query("SELECT * FROM goals WHERE user_id=%s ORDER BY end_date DESC", (uid,))
    for g in rows:
        g["prog"] = an.goal_progress(g, uid)
    return render_template("goals.html", goals=rows, cats=["All"] + an.CATEGORIES, today=date.today().isoformat(),
                           end_default=(date.today() + timedelta(days=7)).isoformat())


@app.route("/goals/delete/<int:gid>", methods=["POST"])
@login_required
def goal_delete(gid):
    query("DELETE FROM goals WHERE id=%s AND user_id=%s", (gid, session["user_id"]), commit=True)
    flash("Goal deleted.", "success")
    return redirect(url_for("goals"))


# ------------------------------------------------------------------ G. REPORTS
@app.route("/reports")
@login_required
def reports():
    uid = session["user_id"]
    end = parse_date(request.args.get("end"), date.today())
    start = parse_date(request.args.get("start"), end - timedelta(days=29))
    df = an.load_df(uid, start, end)
    feat = ml.daily_features(df)
    km, tree, weekly = ml.run_kmeans(feat), ml.run_tree(feat), an.weekly_totals(df)
    sm = an.summary(df)
    gl = query("SELECT * FROM goals WHERE user_id=%s AND start_date<=%s AND end_date>=%s", (uid, end, start))
    for g in gl:
        g["prog"] = an.goal_progress(g, uid)
    user = query("SELECT full_name, email FROM users WHERE id=%s", (uid,), one=True)
    return render_template("reports.html", start=start, end=end, sm=sm, weekly=weekly, km=km, tree=tree,
                           cats=an.category_totals(df), slots=an.slot_totals(df), goals=gl, user=user,
                           daily=[{"date": d, "minutes": m} for d, m in an._per_day(df).items()],
                           insights=an.insights(sm, weekly, tree), generated=date.today())


@app.route("/reports/csv")
@login_required
def reports_csv():
    end = parse_date(request.args.get("end"), date.today())
    start = parse_date(request.args.get("start"), end - timedelta(days=29))
    rows = query("SELECT activity_date,category,app_name,duration_min,time_slot,notes FROM activities "
                 "WHERE user_id=%s AND activity_date BETWEEN %s AND %s ORDER BY activity_date",
                 (session["user_id"], start, end))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Category", "App", "Duration (min)", "Time Slot", "Notes"])
    for r in rows:
        w.writerow([r["activity_date"], r["category"], r["app_name"], r["duration_min"], r["time_slot"], r["notes"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=habit_report_{start}_{end}.csv"})


if __name__ == "__main__":
    app.run(debug=True)
