import os
import psycopg2
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

# ================= DB =================
def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ================= SAFE RESPONSE WRAPPER =================
def safe_json(data=None):
    return JSONResponse(content={"ok": True, "data": data or []})

# ================= INIT DB =================
@app.on_event("startup")
def startup():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user'
    )
    """)

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
        user_name TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

# ================= USERS =================
class User(BaseModel):
    username: str
    password: str
    role: str = "user"

@app.post("/create-user")
def create_user(data: User):
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO users(username,password,role)
        VALUES(%s,%s,%s)
        ON CONFLICT (username) DO UPDATE SET
        password=EXCLUDED.password,
        role=EXCLUDED.role
        """, (data.username, data.password, data.role))

        conn.commit()
        cur.close()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_role(username):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else "user"
    except:
        return "user"

# ================= LOGIN =================
@app.get("/", response_class=HTMLResponse)
def login():
    return """
    <h2>LOGIN</h2>
    <form action="/login" method="post">
        <input name="username" placeholder="user">
        <input name="password" type="password" placeholder="pass">
        <button>login</button>
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

    if not row or row[0] != password:
        return HTMLResponse("LOGIN FAIL")

    return RedirectResponse(f"/home?user={username}", status_code=302)

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    role = get_role(user)

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
def add_jig(data: Jig):
    try:
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
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/jigs")
def get_jigs():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT jig_name,image FROM jig_master ORDER BY jig_name")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return safe_json([{"name": r[0], "image": r[1]} for r in rows])
    except:
        return safe_json([])

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
        SELECT jig_name,
               (SELECT status FROM jig_log l
                WHERE l.jig_name=jig_master.jig_name
                ORDER BY time DESC LIMIT 1)
        FROM jig_master
        """)

        rows = cur.fetchall()
        cur.close()
        conn.close()

        result = {r[0]: (r[1] if r[1] else "FREE") for r in rows}
        return safe_json(result)

    except:
        return safe_json({})

# ================= BORROW / RETURN =================
class Action(BaseModel):
    jig_name: str
    user: str

@app.post("/borrow")
def borrow(data: Action):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log(jig_name,user_name,status)
    VALUES(%s,%s,'BORROW')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}

@app.post("/return")
def return_jig(data: Action):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log(jig_name,user_name,status)
    VALUES(%s,%s,'RETURN')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}

# ================= COMMENTS =================
class Comment(BaseModel):
    jig: str
    text: str

@app.post("/comment")
def add_comment(data: Comment):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_comment(jig_name,comment,user_name)
    VALUES(%s,%s,%s)
    """, (data.jig, data.text, "system"))

    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}

@app.get("/comments")
def get_comments():
    try:
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

        return safe_json([{
            "id": r[0],
            "jig": r[1],
            "text": r[2],
            "user": r[3],
            "time": str(r[4])
        } for r in rows])

    except:
        return safe_json([])

# ================= LOGS =================
@app.get("/logs")
def logs():
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
        SELECT jig_name,user_name,status,time
        FROM jig_log
        ORDER BY time DESC
        """)

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return safe_json([{
            "jig_name": r[0],
            "user": r[1],
            "status": r[2],
            "time": str(r[3])
        } for r in rows])

    except:
        return safe_json([])