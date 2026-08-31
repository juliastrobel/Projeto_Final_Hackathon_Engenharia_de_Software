import httpx
import os
import secrets
import sqlite3
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

BASE_URL = os.getenv("BASE_URL")

app = FastAPI()

DB_PATH = "/app/data/hackathon.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)

    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


init_db()

templates = Jinja2Templates(directory="templates")


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
        """
        INSERT INTO teams
        (team_name, leader_email, leader_email_verified, verify_token)
        VALUES (?, ?, 0, ?)
        """,
        (team_name, leader_email, verify_token),
    )

    team_id = cur.lastrowid

    for nome in nomes_validos:
        cur.execute(
            """
            INSERT INTO team_members
            (team_id, member_name)
            VALUES (?, ?)
            """,
            (team_id, nome),
        )

    conn.commit()
    conn.close()

    enviar_email_verificacao(leader_email, verify_token)

    return {
        "status": "inscrição recebida, verifique seu email"
    }

def enviar_email_verificacao(email: str, token: str):
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")

    link = f"{BASE_URL}/verify?token={token}"

    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "sender": {
                "name": "Hackathon IFPR",
                "email": sender_email,
            },
            "to": [
                {
                    "email": email
                }
            ],
            "subject": "Confirme seu email - Hackathon",
            "htmlContent": f"""
                <p>Confirme sua inscrição clicando no link:</p>

                <p>
                    <a href="{link}">
                        Confirmar inscrição
                    </a>
                </p>

                <p>
                    Se você não fez essa inscrição, ignore este e-mail.
                </p>
            """,
        },
        timeout=30,
    )

    if response.status_code >= 400:
        raise Exception(
            f"Erro ao enviar email pela Brevo: "
            f"{response.status_code} - {response.text}"
        )

@app.get("/verify")
async def verificar_email(token: str):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM teams WHERE verify_token = ?",
        (token,),
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return {"erro": "token inválido"}

    cur.execute(
        "UPDATE teams SET leader_email_verified = 1 WHERE id = ?",
        (row["id"],),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        url=f"/login?team_id={row['id']}"
    )


@app.get("/login")
async def login(team_id: int):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT leader_email_verified FROM teams WHERE id = ?",
        (team_id,),
    )

    row = cur.fetchone()
    conn.close()

    if not row or not row["leader_email_verified"]:
        return {
            "erro": "Verifique seu email antes de conectar o GitHub"
        }

    client_id = os.getenv("GITHUB_CLIENT_ID")

    redirect_uri = f"{BASE_URL}/auth/callback"

    github_auth_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={team_id}"
    )

    return RedirectResponse(url=github_auth_url)


@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    team_id = int(state)

    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    redirect_uri = f"{BASE_URL}/auth/callback"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Accept": "application/json"
            },
        )

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return {
            "erro": "falha ao obter token",
            "detalhes": token_data,
        }

    user_response = await client.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            },
        )

    user_data = user_response.json()
    github_username = user_data.get("login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE teams
        SET github_token = ?
        WHERE id = ?
        """,
        (access_token, team_id),
    )

    conn.commit()
    conn.close()

    return {
        "status": "GitHub conectado com sucesso",
        "github_username": github_username,
    }

@app.get("/debug/oauth")
async def debug_oauth():
    return {
        "client_id_usado": os.getenv("GITHUB_CLIENT_ID"),
        "client_secret_primeiros_chars": (os.getenv("GITHUB_CLIENT_SECRET") or "")[:6],
        "client_secret_tamanho": len(os.getenv("GITHUB_CLIENT_SECRET") or ""),
    }

