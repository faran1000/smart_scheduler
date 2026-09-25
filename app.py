from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
import jdatetime
import os

app = Flask(__name__)
app.secret_key = "smart_scheduler_secret_key_2026"

def get_db_connection():
    conn = sqlite3.connect('smart_scheduler.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            category_id INTEGER,
            priority TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'انجام نشده',
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')

    cursor.execute("SELECT id FROM users WHERE id = 1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'کاربر', '123456')")

    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO categories (name) VALUES (?)", [('عمومی',), ('کاری',), ('شخصی',), ('درسی',)])

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT username FROM users WHERE id = ?", (session["user_id"],))
        user_row = cursor.fetchone()
        username = user_row[0] if user_row else "کاربر"

        cursor.execute("""
            SELECT t.id, t.title, t.description, t.priority, 
                   t.due_date, t.status, c.name AS category_name 
            FROM tasks t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = ? 
            ORDER BY t.id DESC
        """, (session["user_id"],))
        raw_tasks = cursor.fetchall()

        tasks = []
        for row in raw_tasks:
            shamsi_due = ""
            if row[4]:
                dt_val = str(row[4]).split('.')[0].strip()
                try:
                    dt = None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                        try:
                            dt = datetime.strptime(dt_val, fmt)
                            break
                        except ValueError:
                            pass
                    if dt:
                        shamsi_dt = jdatetime.datetime.fromgregorian(datetime=dt)
                        shamsi_due = shamsi_dt.strftime("%Y/%m/%d %H:%M")
                    else:
                        shamsi_due = dt_val
                except Exception:
                    shamsi_due = str(row[4])

            tasks.append((row[0], row[1], row[2], row[3], shamsi_due, row[5], row[6]))

        cursor.execute("SELECT id, name FROM categories")
        categories = cursor.fetchall()
        
        return render_template(
            "index.html",
            tasks=tasks,
            categories=categories,
            username=username
        )
    finally:
        cursor.close()
        conn.close()

@app.route("/add_task", methods=["GET", "POST"])
def add_task():
    if request.method == "GET":
        return redirect(url_for("index"))

    if "user_id" not in session:
        session["user_id"] = 1

    title = request.form.get("title", "").strip()
    desc = request.form.get("desc", "").strip() or None
    priority = request.form.get("priority", "متوسط")
    cat_id = request.form.get("cat_id") or None

    due_raw = request.form.get("due", "").strip()
    due_date = None

    if due_raw:
        cleaned = due_raw.replace("T", " ").split(".")[0].strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                due_date = datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M:%S")
                break
            except ValueError:
                pass

        if not due_date and "/" in cleaned:
            try:
                parts = cleaned.split(" ")
                date_p = parts[0].split("/")
                jy, jm, jd = int(date_p[0]), int(date_p[1]), int(date_p[2])
                hour, minute = 0, 0
                if len(parts) > 1 and ":" in parts[1]:
                    time_p = parts[1].split(":")
                    hour, minute = int(time_p[0]), int(time_p[1])
                g_date = jdatetime.datetime(jy, jm, jd, hour, minute).togregorian()
                due_date = g_date.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                due_date = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (title, description, category_id, priority, due_date, user_id, status)
        VALUES (?, ?, ?, ?, ?, ?, 'انجام نشده')
    """, (title, desc, cat_id, priority, due_date, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/update_status/<int:task_id>/<status>")
def update_status(task_id, status):
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?", (status, task_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/reports")
def reports():
    if "user_id" not in session:
        session["user_id"] = 1

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,))
    total_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'انجام شده'", (user_id,))
    done_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'در حال انجام'", (user_id,))
    in_progress_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND (status = 'انجام نشده' OR status IS NULL)", (user_id,))
    pending_tasks = cursor.fetchone()[0] or 0

    completion_rate = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    cursor.execute("""
        SELECT id, title, priority, due_date, status 
        FROM tasks 
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))
    tasks = cursor.fetchall()
    conn.close()

    summary = {
        "total": total_tasks,
        "done": done_tasks,
        "in_progress": in_progress_tasks,
        "pending": pending_tasks,
        "rate": completion_rate
    }

    return render_template("reports.html", summary=summary, tasks=tasks)

@app.route("/calendar")
def calendar():
    if "user_id" not in session:
        session["user_id"] = 1
    return render_template("calendar.html")

@app.route("/api/tasks")
def api_tasks():
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, due_date, status, priority 
        FROM tasks 
        WHERE user_id = ? AND due_date IS NOT NULL
    """, (session["user_id"],))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        events.append({
            "id": r[0],
            "title": f"{r[1]} ({r[3]})",
            "due": r[2]
        })

    return jsonify(events)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return "این نام کاربری قبلاً ثبت شده است."
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ? AND password_hash = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        return "نام کاربری یا رمز عبور اشتباه است."
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
