import os
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

db_pool = None

# ================= DB INIT =================
@app.on_event("startup")
def startup():
    global db_pool
    db_pool = pool.SimpleConnectionPool(1, 10, DATABASE_URL)

    conn = db_pool.getconn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reserve(
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        user_name TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    db_pool.putconn(conn)

# ================= HELPER =================
def get_conn():
    return db_pool.getconn()

def release_conn(conn):
    db_pool.putconn(conn)

# ================= LOGIN =================
@app.get("/", response_class=HTMLResponse)
def login_page():
    return """
    <h2>Login</h2>
    <form action="/login" method="post">
        <input name="username"><br>
        <input name="password" type="password"><br>
        <button>Login</button>
    </form>
    """

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cur.fetchone()

    cur.close()
    release_conn(conn)

    if user:
        return RedirectResponse(url=f"/home?user={username}", status_code=302)
    return {"error": "Sai tài khoản"}

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    with open("templates/index.html", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{username}}", user)

# ================= USER =================
@app.post("/add-user")
def add_user(username: str = Form(...), password: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT INTO users(username,password) VALUES(%s,%s)", (username, password))

    conn.commit()
    cur.close()
    release_conn(conn)

    return {"msg": "ok"}

# ================= BORROW =================
class Borrow(BaseModel):
    jig_name: str
    user: str

@app.post("/borrow")
def borrow(data: Borrow):
    conn = get_conn()
    cur = conn.cursor()

    # FIFO check
    cur.execute("""
    SELECT user_name FROM reserve
    WHERE jig_name=%s
    ORDER BY time ASC LIMIT 1
    """, (data.jig_name,))
    first = cur.fetchone()

    if first and first[0] != data.user:
        cur.close()
        release_conn(conn)
        return {"error": "Not your turn (FIFO)"}

    cur.execute("DELETE FROM reserve WHERE jig_name=%s AND user_name=%s",
                (data.jig_name, data.user))

    cur.execute("""
    INSERT INTO jig_log(jig_name,borrow_user,status)
    VALUES(%s,%s,'BORROW')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release_conn(conn)

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
    INSERT INTO jig_log(jig_name,return_user,status)
    VALUES(%s,%s,'RETURN')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release_conn(conn)

    return {"msg": "ok"}

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT DISTINCT ON (jig_name) jig_name,status,borrow_user
    FROM jig_log
    ORDER BY jig_name,time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    release_conn(conn)

    result = {}
    for r in rows:
        result[r[0]] = {"status": r[1], "user": r[2]}

    return result

# ================= RESERVE =================
class Reserve(BaseModel):
    jig_name: str
    user: str

@app.post("/reserve")
def reserve(data: Reserve):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT INTO reserve(jig_name,user_name) VALUES(%s,%s)",
                (data.jig_name, data.user))

    conn.commit()
    cur.close()
    release_conn(conn)

    return {"msg": "ok"}

@app.get("/reserve")
def reserve_list():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT jig_name,user_name,time
    FROM reserve
    ORDER BY time ASC
    """)

    rows = cur.fetchall()

    cur.close()
    release_conn(conn)

    return [{"jig": r[0], "user": r[1], "time": str(r[2])} for r in rows]