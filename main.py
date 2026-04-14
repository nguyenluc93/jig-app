import os
import psycopg2
from psycopg2 import pool
from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL")

db_pool = None

@app.on_event("startup")
def startup():
    global db_pool
    db_pool = pool.SimpleConnectionPool(1, 5, DATABASE_URL)

    conn = db_pool.getconn()
    cur = conn.cursor()

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

    conn.commit()
    cur.close()
    db_pool.putconn(conn)

def get_conn():
    return db_pool.getconn()

def release(conn):
    db_pool.putconn(conn)

# LOGIN
@app.get("/", response_class=HTMLResponse)
def login():
    return """
    <form action="/login" method="post">
    <input name="username">
    <input name="password" type="password">
    <button>Login</button>
    </form>
    """

@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...)):
    return RedirectResponse(f"/home?user={username}", status_code=302)

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    with open("templates/index.html") as f:
        html = f.read()
    return html.replace("{{username}}", user)

# BORROW
class Borrow(BaseModel):
    jig_name:str
    user:str

@app.post("/borrow")
def borrow(data:Borrow):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO jig_log(jig_name,borrow_user,status) VALUES(%s,%s,'BORROW')",
                (data.jig_name,data.user))
    conn.commit()
    cur.close();release(conn)
    return {"msg":"ok"}

# RETURN
class Return(BaseModel):
    jig_name:str
    user:str

@app.post("/return")
def return_jig(data:Return):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO jig_log(jig_name,return_user,status) VALUES(%s,%s,'RETURN')",
                (data.jig_name,data.user))
    conn.commit()
    cur.close();release(conn)
    return {"msg":"ok"}

# STATUS
@app.get("/jig-status")
def status():
    conn=get_conn();cur=conn.cursor()
    cur.execute("""
    SELECT DISTINCT ON (jig_name) jig_name,status
    FROM jig_log ORDER BY jig_name,time DESC
    """)
    rows=cur.fetchall()
    cur.close();release(conn)

    return {r[0]:r[1] for r in rows}

# QR AUTO RETURN PAGE
@app.get("/return-page", response_class=HTMLResponse)
def return_page(jigs: str = Query(...)):
    return f"""
    <h2>Return JIG</h2>
    <input id="user" placeholder="Your name">
    <button onclick="go()">Return</button>

    <script>
    async function go(){{
        let user=document.getElementById('user').value
        let arr="{jigs}".split(",")

        for(let j of arr){{
            await fetch('/return',{{
                method:'POST',
                headers:{{'Content-Type':'application/json'}},
                body:JSON.stringify({{jig_name:j,user:user}})
            }})
        }}

        alert("Done")
    }}
    </script>
    """