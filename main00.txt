from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, FileResponse
import sqlite3, uuid, qrcode, os
from datetime import datetime

app = FastAPI()
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

conn = sqlite3.connect("jig.db", check_same_thread=False)
cursor = conn.cursor()

# ===== DB =====
cursor.execute("CREATE TABLE IF NOT EXISTS JIGS (id TEXT PRIMARY KEY, status TEXT, current_tx TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS TRANSACTIONS (id TEXT, jig_id TEXT, user TEXT, borrow_time TEXT, expected_return TEXT, return_time TEXT, returned_by TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS COMMENTS (id TEXT, jig_id TEXT, user TEXT, content TEXT, time TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS RESERVATIONS (id TEXT, jig_id TEXT, user TEXT, time TEXT)")
conn.commit()

for jig in ["T-1-2-1","T-1-2-2","T-1-2-3"]:
    cursor.execute("INSERT OR IGNORE INTO JIGS VALUES (?, 'AVAILABLE', NULL)", (jig,))
conn.commit()

# ===== MAIN UI =====
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>JIG System</title>

<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">

<style>
body { margin:0; font-family:Arial; display:flex; background:#f5f6fa; }

.sidebar {
    width:240px;
    background:#111827;
    color:white;
    height:100vh;
    padding:20px 10px;
}

.sidebar h2 {
    text-align:center;
    margin-bottom:20px;
}

.menu-item {
    padding:12px;
    margin:6px 0;
    cursor:pointer;
    border-radius:8px;
}

.menu-item:hover {
    background:#374151;
}

.active {
    background:#2563eb;
}

.content {
    flex:1;
    padding:20px;
}

.card {
    background:white;
    padding:15px;
    border-radius:10px;
    box-shadow:0 2px 5px rgba(0,0,0,0.1);
}

table {
    width:100%;
    border-collapse: collapse;
}

th {
    background:#2563eb;
    color:white;
}

td, th {
    padding:10px;
    border-bottom:1px solid #ddd;
    text-align:center;
}

button {
    padding:6px 10px;
    border:none;
    background:#2563eb;
    color:white;
    border-radius:5px;
    cursor:pointer;
}
</style>

<script>
function setActive(el){
    document.querySelectorAll(".menu-item").forEach(e=>e.classList.remove("active"))
    el.classList.add("active")
}

async function loadTab(tab, el){
    if(el) setActive(el)
    let res = await fetch("/tab/" + tab)
    document.getElementById("content").innerHTML = await res.text()
}

setInterval(()=>loadTab('dashboard'),3000)
</script>
</head>

<body onload="loadTab('dashboard')">

<div class="sidebar">
    <h2>⚙️ JIG System</h2>

    <div class="menu-item active" onclick="loadTab('dashboard', this)">
        <i class="fa fa-home"></i> Dashboard
    </div>

    <div class="menu-item" onclick="loadTab('scan', this)">
        <i class="fa fa-camera"></i> Scan QR
    </div>

    <div class="menu-item" onclick="loadTab('history', this)">
        <i class="fa fa-clock"></i> History
    </div>

    <div class="menu-item" onclick="loadTab('comment', this)">
        <i class="fa fa-comment"></i> Comment
    </div>
</div>

<div class="content" id="content"></div>

</body>
</html>
"""