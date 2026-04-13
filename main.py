from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
import sqlite3
import uuid
import qrcode
from datetime import datetime
import os

app = FastAPI()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

conn = sqlite3.connect("jig.db", check_same_thread=False)
cursor = conn.cursor()

# ===== INIT DB =====
cursor.execute("""
CREATE TABLE IF NOT EXISTS JIGS (
    id TEXT PRIMARY KEY,
    status TEXT,
    current_tx TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS TRANSACTIONS (
    id TEXT,
    jig_id TEXT,
    user TEXT,
    borrow_time TEXT,
    expected_return TEXT,
    return_time TEXT,
    returned_by TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS COMMENTS (
    id TEXT,
    jig_id TEXT,
    user TEXT,
    content TEXT,
    time TEXT
)
""")

conn.commit()

# INIT DATA
for jig in ["T-1-2-1", "T-1-2-2", "T-1-2-3"]:
    cursor.execute("INSERT OR IGNORE INTO JIGS VALUES (?, 'AVAILABLE', NULL)", (jig,))
conn.commit()

# ===== MAIN UI =====
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
    <title>JIG Manager</title>
    <style>
    body { margin:0; font-family:Arial; display:flex; }
    .sidebar {
        width:220px;
        background:#1e1e2f;
        color:white;
        height:100vh;
        padding:10px;
    }
    .sidebar button {
        width:100%;
        margin:5px 0;
        padding:12px;
        background:#333;
        color:white;
        border:none;
        cursor:pointer;
    }
    .content {
        flex:1;
        padding:20px;
    }
    table {
        width:100%;
        border-collapse: collapse;
    }
    td, th {
        border:1px solid #ccc;
        padding:8px;
        text-align:center;
    }
    </style>

    <script>
    async function loadTab(tab){
        let res = await fetch("/tab/" + tab)
        let html = await res.text()
        document.getElementById("content").innerHTML = html
    }

    setInterval(()=>loadTab('dashboard'),3000)
    </script>
    </head>

    <body onload="loadTab('dashboard')">
        <div class="sidebar">
            <h3>JIG System</h3>
            <button onclick="loadTab('dashboard')">Dashboard</button>
            <button onclick="loadTab('scan')">Scan QR</button>
            <button onclick="loadTab('history')">Lịch sử</button>
            <button onclick="loadTab('comment')">Comment</button>
        </div>

        <div class="content" id="content"></div>
    </body>
    </html>
    """

# ===== DASHBOARD =====
@app.get("/tab/dashboard", response_class=HTMLResponse)
def dashboard():
    cursor.execute("SELECT * FROM JIGS")
    data = cursor.fetchall()

    html = "<h2>Danh sách JIG</h2><table><tr><th>JIG</th><th>Status</th><th>Action</th></tr>"

    for jig, status, tx in data:
        if status == "AVAILABLE":
            color = "green"
            action = f"<button onclick=\"loadTab('borrow_form?jig={jig}')\">Mượn</button>"
        else:
            color = "red"
            action = "Đang sử dụng"

        html += f"<tr><td>{jig}</td><td style='color:{color}'>{status}</td><td>{action}</td></tr>"

    html += "</table>"
    return html

# ===== BORROW FORM =====
@app.get("/tab/borrow_form", response_class=HTMLResponse)
def borrow_form(jig: str):
    return f"""
    <h2>Mượn {jig}</h2>
    <form action="/borrow" method="post">
        Tên: <input name="user"><br><br>
        Ngày trả dự kiến: <input type="datetime-local" name="expected"><br><br>
        <input type="hidden" name="jig_id" value="{jig}">
        <button type="submit">Xác nhận</button>
    </form>
    """

# ===== BORROW =====
@app.post("/borrow", response_class=HTMLResponse)
def borrow(jig_id: str = Form(...), user: str = Form(...), expected: str = Form(...)):
    tx_id = str(uuid.uuid4())

    cursor.execute("UPDATE JIGS SET status='IN_USE', current_tx=? WHERE id=?", (tx_id, jig_id))
    cursor.execute("""
    INSERT INTO TRANSACTIONS VALUES (?, ?, ?, ?, ?, NULL, NULL)
    """, (tx_id, jig_id, user, datetime.now().isoformat(), expected))

    conn.commit()

    url = f"{BASE_URL}/return?tx={tx_id}"
    img = qrcode.make(url)
    path = f"{tx_id}.png"
    img.save(path)

    return f"""
    <h2>QR Code</h2>
    <p>Scan để trả JIG</p>
    <img src="/qr/{tx_id}">
    """

# ===== QR =====
@app.get("/qr/{tx_id}")
def get_qr(tx_id: str):
    return FileResponse(f"{tx_id}.png")

# ===== SCAN PAGE =====
@app.get("/tab/scan", response_class=HTMLResponse)
def scan_page():
    return """
    <h2>Scan QR để trả JIG</h2>

    <div id="reader" style="width:300px;"></div>

    <script src="https://unpkg.com/html5-qrcode"></script>

    <script>
    function onScanSuccess(decodedText) {
        window.location.href = decodedText;
    }

    let scanner = new Html5QrcodeScanner("reader", {
        fps: 10,
        qrbox: 250
    });

    scanner.render(onScanSuccess);
    </script>
    """

# ===== RETURN PAGE =====
@app.get("/return", response_class=HTMLResponse)
def return_page(tx: str):
    cursor.execute("SELECT jig_id, user FROM TRANSACTIONS WHERE id=?", (tx,))
    data = cursor.fetchone()

    if not data:
        return "Invalid QR"

    jig_id, user = data

    return f"""
    <h2>Trả JIG</h2>
    <p>JIG: {jig_id}</p>
    <p>Người mượn: {user}</p>

    <form action="/confirm_return" method="post">
        <input type="hidden" name="tx" value="{tx}">
        Tên người trả: <input name="returned_by"><br><br>
        <button type="submit">Xác nhận trả</button>
    </form>
    """

# ===== CONFIRM RETURN =====
@app.post("/confirm_return", response_class=HTMLResponse)
def confirm_return(tx: str = Form(...), returned_by: str = Form(...)):
    cursor.execute("SELECT jig_id FROM TRANSACTIONS WHERE id=?", (tx,))
    jig_id = cursor.fetchone()[0]

    cursor.execute("""
    UPDATE TRANSACTIONS
    SET return_time=?, returned_by=?
    WHERE id=?
    """, (datetime.now().isoformat(), returned_by, tx))

    cursor.execute("UPDATE JIGS SET status='AVAILABLE', current_tx=NULL WHERE id=?", (jig_id,))

    conn.commit()

    return "<h2>Đã trả thành công</h2>"

# ===== HISTORY =====
@app.get("/tab/history", response_class=HTMLResponse)
def history():
    cursor.execute("SELECT * FROM TRANSACTIONS ORDER BY borrow_time DESC")
    data = cursor.fetchall()

    html = "<h2>Lịch sử</h2><table><tr><th>JIG</th><th>User</th><th>Mượn</th><th>Trả</th></tr>"

    for row in data:
        _, jig, user, bt, exp, rt, rb = row
        html += f"<tr><td>{jig}</td><td>{user}</td><td>{bt}</td><td>{rt or ''}</td></tr>"

    html += "</table>"
    return html

# ===== COMMENT =====
@app.get("/tab/comment", response_class=HTMLResponse)
def comment():
    cursor.execute("SELECT * FROM COMMENTS ORDER BY time DESC")
    data = cursor.fetchall()

    html = """
    <h2>Comment</h2>
    <form action="/add_comment" method="post">
        JIG: <input name="jig"><br>
        User: <input name="user"><br>
        Nội dung: <input name="content"><br>
        <button type="submit">Gửi</button>
    </form>
    <hr>
    """

    for _, jig, user, content, time in data:
        html += f"<p><b>{jig}</b>: {content} ({user})</p>"

    return html

@app.post("/add_comment", response_class=HTMLResponse)
def add_comment(jig: str = Form(...), user: str = Form(...), content: str = Form(...)):
    cursor.execute("""
    INSERT INTO COMMENTS VALUES (?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), jig, user, content, datetime.now().isoformat()))
    conn.commit()

    return "<h3>Đã thêm comment</h3>"