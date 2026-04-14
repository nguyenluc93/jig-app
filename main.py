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

    # JIG MASTER
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_master(
        id SERIAL PRIMARY KEY,
        jig_name TEXT UNIQUE,
        image TEXT
    )
    """)

    # JIG LOG (đầy đủ column)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_log(
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        borrow_user TEXT,
        return_user TEXT,
        status TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # FIX nếu thiếu column (QUAN TRỌNG)
    cur.execute("""
    ALTER TABLE jig_log ADD COLUMN IF NOT EXISTS borrow_user TEXT;
    """)
    cur.execute("""
    ALTER TABLE jig_log ADD COLUMN IF NOT EXISTS return_user TEXT;
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

# ================= JIG 管理 =================
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

    return {"msg": "追加完了"}

@app.post("/delete-jig")
def delete_jig(data: Jig):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM jig_master WHERE jig_name=%s", (data.jig_name,))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "削除完了"}

@app.get("/jigs")
def get_jigs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT jig_name,image FROM jig_master ORDER BY jig_name")
    rows = cur.fetchall()

    cur.close()
    release(conn)

    return [{"name": r[0], "image": r[1]} for r in rows]

# ================= BORROW =================
class Borrow(BaseModel):
    jig_name: str
    user: str

@app.post("/borrow")
def borrow(data: Borrow):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log(jig_name,borrow_user,status)
    VALUES(%s,%s,'BORROW')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "貸出完了"}

# ================= RETURN =================
class Return(BaseModel):
    jig_name: str
    user: str

@app.post("/return")
def return_jig(data: Return):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log(jig_name,return_user,status)
    VALUES(%s,%s,'RETURN')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release(conn)

    return {"msg": "返却完了"}

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT jig_name, status, time
    FROM jig_log
    ORDER BY time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    release(conn)

    status_map = {}

    for jig_name, status, time in rows:
        if jig_name not in status_map:
            status_map[jig_name] = status

    return status_map