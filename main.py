import os
import psycopg2
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

# ================= DB =================
def get_conn():
    return psycopg2.connect(DATABASE_URL)

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
    return RedirectResponse(f"/home?user={username}", status_code=302)

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    with open("templates/index.html", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{username}}", user)

# ================= INIT DB =================
@app.on_event("startup")
def startup():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_master(
        id SERIAL PRIMARY KEY,
        jig_name TEXT UNIQUE,
        image TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_log(
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        user_name TEXT,
        status TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_comment(
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        comment TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

# ================= JIG =================
class Jig(BaseModel):
    jig_name: str
    image: str

@app.post("/add-jig")
def add_jig(data: Jig):
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
def delete_jig(data: Jig):
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
        SELECT j.jig_name,
               (SELECT status FROM jig_log l 
                WHERE l.jig_name=j.jig_name 
                ORDER BY time DESC LIMIT 1)
        FROM jig_master j
        """)
        rows = cur.fetchall()

        result = {}
        for r in rows:
            result[r[0]] = r[1] if r[1] else "FREE"

        return result
    finally:
        cur.close()
        conn.close()

# ================= BORROW =================
class Borrow(BaseModel):
    jig_name: str
    user: str

@app.post("/borrow")
def borrow(data: Borrow):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO jig_log(jig_name,user_name,status)
        VALUES(%s,%s,'BORROW')
        """, (data.jig_name, data.user))
        conn.commit()
        return {"msg": "ok"}
    finally:
        cur.close()
        conn.close()

# ================= RETURN =================
class Return(BaseModel):
    jig_name: str
    user: str

@app.post("/return")
def return_jig(data: Return):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO jig_log(jig_name,user_name,status)
        VALUES(%s,%s,'RETURN')
        """, (data.jig_name, data.user))
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

@app.post("/comment")
def add_comment(data: Comment):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO jig_comment(jig_name,comment)
        VALUES(%s,%s)
        """, (data.jig, data.text))
        conn.commit()
        return {"msg": "ok"}
    except Exception as e:
        conn.rollback()
        return {"msg": "error", "detail": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/comments")
def get_comments():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT id,jig_name,comment,time
        FROM jig_comment
        ORDER BY time DESC
        """)
        rows = cur.fetchall()

        return [{
            "id": r[0],
            "jig": r[1],
            "text": r[2],
            "time": str(r[3])
        } for r in rows]
    finally:
        cur.close()
        conn.close()

@app.post("/delete-comment")
def delete_comment(id: int = Form(...)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM jig_comment WHERE id=%s", (id,))
        conn.commit()
        return {"msg": "deleted"}
    finally:
        cur.close()
        conn.close()