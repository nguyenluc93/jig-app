import os
import psycopg2
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# DB
# =========================
def get_conn():
    return psycopg2.connect(DATABASE_URL)


# =========================
# INIT TABLE
# =========================
@app.on_event("startup")
def startup():
    conn = get_conn()
    cur = conn.cursor()

    # USER TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # JIG LOG
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_log (
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        borrow_user TEXT,
        return_user TEXT,
        status TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()


# =========================
# LOGIN PAGE
# =========================
@app.get("/", response_class=HTMLResponse)
def login_page():
    return """
    <h2>Login</h2>
    <form action="/login" method="post">
        <input name="username" placeholder="User"><br>
        <input name="password" type="password" placeholder="Pass"><br>
        <button type="submit">Login</button>
    </form>
    """


# =========================
# LOGIN
# =========================
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",
                (username, password))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if user:
        response = RedirectResponse(url=f"/home?user={username}", status_code=302)
        return response
    else:
        return {"error": "Sai tài khoản"}


# =========================
# HOME (sau login)
# =========================
@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    with open("templates/index.html", encoding="utf-8") as f:
        html = f.read()

    # inject tên user
    html = html.replace("{{username}}", user)
    return html


# =========================
# ADD USER (admin dùng)
# =========================
@app.post("/add-user")
def add_user(username: str = Form(...), password: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT INTO users (username, password) VALUES (%s,%s)",
                (username, password))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "User added"}


# =========================
# DELETE USER
# =========================
@app.post("/delete-user")
def delete_user(username: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE username=%s", (username,))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "User deleted"}


# =========================
# BORROW
# =========================
class BorrowRequest(BaseModel):
    jig_name: str
    user: str


@app.post("/borrow")
def borrow(data: BorrowRequest):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log (jig_name, borrow_user, status)
    VALUES (%s, %s, 'BORROW')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Borrow OK"}


# =========================
# RETURN (scan QR)
# =========================
class ReturnRequest(BaseModel):
    jig_name: str
    user: str


@app.post("/return")
def return_jig(data: ReturnRequest):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log (jig_name, return_user, status)
    VALUES (%s, %s, 'RETURN')
    """, (data.jig_name, data.user))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Return OK"}


# =========================
# LOGS (30 ngày)
# =========================
@app.get("/logs")
def logs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT jig_name, borrow_user, return_user, status, time
    FROM jig_log
    WHERE time > NOW() - INTERVAL '30 days'
    ORDER BY time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "jig": r[0],
            "borrow": r[1],
            "return": r[2],
            "status": r[3],
            "time": str(r[4])
        })

    return result