from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import datetime
import jdatetime

app = Flask(__name__)
app.secret_key = "GAPGPTMASKTOKEN69rbztv0ezX0X"

def get_db_connection():
     conn = sqlite3.connect('smart_scheduler.db')
     conn.row_factory = sqlite3.Row
     return conn

def init_db():
     conn = get_db_connection()
     conn.execute('''
               CREATE TABLE IF NOT EXISTS tasks (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 task TEXT,
                 description TEXT,
                 category TEXT,
                 priority TEXT,
                 deadline TEXT,
                 status TEXT DEFAULT 'در انتظار'
             )
         ''')
     conn.commit()
     conn.close()

     init_db()



@app.route("/")
def index():
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT username FROM users WHERE id = ?", (session["user_id"],))
        user_row = cursor.fetchone()
        username = user_row[0] if user_row else "کاربر"

        cursor.execute("""
            SELECT t.id, t.title, t.description, t.priority, 
            t.due_date, 
            t.status, c.name AS category_name 
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
                dt_val = row[4]
                try:
                    if isinstance(dt_val, str):
                        if '.' in dt_val:
                            dt_val = dt_val.split('.')[0]
                        try:
                            dt = datetime.strptime(dt_val, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            dt = datetime.strptime(dt_val, '%Y-%m-%d %H:%M')
                    else:
                        dt = dt_val
                    
                    shamsi_dt = jdatetime.datetime.fromgregorian(datetime=dt)
                    shamsi_due = shamsi_dt.strftime("%Y/%m/%d %H:%M")
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
    
    # دریافت مقدار تاریخ ارسالی از تقویم
    due_raw = request.form.get("due", "").strip()
    print("due_raw =", repr(due_raw))

    due_date = None

    if due_raw:
        # حذف T یا میلی‌ثانیه احتمالی
        cleaned = due_raw.replace("T", " ").split(".")[0].strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                due_date = datetime.strptime(cleaned, fmt)
                break
            except ValueError:
                pass

        # اگر تاریخ به صورت متن شمسی فرستاده شده بود (مثلا 1403/07/04 15:30)
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
                due_date = g_date
            except Exception:
                due_date = None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tasks (title, description, category_id, priority, due_date, user_id, status)
        VALUES (?, ?, ?, ?, ?, ?, N'انجام نشده')
    """, (title, desc, cat_id, priority, due_date, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/update_status/<int:task_id>/<status>")
def update_status(task_id, status):
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?", (status, task_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):
    if "user_id" not in session:
        session["user_id"] = 1

    conn = get_db()
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
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,))
    total_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = N'انجام شده'", (user_id,))
    done_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = N'در حال انجام'", (user_id,))
    in_progress_tasks = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND (status = N'انجام نشده' OR status IS NULL)", (user_id,))
    pending_tasks = cursor.fetchone()[0] or 0

    completion_rate = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    cursor.execute("""
        SELECT id, title, priority, 
               CONVERT(VARCHAR(16), due_date, 120) AS due_date, 
               status 
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

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, 
               CONVERT(VARCHAR(19), due_date, 120) AS due_date, 
               status, priority 
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
        conn = get_db()
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
        conn = get_db()
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

if __name__ == "__main__":
    app.run(debug=True)
