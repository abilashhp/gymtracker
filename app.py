from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3, os
from datetime import datetime, date, timedelta
from collections import defaultdict

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "gymtracker.db")


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT NOT NULL,
                label TEXT NOT NULL,
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                set_number INTEGER NOT NULL,
                reps INTEGER,
                weight_kg REAL,
                notes TEXT DEFAULT ''
            );
        """)


@app.route("/")
def index():
    db = get_db()
    sessions = db.execute(
        "SELECT * FROM sessions ORDER BY session_date DESC, id DESC LIMIT 30"
    ).fetchall()

    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    last_monday = monday - timedelta(weeks=1)

    session_ids = [s["id"] for s in sessions]
    session_exercises = {}
    if session_ids:
        placeholders = ",".join("?" * len(session_ids))
        rows = db.execute(
            f"""SELECT session_id, name, COUNT(*) as set_count,
                       MAX(weight_kg) as max_weight, MAX(reps) as max_reps
                FROM exercises WHERE session_id IN ({placeholders})
                GROUP BY session_id, name
                ORDER BY session_id, set_count DESC""",
            session_ids
        ).fetchall()
        for row in rows:
            sid = row["session_id"]
            if sid not in session_exercises:
                session_exercises[sid] = []
            session_exercises[sid].append(dict(row))

    def week_label(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        if d >= monday:
            return "This week"
        elif d >= last_monday:
            return "Last week"
        else:
            ws = d - timedelta(days=d.weekday())
            return ws.strftime("Week of %b %-d")

    def fmt_date(date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        if d == today_date:
            return "Today"
        elif d == today_date - timedelta(days=1):
            return "Yesterday"
        return d.strftime("%a, %b %-d")

    grouped_sessions = []
    current_week = None
    for s in sessions:
        wk = week_label(s["session_date"])
        if wk != current_week:
            current_week = wk
            grouped_sessions.append({"week": wk, "sessions": []})
        exs = session_exercises.get(s["id"], [])
        total_sets = sum(e["set_count"] for e in exs)
        grouped_sessions[-1]["sessions"].append({
            "id": s["id"],
            "label": s["label"],
            "notes": s["notes"],
            "session_date": s["session_date"],
            "formatted_date": fmt_date(s["session_date"]),
            "exercises": exs,
            "total_sets": total_sets,
        })

    return render_template("index.html", grouped_sessions=grouped_sessions,
                          today=today_date.isoformat())


@app.route("/session/new", methods=["GET", "POST"])
def new_session():
    if request.method == "POST":
        session_date = request.form["session_date"]
        label = request.form["label"].strip() or "Workout"
        notes = request.form.get("notes", "").strip()
        db = get_db()
        cur = db.execute(
            "INSERT INTO sessions (session_date, label, notes) VALUES (?,?,?)",
            (session_date, label, notes)
        )
        db.commit()
        return redirect(url_for("session_detail", session_id=cur.lastrowid))
    return render_template("new_session.html", today=date.today().isoformat())


@app.route("/session/<int:session_id>")
def session_detail(session_id):
    db = get_db()
    session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        return redirect(url_for("index"))
    exercises = db.execute(
        "SELECT * FROM exercises WHERE session_id=? ORDER BY name, set_number",
        (session_id,)
    ).fetchall()
    grouped = defaultdict(list)
    for ex in exercises:
        grouped[ex["name"]].append(ex)

    exercise_stats = {}
    for name, sets in grouped.items():
        weights = [s["weight_kg"] for s in sets if s["weight_kg"] is not None]
        reps_list = [s["reps"] for s in sets if s["reps"] is not None]
        volume = sum((s["reps"] or 0) * (s["weight_kg"] or 0) for s in sets)
        exercise_stats[name] = {
            "max_weight": max(weights) if weights else None,
            "max_reps": max(reps_list) if reps_list else None,
            "volume": int(volume),
        }

    total_sets = len(exercises)
    total_volume = sum(s["volume"] for s in exercise_stats.values())

    return render_template("session.html", session=session, grouped=dict(grouped),
                          exercise_stats=exercise_stats,
                          total_sets=total_sets, total_volume=total_volume)


@app.route("/session/<int:session_id>/add_set", methods=["POST"])
def add_set(session_id):
    data = request.get_json()
    name = data.get("name", "").strip()
    reps = data.get("reps")
    weight = data.get("weight_kg")
    notes = data.get("notes", "").strip()
    if not name:
        return jsonify({"error": "Exercise name required"}), 400
    db = get_db()
    # find next set number for this exercise in this session
    row = db.execute(
        "SELECT COALESCE(MAX(set_number),0)+1 as next FROM exercises WHERE session_id=? AND name=?",
        (session_id, name)
    ).fetchone()
    set_num = row["next"]
    db.execute(
        "INSERT INTO exercises (session_id, name, set_number, reps, weight_kg, notes) VALUES (?,?,?,?,?,?)",
        (session_id, name, set_num, reps, weight, notes)
    )
    db.commit()
    return jsonify({"ok": True, "set_number": set_num})


@app.route("/session/<int:session_id>/delete_set/<int:ex_id>", methods=["DELETE"])
def delete_set(session_id, ex_id):
    db = get_db()
    db.execute("DELETE FROM exercises WHERE id=? AND session_id=?", (ex_id, session_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/session/<int:session_id>/delete", methods=["POST"])
def delete_session(session_id):
    db = get_db()
    db.execute("DELETE FROM exercises WHERE session_id=?", (session_id,))
    db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    db.commit()
    return redirect(url_for("index"))


@app.route("/api/exercise_names")
def exercise_names():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT name FROM exercises ORDER BY name"
    ).fetchall()
    return jsonify([r["name"] for r in rows])


@app.route("/api/last_sets/<string:name>")
def last_sets(name):
    db = get_db()
    rows = db.execute("""
        SELECT e.weight_kg, e.reps, e.set_number, s.session_date
        FROM exercises e JOIN sessions s ON e.session_id=s.id
        WHERE e.name=?
        ORDER BY s.session_date DESC, e.set_number ASC
        LIMIT 5
    """, (name,)).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5001)
