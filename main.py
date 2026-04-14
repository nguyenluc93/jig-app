import os
import psycopg2
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

app = FastAPI()

# =========================
# ENV
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")


# =========================
# DB CONNECTION
# =========================
def get_conn():
    return psycopg2.connect(DATABASE_URL)


# =========================
# MODEL
# =========================
class BorrowRequest(BaseModel):
    user_name: str
    user_email: str
    jig_name: str


class ReturnRequest(BaseModel):
    jig_name: str


# =========================
# INIT TABLE
# =========================
@app.on_event("startup")
def startup():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jig_log (
        id SERIAL PRIMARY KEY,
        jig_name TEXT,
        user_name TEXT,
        user_email TEXT,
        status TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()


# =========================
# HOME PAGE
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()


# =========================
# BORROW JIG (có check trùng)
# =========================
@app.post("/borrow")
def borrow_jig(data: BorrowRequest):
    conn = get_conn()
    cur = conn.cursor()

    # 🔥 check JIG đang được mượn chưa
    cur.execute("""
    SELECT * FROM jig_log
    WHERE jig_name=%s AND status='BORROW'
    ORDER BY time DESC LIMIT 1
    """, (data.jig_name,))

    active = cur.fetchone()

    if active:
        cur.close()
        conn.close()
        return {"error": "JIG đang được sử dụng!"}

    # insert borrow
    cur.execute("""
    INSERT INTO jig_log (jig_name, user_name, user_email, status)
    VALUES (%s, %s, %s, %s)
    """, (data.jig_name, data.user_name, data.user_email, "BORROW"))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Borrow success"}


# =========================
# RETURN JIG
# =========================
@app.post("/return")
def return_jig(data: ReturnRequest):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO jig_log (jig_name, status)
    VALUES (%s, %s)
    """, (data.jig_name, "RETURN"))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Return success"}


# =========================
# GET LOGS
# =========================
@app.get("/logs")
def get_logs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT jig_name, user_name, status, time
    FROM jig_log
    ORDER BY time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # format cho đẹp
    result = []
    for r in rows:
        result.append({
            "jig": r[0],
            "user": r[1],
            "status": r[2],
            "time": str(r[3])
        })

    return result