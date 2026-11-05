# HabitLens: Personal Digital Habit Analysis System

HabitLens is a web app that helps you understand how you spend your time on digital devices. You log your daily app usage, and the system shows charts, spots patterns using machine learning, tracks your goals, and gives personalised insights about your habits.

Built with **Python** (backend), **MySQL**, **HTML/CSS/JavaScript** and **scikit-learn** (K-Means Clustering and Decision Tree).

<!-- Add a screenshot after you take one:
![Dashboard](screenshots/dashboard.png)
-->

## Features

**User management**
- Register, log in and log out (passwords are stored as secure hashes)
- Edit your profile (name, age, occupation) and change your password

**Activity tracking**
- Log activities with a date, category, app name, duration and time slot (Morning, Afternoon, Evening, Night)
- Seven categories: Social Media, Entertainment, Gaming, Education, Productivity, Communication, Other
- Filter by date range, delete entries, or load 30 days of sample data to try the app instantly

**Dashboard**
- Today's total screen time and health status
- Last 7 days chart, category breakdown and time-of-day usage
- Goal progress and personalised insights

**Daily and weekly analysis**
- Choose a 14, 30, 60 or 90 day window
- Weekly totals and daily averages, with week-over-week change
- Machine learning results (see below)

**Goals**
- Set a daily limit ("stay under 2 hours of Social Media") or a daily target ("study at least 1 hour")
- Progress is shown as a percentage of days met, with a status such as On track, Needs attention, Achieved or Missed

**Reports**
- Printable report for any date range
- Download your activity data as a CSV file

## Machine learning

**1. K-Means Clustering** groups your days into habit patterns using four features: total, leisure, productive and night-time minutes. Days are named **Productive**, **Balanced** or **Distracted** based on their average leisure plus night usage. It needs at least 4 days of data (3 clusters from 9 days, otherwise 2). The silhouette score is shown as a quality measure.

**2. Decision Tree** classifies each day as **Healthy**, **Moderate** or **Unhealthy**. The tree is trained on 600 generated baseline days plus your own days, labelled with a digital-wellbeing guideline (limits on total, leisure and night usage). The page also shows feature importance and the learned rules. There is also a small prediction API (`POST /api/predict`) that classifies a day from the four values.

> Note: the labels come from a rule-based guideline, so the reported accuracy measures how well the tree learned that guideline. It is not a clinical or medical assessment.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python |
| Database | MySQL |
| Data analysis | pandas, NumPy |
| Machine learning | scikit-learn |
| Frontend | HTML, CSS, JavaScript (Jinja2 templates) |

## Project structure

```
Digital-Habit-Analyzer/
├── app.py              # Flask routes (users, activities, analysis, goals, reports)
├── analytics.py        # Daily/weekly analysis, goal progress, insights
├── ml.py               # K-Means and Decision Tree
├── db.py               # MySQL connection helpers
├── config.example.py   # Template for your private config.py
├── database.sql        # Database schema
├── requirements.txt    # Python dependencies
├── templates/          # HTML pages
└── static/
    ├── css/style.css
    └── js/main.js
```

## Getting started

**Requirements:** Python 3.9+ and MySQL Server.

**1. Clone the repository**
```bash
git clone https://github.com/lirisha-dot/Digital-Habit-Analyzer.git
cd Digital-Habit-Analyzer
```

**2. (Optional) Create a virtual environment**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Create the database**
```bash
mysql -u root -p < database.sql
```
Or open `database.sql` in MySQL Workbench and run it.

**5. Create your config file**

Copy `config.example.py` to `config.py`, then enter your MySQL password and set your own secret key:
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "YOUR_MYSQL_PASSWORD",
    "database": "digital_habit_db",
}
SECRET_KEY = "any-long-random-text"
```
`config.py` is listed in `.gitignore`, so your credentials are never uploaded.

**6. Run the app**
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser, register an account, and click **Add sample data** to explore with 30 days of example activity.

## Security notes

- Passwords are hashed with Werkzeug and never stored in plain text
- All database queries use parameterised statements
- The app runs with `debug=True` for development. Turn this off and use a strong `SECRET_KEY` before deploying anywhere public

## Author

Made by [lirisha-dot](https://github.com/lirisha-dot).
