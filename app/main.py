import secrets
import sqlite3
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_db():
    conn = sqlite3.connect("verifier.db")
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
    # remove campos vazios (integrante 4 e 5 são opcionais no form)
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

    return {"status": "inscrição recebida", "team_id": team_id, "verify_token": verify_token}
