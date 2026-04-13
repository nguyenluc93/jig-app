from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
import psycopg2
import uuid, qrcode, os
from datetime import datetime

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# ===== INIT DB =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS jigs (
    id TEXT PRIMARY KEY,
    status TEXT,
    current_tx TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT,
    jig_id TEXT,
    user_name TEXT,
    borrow_time TEXT,
    expected_return TEXT,
    return_time TEXT,
    returned_by TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reservations (
    id TEXT,
    jig_id TEXT,
    user_name TEXT,
    time TEXT
)
""")

conn.commit()

# INIT DATA
for jig in ["T-1-2-1","T-1-2-2","T-1-2-3"]:
    cursor.execute("INSERT INTO jigs VALUES (%s,'AVAILABLE',NULL) ON CONFLICT DO NOTHING", (jig,))
conn.commit()

# ===== UI =====
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head><title>JIG管理</title></head>
    <body>
    <h1>JIG管理システム</h1>
    <a href="/dashboard">Dashboard</a>
    </body>
    </html>
    """

# ===== DASHBOARD =====
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    cursor.execute("SELECT * FROM jigs")
    data = cursor.fetchall()

    html = "<h2>JIG一覧</h2><table border=1><tr><th>JIG</th><th>Status</th><th>Action</th></tr>"

    for jig, status, tx in data:
        if status == "AVAILABLE":
            action = f"<a href='/borrow_form?jig={jig}'>貸出</a>"
        else:
            action = "使用中"

        html += f"<tr><td>{jig}</td><td>{status}</td><td>{action}</td></tr>"

    html += "</table>"
    return html

# ===== BORROW FORM =====
@app.get("/borrow_form", response_class=HTMLResponse)
def borrow_form(jig: str):
    return f"""
    <h2>{jig} 貸出</h2>
    <form action="/borrow" method="post">
    使用者: <input name="user"><br>
    <input type="hidden" name="jig_id" value="{jig}">
    <button type="submit">OK</button>
    </form>
    """

# ===== BORROW =====
@app.post("/borrow", response_class=HTMLResponse)
def borrow(jig_id: str = Form(...), user: str = Form(...)):
    tx_id = str(uuid.uuid4())

    cursor.execute("UPDATE jigs SET status='IN_USE', current_tx=%s WHERE id=%s", (tx_id, jig_id))

    cursor.execute("""
    INSERT INTO transactions VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (tx_id, jig_id, user, datetime.now().isoformat(), "", None, None))

    conn.commit()

    url = f"{BASE_URL}/return?tx={tx_id}"
    img = qrcode.make(url)
    path = f"{tx_id}.png"
    img.save(path)

    return f"<h2>QR</h2><img src='/qr/{tx_id}'>"

# ===== QR =====
@app.get("/qr/{tx_id}")
def qr(tx_id: str):
    return FileResponse(f"{tx_id}.png")

# ===== RETURN =====
@app.get("/return", response_class=HTMLResponse)
def return_page(tx: str):
    return f"""
    <form action="/confirm_return" method="post">
    <input type="hidden" name="tx" value="{tx}">
    返却者: <input name="returned_by">
    <button type="submit">返却</button>
    </form>
    """

# ===== CONFIRM RETURN =====
@app.post("/confirm_return", response_class=HTMLResponse)
def confirm_return(tx: str = Form(...), returned_by: str = Form(...)):
    cursor.execute("SELECT jig_id FROM transactions WHERE id=%s", (tx,))
    jig_id = cursor.fetchone()[0]

    cursor.execute("UPDATE transactions SET return_time=%s, returned_by=%s WHERE id=%s",
                   (datetime.now().isoformat(), returned_by, tx))

    cursor.execute("UPDATE jigs SET status='AVAILABLE', current_tx=NULL WHERE id=%s", (jig_id,))
    conn.commit()

    return "返却完了"