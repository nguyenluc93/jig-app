import os
import psycopg2
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ================= INIT DB (SAFE - NO DROP) =================
@app.on_event("startup")
def startup():
    conn = get_conn()
    cur = conn.cursor()

    # USERS (SAFE)
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

    conn.commit()
    cur.close()
    conn.close()

# ================= USER =================
class UserCreate(BaseModel):
    username: str
    password: str
    role: str

@app.post("/create-user")
def create_user(data: UserCreate):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO users(username,password,role)
        VALUES(%s,%s,%s)
        """, (data.username.strip(), data.password.strip(), data.role))
        conn.commit()
        return {"msg": "user created"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

def get_user_role(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row and row[0] else "user"

def require_admin(username):
    if get_user_role(username) != "admin":
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
    cur.execute("SELECT password FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return HTMLResponse("<h3>User NOT FOUND</h3>")

    if row[0] != password:
        return HTMLResponse("<h3>WRONG PASSWORD</h3>")

    return RedirectResponse(f"/home?user={username}", status_code=302)

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    role = get_user_role(user)

    with open("templates/index.html", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{{username}}", user)
    html = html.replace("{{role}}", role)

    return html

# ================= JIG =================
class Jig(BaseModel):
    jig_name: str
    image: str

@app.post("/add-jig")
def add_jig(data: Jig, user: str):
    require_admin(user)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO jig_master(jig_name,image)
    VALUES(%s,%s)
    ON CONFLICT (jig_name) DO UPDATE SET image=%s
    """, (data.jig_name, data.image, data.image))
    conn.commit()
    cur.close()
    conn.close()
    return {"msg": "ok"}

@app.get("/jigs")
def get_jigs():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT jig_name,image FROM jig_master ORDER BY jig_name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"name": r[0], "image": r[1]} for r in rows]

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT DISTINCT ON (jig_name) jig_name, status
    FROM jig_log
    ORDER BY jig_name, time DESC
    """)
    latest = dict(cur.fetchall())

    cur.execute("SELECT jig_name FROM jig_master")
    all_jigs = [r[0] for r in cur.fetchall()]

    cur.close()
    conn.close()

    return {j: latest.get(j, "FREE") for j in all_jigs}

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
    conn.close()
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
    conn.close()
    return {"msg": "ok"}

# ================= COMMENT =================
class Comment(BaseModel):
    jig: str
    text: str
    user: str

@app.post("/comment")
def add_comment(data: Comment):
    conn = get_conn()
    cur = conn.cursor()
    full = f"{data.text} (by {data.user})"
    cur.execute("""
    INSERT INTO jig_comment(jig_name,comment,user_name)
    VALUES(%s,%s,%s)
    """, (data.jig, full, data.user))
    conn.commit()
    cur.close()
    conn.close()
    return {"msg": "ok"}

@app.get("/comments")
def get_comments():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT id,jig_name,comment,user_name,time
    FROM jig_comment
    ORDER BY time DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [{
        "id": r[0],
        "jig": r[1],
        "text": r[2],
        "user": r[3],
        "time": str(r[4])
    } for r in rows]