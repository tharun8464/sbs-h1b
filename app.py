from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "h1b_secret"
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Database Setup
def init_db():
    conn = sqlite3.connect("h1b.db")
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS documents")
    c.execute("DROP TABLE IF EXISTS admin_docs")
    c.execute('''CREATE TABLE users 
                 (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT UNIQUE, password TEXT, status TEXT)''')
    c.execute('''CREATE TABLE documents 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, doc_name TEXT, file_path TEXT, doc_type TEXT)''')
    c.execute('''CREATE TABLE admin_docs 
                 (id INTEGER PRIMARY KEY, user_id INTEGER, doc_name TEXT, file_path TEXT)''')
    c.execute("INSERT OR IGNORE INTO users (first_name, last_name, email, password, status) VALUES (?, ?, ?, ?, ?)",
              ("Admin", "User", "admin@h1b.com", "admin123", "Admin"))
    conn.commit()
    conn.close()

# Signup Page
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        password = request.form["password"]
        conn = sqlite3.connect("h1b.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (first_name, last_name, email, password, status) VALUES (?, ?, ?, ?, ?)",
                      (first_name, last_name, email, password, "Pending"))
            conn.commit()
            session["user_id"] = c.lastrowid
            flash("Sign up successful! Login to continue.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists!")
        finally:
            conn.close()
    return render_template("signup.html")

# Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        conn = sqlite3.connect("h1b.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["user_id"] = user[0]
            if user[5] == "Admin":
                return redirect(url_for("dashboard"))
            return redirect(url_for("checklist"))
        flash("Invalid email or password!")
    return render_template("login.html")

# Checklist Page (Candidate)
@app.route("/checklist")
def checklist():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    conn = sqlite3.connect("h1b.db")
    c = conn.cursor()
    c.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    c.execute("SELECT doc_type, doc_name FROM documents WHERE user_id = ?", (user_id,))
    docs = {row[0]: row[1] for row in c.fetchall()}
    c.execute("SELECT doc_name, file_path FROM admin_docs WHERE user_id = ?", (user_id,))
    admin_docs = c.fetchall()
    conn.close()
    return render_template("checklist.html", user=user, docs=docs, admin_docs=admin_docs)

# Upload Route (Candidate - Individual Uploads)
@app.route("/upload", methods=["POST"])
def upload():
    if "user_id" not in session:
        return {"success": False}, 403
    user_id = session["user_id"]
    conn = sqlite3.connect("h1b.db")
    c = conn.cursor()
    c.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    user_folder = os.path.join(app.config["UPLOAD_FOLDER"], f"{user[0]}_{user[1]}")
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    files = request.files
    for doc_type in files:
        file = files[doc_type]
        if file and file.filename:
            filename = f"{doc_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = os.path.join(user_folder, filename)
            file.save(file_path)
            c.execute("INSERT INTO documents (user_id, doc_name, file_path, doc_type) VALUES (?, ?, ?, ?)",
                      (user_id, file.filename, file_path, doc_type))
    conn.commit()
    conn.close()
    return {"success": True}

# Submit Route (Final Submission)
@app.route("/submit", methods=["POST"])
def submit():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    conn = sqlite3.connect("h1b.db")
    c = conn.cursor()
    c.execute("SELECT doc_type FROM documents WHERE user_id = ?", (user_id,))
    uploaded_docs = [row[0] for row in c.fetchall()]
    mandatory_docs = ["education", "resume", "passport", "work_exp", "job_duties"]
    missing_docs = [doc for doc in mandatory_docs if doc not in uploaded_docs]
    if missing_docs:
        flash(f"Missing mandatory documents: {', '.join(missing_docs)}")
    else:
        c.execute("UPDATE users SET status = ? WHERE id = ?", ("Submitted", user_id))
        conn.commit()
        flash("Documents submitted successfully!")
    conn.close()
    return redirect(url_for("checklist"))

# Dashboard Page (Admin)
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect("h1b.db")
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE id = ?", (session["user_id"],))
    if c.fetchone()[0] != "Admin":
        conn.close()
        return redirect(url_for("checklist"))
    c.execute("SELECT id, first_name, last_name, email, status FROM users WHERE status != 'Admin'")
    candidates = c.fetchall()
    docs = {}
    for candidate in candidates:
        c.execute("SELECT doc_type, doc_name FROM documents WHERE user_id = ?", (candidate[0],))
        docs[candidate[0]] = c.fetchall()
    conn.close()
    return render_template("dashboard.html", candidates=candidates, docs=docs)

# Admin Upload Route
@app.route("/admin_upload/<int:user_id>", methods=["POST"])
def admin_upload(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect("h1b.db")
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE id = ?", (session["user_id"],))
    if c.fetchone()[0] != "Admin":
        conn.close()
        return redirect(url_for("checklist"))
    c.execute("SELECT first_name, last_name FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    user_folder = os.path.join(app.config["UPLOAD_FOLDER"], f"{user[0]}_{user[1]}")
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    file = request.files["file"]
    if file and file.filename:
        filename = f"admin_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = os.path.join(user_folder, filename)
        file.save(file_path)
        c.execute("INSERT INTO admin_docs (user_id, doc_name, file_path) VALUES (?, ?, ?)",
                  (user_id, file.filename, file_path))
    conn.commit()
    conn.close()
    flash("Document sent to candidate!")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    init_db()
    app.run(debug=True, port=5003)
