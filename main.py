import os
import psycopg2
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# ================= DB INIT =================
@app.on_event("startup")
def startup():
    conn = get_conn()
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS comment(
        id SERIAL PRIMARY KEY,
        user_name TEXT,
        content TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cur.close()
    conn.close()

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

    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",(username,password))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if user:
        return RedirectResponse(url=f"/home?user={username}",status_code=302)
    return {"error":"fail"}

@app.get("/home", response_class=HTMLResponse)
def home(user: str):
    with open("templates/index.html",encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{username}}",user)

# ================= USER =================
@app.post("/add-user")
def add_user(username: str = Form(...), password: str = Form(...)):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO users VALUES(DEFAULT,%s,%s)",(username,password))
    conn.commit();cur.close();conn.close()
    return {"msg":"ok"}

# ================= BORROW =================
class Borrow(BaseModel):
    jig_name:str
    user:str

@app.post("/borrow")
def borrow(data:Borrow):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO jig_log(jig_name,borrow_user,status) VALUES(%s,%s,'BORROW')",
                (data.jig_name,data.user))
    conn.commit();cur.close();conn.close()
    return {"msg":"ok"}

# ================= RETURN =================
class Return(BaseModel):
    jig_name:str
    user:str

@app.post("/return")
def return_jig(data:Return):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO jig_log(jig_name,return_user,status) VALUES(%s,%s,'RETURN')",
                (data.jig_name,data.user))
    conn.commit();cur.close();conn.close()
    return {"msg":"ok"}

# ================= STATUS =================
@app.get("/jig-status")
def jig_status():
    conn=get_conn();cur=conn.cursor()
    cur.execute("""
    SELECT DISTINCT ON (jig_name) jig_name,status,borrow_user
    FROM jig_log
    ORDER BY jig_name,time DESC
    """)
    rows=cur.fetchall()
    cur.close();conn.close()

    result={}
    for r in rows:
        result[r[0]]={"status":r[1],"user":r[2]}
    return result

# ================= RESERVE =================
class Reserve(BaseModel):
    jig_name:str
    user:str

@app.post("/reserve")
def reserve(data:Reserve):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO reserve(jig_name,user_name) VALUES(%s,%s)",
                (data.jig_name,data.user))
    conn.commit();cur.close();conn.close()
    return {"msg":"ok"}

# ================= COMMENT =================
class Comment(BaseModel):
    user:str
    content:str

@app.post("/comment")
def comment(data:Comment):
    conn=get_conn();cur=conn.cursor()
    cur.execute("INSERT INTO comment(user_name,content) VALUES(%s,%s)",
                (data.user,data.content))
    conn.commit();cur.close();conn.close()
    return {"msg":"ok"}

@app.get("/comment")
def get_comment():
    conn=get_conn();cur=conn.cursor()
    cur.execute("SELECT user_name,content,time FROM comment ORDER BY time DESC")
    rows=cur.fetchall()
    cur.close();conn.close()

    return [{"user":r[0],"content":r[1],"time":str(r[2])} for r in rows]