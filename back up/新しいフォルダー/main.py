import os
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

db_pool = None

# ================= DB =================
@app.on_event("startup")
def startup():
    global db_pool
    db_pool = pool.SimpleConnectionPool(1, 5, DATABASE_URL)

    conn = db_pool.getconn()
    cur = conn.cursor()

    # JIG
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
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    db_pool.putconn(conn)

def get_conn():
    return db_pool.getconn()

def release(conn):
    db_pool.putconn(conn)

# ================= LOGIN =================
@app.get("/", response_class=HTMLResponse)
def login():
    return """
    <h2>ログイン</h2>
    <form action="/login" method="post">
    <input name="username">
    <input name="password" type="password">
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

# ================= JIG =================
class Jig(BaseModel):
    jig_name: str
    image: str

@app.post("/add-jig")
def add_jig(data: Jig):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_master(jig_name,image)
    VALUES(%s,%s)
    ON CONFLICT (jig_name) DO UPDATE SET image=%s
    """, (data.jig_name, data.image, data.image))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "ok"}

@app.post("/delete-jig")
def delete_jig(data: Jig):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM jig_master WHERE jig_name=%s", (data.jig_name,))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "ok"}

@app.get("/jigs")
def get_jigs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT jig_name,image FROM jig_master ORDER BY jig_name")
    rows = cur.fetchall()

    cur.close()
    release(conn)

    return [{"name": r[0], "image": r[1]} for r in rows]

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT DISTINCT ON (jig_name)
    jig_name,status
    FROM jig_log
    ORDER BY jig_name,time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    release(conn)

    return {r[0]: r[1] for r in rows}

# ================= BORROW =================
class Borrow(BaseModel):
    jig_name: str
    user: str

@app.post("/borrow")
def borrow(data: Borrow):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log(jig_name,user_name,status)
    VALUES(%s,%s,'BORROW')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "ok"}

# ================= RETURN =================
class Return(BaseModel):
    jig_name: str
    user: str

@app.post("/return")
def return_jig(data: Return):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log(jig_name,user_name,status)
    VALUES(%s,%s,'RETURN')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "ok"}

# ================= LOG =================
@app.get("/logs")
def logs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT jig_name,user_name,status,time
    FROM jig_log
    ORDER BY time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    release(conn)

    return [{"jig_name":r[0],"user":r[1],"status":r[2],"time":str(r[3])} for r in rows]

# ================= COMMENT =================
class Comment(BaseModel):
    jig: str
    text: str

@app.post("/comment")
def add_comment(data: Comment):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_comment(jig_name,comment)
    VALUES(%s,%s)
    """, (data.jig, data.text))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "ok"}

@app.get("/comments")
def get_comments():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT id,jig_name,comment,time
    FROM jig_comment
    ORDER BY time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    release(conn)

    return [{"id":r[0],"jig":r[1],"text":r[2],"time":str(r[3])} for r in rows]

@app.post("/delete-comment")
def delete_comment(id: int = Form(...)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM jig_comment WHERE id=%s",(id,))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg":"deleted"}