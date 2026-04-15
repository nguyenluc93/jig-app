import os
import psycopg2
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

# ================= DB =================
def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ================= INIT DB =================
@app.on_event("startup")
def startup():
    conn = get_conn()
    cur = conn.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # JIG MASTER
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_master(
        id SERIAL PRIMARY KEY,
        jig_name TEXT UNIQUE,
        image TEXT
    )
    """)

    # LOG
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_log(
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        user_name TEXT,
        status TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # COMMENT
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_comment(
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        comment TEXT,
        user_name TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Fix DB cũ
    cur.execute("""
    ALTER TABLE jig_comment 
    ADD COLUMN IF NOT EXISTS user_name TEXT
    """)

    conn.commit()
    cur.close()
    conn.close()

# ================= USER =================
class UserCreate(BaseModel):
    username: str
    password: str
    role: str  # admin / user

@app.post("/create-user")
def create_user(data: UserCreate):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO users(username,password,role)
        VALUES(%s,%s,%s)
        """, (data.username, data.password, data.role))
        conn.commit()
        return {"msg": "user created"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/debug-users")
def debug_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username,password,role FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_user_role(username):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

def require_admin(username):
    role = get_user_role(username)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

# ================= LOGIN =================
@app.get("/", response_class=HTMLResponse)
def login():
    return """
    <h2>ログイン</h2>
    <form action="/login" method="post">
    <input name="username" placeholder="ユーザー名">
    <input name="password" type="password" placeholder="パスワード">
    <button>ログイン</button>
    </form>
    """

@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT password FROM users WHERE username=%s", (username,))
        row = cur.fetchone()

        if not row or row[0] != password:
            return HTMLResponse("<h3>Login failed</h3>")

        return RedirectResponse(f"/home?user={username}", status_code=302)
    finally:
        cur.close()
        conn.close()

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    with open("templates/index.html", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{username}}", user)

# ================= JIG =================
class Jig(BaseModel):
    jig_name: str
    image: str

@app.post("/add-jig")
def add_jig(data: Jig, user: str):
    require_admin(user)

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO jig_master(jig_name,image)
        VALUES(%s,%s)
        ON CONFLICT (jig_name) DO UPDATE SET image=%s
        """, (data.jig_name, data.image, data.image))
        conn.commit()
        return {"msg": "ok"}
    finally:
        cur.close()
        conn.close()

@app.post("/delete-jig")
def delete_jig(data: Jig, user: str):
    require_admin(user)

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM jig_master WHERE jig_name=%s", (data.jig_name,))
        conn.commit()
        return {"msg": "ok"}
    finally:
        cur.close()
        conn.close()

@app.get("/jigs")
def get_jigs():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT jig_name,image FROM jig_master ORDER BY jig_name")
        rows = cur.fetchall()
        return [{"name": r[0], "image": r[1]} for r in rows]
    finally:
        cur.close()
        conn.close()

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT DISTINCT ON (jig_name) jig_name, status
        FROM jig_log
        ORDER BY jig_name, time DESC
        """)
        latest = dict(cur.fetchall())

        cur.execute("SELECT jig_name FROM jig_master")
        all_jigs = [r[0] for r in cur.fetchall()]

        result = {}
        for j in all_jigs:
            result[j] = latest.get(j, "FREE")

        return result
    finally:
        cur.close()
        conn.close()

# ================= BORROW =================
class BorrowBatch(BaseModel):
    jigs: list[str]
    user: str

@app.post("/borrow")
def borrow(data: BorrowBatch):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT DISTINCT ON (jig_name) jig_name, status
        FROM jig_log
        ORDER BY jig_name, time DESC
        """)
        latest = dict(cur.fetchall())

        for jig in data.jigs:
            if latest.get(jig) == "BORROW":
                raise HTTPException(status_code=400, detail=f"{jig} already borrowed")

        for jig in data.jigs:
            cur.execute("""
            INSERT INTO jig_log(jig_name,user_name,status)
            VALUES(%s,%s,'BORROW')
            """, (jig, data.user))

        conn.commit()
        return {"msg": "ok"}
    finally:
        cur.close()
        conn.close()

# ================= RETURN =================
class ReturnBatch(BaseModel):
    jigs: list[str]
    user: str

@app.post("/return")
def return_jig(data: ReturnBatch):
    conn = get_conn()
    cur = conn.cursor()
    try:
        for jig in data.jigs:
            cur.execute("""
            INSERT INTO jig_log(jig_name,user_name,status)
            VALUES(%s,%s,'RETURN')
            """, (jig, data.user))

        conn.commit()
        return {"msg": "ok"}
    finally:
        cur.close()
        conn.close()

# ================= LOG =================
@app.get("/logs")
def logs():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT jig_name,user_name,status,time
        FROM jig_log
        ORDER BY time DESC
        """)
        rows = cur.fetchall()

        return [{
            "jig_name": r[0],
            "user": r[1],
            "status": r[2],
            "time": str(r[3])
        } for r in rows]
    finally:
        cur.close()
        conn.close()

# ================= COMMENT =================
class Comment(BaseModel):
    jig: str
    text: str
    user: str

@app.post("/comment")
def add_comment(data: Comment):
    conn = get_conn()
    cur = conn.cursor()
    try:
        full = f"{data.text} (by {data.user})"
        cur.execute("""
        INSERT INTO jig_comment(jig_name,comment,user_name)
        VALUES(%s,%s,%s)
        """, (data.jig, full, data.user))
        conn.commit()
        return {"msg": "ok"}
    finally:
        cur.close()
        conn.close()

@app.get("/comments")
def get_comments():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT id,jig_name,comment,user_name,time
        FROM jig_comment
        ORDER BY time DESC
        """)
        rows = cur.fetchall()

        return [{
            "id": r[0],
            "jig": r[1],
            "text": r[2],
            "user": r[3],
            "time": str(r[4])
        } for r in rows]
    finally:
        cur.close()
        conn.close()

@app.post("/delete-comment")
def delete_comment(id: int = Form(...), user: str = Form(...)):
    require_admin(user)

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM jig_comment WHERE id=%s", (id,))
        conn.commit()
        return {"msg": "deleted"}
    finally:
        cur.close()
        conn.close()