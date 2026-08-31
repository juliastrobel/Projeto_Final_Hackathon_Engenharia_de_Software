import httpx  # para chamar a API de troca de código por token
import os
import secrets
import sqlite3
#import smtplib
import resend
#from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

load_dotenv()  # carrega as variáveis do .env logo no início

BASE_URL = os.getenv("BASE_URL") # para fazer deploy

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_db():
    conn = sqlite3.connect("hackathon.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/inscricao", response_class=HTMLResponse)
async def form_inscricao(request: Request):
    return templates.TemplateResponse(request, "inscricao.html", {})

@app.post("/inscricao")
async def receber_inscricao(
    team_name: str = Form(...),
    leader_email: str = Form(...),
    member_names: list[str] = Form(...),
):
    nomes_validos = [nome for nome in member_names if nome.strip()]

    if not (3 <= len(nomes_validos) <= 5):
        return {"erro": "A equipe deve ter entre 3 e 5 integrantes preenchidos"}

    verify_token = secrets.token_urlsafe(32)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO teams (team_name, leader_email, leader_email_verified, verify_token) VALUES (?, ?, 0, ?)",
        (team_name, leader_email, verify_token),
    )
    team_id = cur.lastrowid

    for nome in nomes_validos:
        cur.execute(
            "INSERT INTO team_members (team_id, member_name) VALUES (?, ?)",
            (team_id, nome),
        )

    conn.commit()
    conn.close()

    enviar_email_verificacao(leader_email, verify_token)

    return {"status": "inscrição recebida, verifique seu email"}


def enviar_email_verificacao(email: str, token: str):
    resend.api_key = os.getenv("RESEND_API_KEY")

    link = f"{BASE_URL}/verify?token={token}"

    resend.Emails.send({
        "from": "Hackathon <onboarding@resend.dev>",
        "to": [email],
        "subject": "Confirme seu email - Hackathon",
        "html": f"""
            <p>Confirme sua inscrição clicando no link:</p>
            <p><a href="{link}">Confirmar inscrição</a></p>
        """

    })
    #gmail_user = os.getenv("GMAIL_USER")
    #gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    #link = f"http://localhost:8000/verify?token={token}"
    #corpo = f"Confirme sua inscrição clicando no link: {link}"

    #msg = MIMEText(corpo)
    #msg["Subject"] = "Confirme seu email - Hackathon"
    #msg["From"] = gmail_user
    #msg["To"] = email

    #with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        #server.login(gmail_user, gmail_password)
        #server.send_message(msg)


@app.get("/verify")
async def verificar_email(token: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM teams WHERE verify_token = ?", (token,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return {"erro": "token inválido"}

    cur.execute(
        "UPDATE teams SET leader_email_verified = 1 WHERE id = ?", (row["id"],)
    )
    conn.commit()
    conn.close()
    
    #return {"status": "email verificado com sucesso", "team_id": row["id"]}
    return RedirectResponse(url=f"/login?team_id={row['id']}")

@app.get("/login")
async def login(team_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT leader_email_verified FROM teams WHERE id = ?", (team_id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row["leader_email_verified"]:
        return {"erro": "Verifique seu email antes de conectar o GitHub"}

    client_id = os.getenv("GITHUB_CLIENT_ID")
    redirect_uri = "http://localhost:8000/auth/callback"

    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={team_id}"  # usamos o state pra saber qual equipe está autorizando
        f"&scope=repo"
    )

    return RedirectResponse(url=github_auth_url)

@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    team_id = int(state)  # veio do parâmetro state que passamos no /login

    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": "http://localhost:8000/auth/callback",
            },
            headers={"Accept": "application/json"},
        )

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return {"erro": "falha ao obter token", "detalhes": token_data}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teams SET github_token = ? WHERE id = ?", (access_token, team_id)
    )
    conn.commit()
    conn.close()

    return {"status": "GitHub conectado com sucesso", "team_id": team_id}
