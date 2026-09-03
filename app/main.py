import httpx
import os
import secrets
import sqlite3
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo


BRASILIA = ZoneInfo("America/Sao_Paulo")

load_dotenv()

RESULTS_RELEASED = os.getenv("RESULTS_RELEASED", "false").strip().lower() == "true"

BASE_URL = os.getenv("BASE_URL")

GITHUB_PAT = os.getenv("GITHUB_PAT", "").strip()

EVENT_START = datetime.fromisoformat(
    os.getenv("EVENT_START")
).replace(tzinfo=BRASILIA)

EVENT_END = datetime.fromisoformat(
    os.getenv("EVENT_END")
).replace(tzinfo=BRASILIA)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

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

def formatar_data(data):
    return data.strftime("%d/%m/%Y às %H:%M:%S")


init_db()

templates = Jinja2Templates(directory="templates")


@app.get("/inscricao", response_class=HTMLResponse)
async def form_inscricao(request: Request):
    return templates.TemplateResponse(request, "inscricao.html", {})


@app.post("/inscricao")
async def receber_inscricao(
    request: Request,
    team_name: str = Form(...),
    leader_name: str = Form(...),
    leader_email: str = Form(...),
    member_names: list[str] = Form(...),
):
    nomes_validos = [nome.strip() for nome in member_names if nome.strip()]

    total_integrantes = 1 + len(nomes_validos)

    if not (3 <= total_integrantes <= 5):
        return templates.TemplateResponse(
            request,
            "inscricao.html",
            {
                "erro": "A equipe deve ter entre 3 e 5 integrantes (incluindo o líder)."
            },
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM teams
        WHERE LOWER(TRIM(team_name)) = LOWER(?)
        """,
        (team_name,),
    )

    equipe_existente = cur.fetchone()

    if equipe_existente:
        conn.close()

        return templates.TemplateResponse(
            request,
            "inscricao.html",
            {
                "erro": "Já existe uma equipe cadastrada com esse nome."
            },
        )

    cur.execute(
        """
        SELECT id FROM teams
        WHERE LOWER(TRIM(leader_email)) = LOWER(?)
        """,
        (leader_email,),
    )

    email_existente = cur.fetchone()

    if email_existente:
        conn.close()

        return templates.TemplateResponse(
            request,
            "inscricao.html",
            {
                "erro": "Este e-mail já está cadastrado como líder de outra equipe."
            },
        )

    verify_token = secrets.token_urlsafe(32)
    access_token = secrets.token_urlsafe(32)

    cur.execute(
        """
        INSERT INTO teams
        (team_name, leader_name, leader_email, leader_email_verified, verify_token, access_token)
        VALUES (?, ?, ?, 0, ?, ?)
        """,
        (team_name, leader_name, leader_email, verify_token, access_token),
    )

    team_id = cur.lastrowid
    
    cur.execute(
    """
    INSERT INTO team_members
    (team_id, member_name, is_leader)
    VALUES (?, ?, 1)
    """,
    (team_id, leader_name),
    )
    
    for nome in nomes_validos:
        cur.execute(
            """
            INSERT INTO team_members
            (team_id, member_name, is_leader)
            VALUES (?, ?, 0)
            """,
            (team_id, nome),
        )

    conn.commit()
    conn.close()

    enviar_email_verificacao(leader_email, verify_token)
    
    return templates.TemplateResponse(
        request,
        "verificacao.html",
        {"team_name": team_name, "leader_email": leader_email},
    )

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
                <p>Confirme sua inscrição clicando no link abaixo:</p>

                <p>
                    <a href="{link}">
                        Confirmar inscrição no Hackathon IFPR 2026
                    </a>
                </p>

                <p>
                    Se não foi você que fez essa inscrição, favor ignorar este e-mail.
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

def enviar_email_area_equipe(email: str, link: str):
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")

    httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "sender": {"name": "Hackathon IFPR", "email": sender_email},
            "to": [{"email": email}],
            "subject": "Seu link de acesso chegou - Área da Equipe",
            "htmlContent": f"""
                <p>Guarde este link como garantia para acessar a área da sua equipe ou simplesmente realize login com o Github</p>
                <p><a href="{link}">{link}</a></p>
                <p>Por favor, não compartilhe este link com outras equipes.</p>
            """,
        },
        timeout=30,
    )

@app.get("/verify")
async def verificar_email(token: str, request: Request):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM teams WHERE verify_token = ?",
        (token,),
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Link de verificação inválido.",  "link_voltar": "/"},
        )
        
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
async def login(team_id: int, request: Request):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT leader_email_verified FROM teams WHERE id = ?",
        (team_id,),
    )

    row = cur.fetchone()
    conn.close()

    if not row or not row["leader_email_verified"]:
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Verifique seu email antes de conectar o GitHub.", "link_voltar": "/"},
        )

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
async def auth_callback(code: str, state: str, request: Request):

    equipe_login_state = request.cookies.get("equipe_login_state")
    equipe_login_team_id = request.cookies.get("equipe_login_team_id")

    login_equipe = (
        equipe_login_state is not None
        and equipe_login_team_id is not None
        and secrets.compare_digest(equipe_login_state, state)
    )

    team_id = None
    
    if not login_equipe:
        try:
            team_id = int(state)
        except ValueError:
            return templates.TemplateResponse(
                request, "erro.html",
                {"mensagem": "Parâmetro de estado inválido.", "link_voltar": "/"},
            )

    client_id = os.getenv("GITHUB_CLIENT_ID", "").strip()
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "").strip()
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
            headers={"Accept": "application/json"},
        )

        token_data = response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            return templates.TemplateResponse(
                request, "erro.html",
                {"mensagem": "Falha ao obter token do GitHub. Tente novamente.", "link_voltar": "/"},
            )

        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
    
    if user_response.status_code != 200:
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Falha ao consultar usuário do GitHub.", "link_voltar": "/"},
        )

    user_data = user_response.json()
    github_username = user_data.get("login")

    if not github_username:
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Não foi possível identificar o usuário do GitHub.", "link_voltar": "/"},
        )

    if login_equipe:

        conn = get_db()
        cur = conn.cursor()

        try:
            login_team_id = int(equipe_login_team_id)
        except (TypeError, ValueError):
            conn.close()
            return templates.TemplateResponse(
                request,
                "erro.html",
                {
                    "mensagem": "Sessão de login inválida.",
                    "link_voltar": "/equipe/login",
                },
            )

        cur.execute(
            """
            SELECT teams.id,
                   teams.team_name,
                   teams.leader_name,
                   teams.leader_email,
                   teams.github_username
            FROM team_members
            JOIN teams
                ON teams.id = team_members.team_id
            WHERE teams.id = ?
              AND team_members.github_username = ?
              AND team_members.is_leader = 1
              AND teams.leader_email_verified = 1
            """,
            (login_team_id, github_username),
        )

        team = cur.fetchone()

        if not team:
            conn.close()

            response = templates.TemplateResponse(
                request,
                "erro.html",
                {
                    "mensagem": (
                        "A conta do GitHub utilizada não corresponde "
                        "ao líder da equipe vinculada a este e-mail."
                    ),
                    "link_voltar": "/equipe/login",
                },
            )

            response.delete_cookie("equipe_login_state")
            response.delete_cookie("equipe_login_team_id")

            return response

        # Cria uma nova sessão da equipe
        session_token = secrets.token_urlsafe(32)

        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(hours=8)

        cur.execute(
            """
            INSERT INTO team_sessions
            (team_id, session_token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                team["id"],
                session_token,
                created_at.isoformat(),
                expires_at.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        response = RedirectResponse(
            url=f"/equipe/{team['id']}",
            status_code=303,
        )

        response.set_cookie(
            key="equipe_session",
            value=session_token,
            httponly=True,
            max_age=60 * 60 * 8,
            samesite="lax",
        )

        response.delete_cookie("equipe_login_state")
        response.delete_cookie("equipe_login_team_id")

        return response

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teams SET github_username = ? WHERE id = ?",
        (github_username, team_id),
    )
    cur.execute(
    """
    UPDATE team_members
    SET github_username = ?
    WHERE team_id = ? AND is_leader = 1
    """,
    (github_username, team_id),
    )
    cur.execute("SELECT team_name, leader_email, access_token FROM teams WHERE id = ?", (team_id,))
    team_row = cur.fetchone()
    conn.commit()
    conn.close()

    link_area_equipe = f"{BASE_URL}/equipe/{team_id}?token={team_row['access_token']}"
    enviar_email_area_equipe(team_row["leader_email"], link_area_equipe)

    return templates.TemplateResponse(
        request,
        "sucesso.html",
        {
            "team_name": team_row["team_name"],
            "github_username": github_username,
            "link_area_equipe": link_area_equipe,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse(request, "home.html", {"cronograma": CRONOGRAMA, "cronograma_marcos": CRONOGRAMA_MARCOS},)

@app.get("/jurado/login", response_class=HTMLResponse)
async def jurado_login_form(request: Request):
    return templates.TemplateResponse(request, "jurado_login.html", {})


@app.post("/jurado/login")
async def jurado_login_enviar(request: Request, email: str = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM judges WHERE email = ?", (email,))
    judge = cur.fetchone()

    if judge:
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(minutes=15)).isoformat()

        cur.execute(
            "INSERT INTO judge_login_tokens (judge_id, token, expires_at) VALUES (?, ?, ?)",
            (judge["id"], token, expires_at),
        )
        conn.commit()

        link = f"{BASE_URL}/jurado/verify?token={token}"
        enviar_email_login_jurado(email, link)

    conn.close()

    # Mensagem genérica, mesmo se o email não for de um jurado cadastrado
    return templates.TemplateResponse(
        request, "jurado_login_enviado.html", {}
    )


def enviar_email_login_jurado(email: str, link: str):
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")

    httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "sender": {"name": "Hackathon IFPR", "email": sender_email},
            "to": [{"email": email}],
            "subject": "Seu link de acesso - Painel do Jurado",
            "htmlContent": f"""
                <p>Clique no link abaixo para acessar o painel de avaliação:</p>
                <p><a href="{link}">Acessar painel</a></p>
                <p>Este link expira em 15 minutos.</p>
            """,
        },
        timeout=30,
    )


@app.get("/jurado/verify")
async def jurado_verify(token: str, request: Request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, judge_id, expires_at, used FROM judge_login_tokens WHERE token = ?",
        (token,),
    )
    row = cur.fetchone()

    if not row or row["used"] or datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        conn.close()
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Link inválido ou expirado. Solicite um novo acesso."},
        )

    cur.execute("UPDATE judge_login_tokens SET used = 1 WHERE id = ?", (row["id"],))

    session_token = secrets.token_urlsafe(32)
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(hours=8)

    cur.execute(
        "INSERT INTO judge_sessions (judge_id, session_token, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (row["judge_id"], session_token, created_at.isoformat(), expires_at.isoformat()),
    )
    conn.commit()
    conn.close()

    response = RedirectResponse(url="/jurado/dashboard")
    response.set_cookie(
        key="jurado_session",
        value=session_token,
        httponly=True,
        max_age=60 * 60 * 8,  # 8 horas de sessão
    )
    return response


def get_jurado_logado(request: Request):
    session_token = request.cookies.get("jurado_session")
    if not session_token:
        return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT judges.id, judges.name, judges.email
        FROM judge_sessions
        JOIN judges ON judges.id = judge_sessions.judge_id
        WHERE judge_sessions.session_token = ?
        AND judge_sessions.expires_at > ?
        """,
        (session_token, datetime.utcnow().isoformat(),),
    )
    judge = cur.fetchone()
    conn.close()
    return judge

@app.get("/jurado/dashboard", response_class=HTMLResponse)
async def jurado_dashboard(request: Request, filtro: str | None = None):
    jurado = get_jurado_logado(request)
    if not jurado:
        return RedirectResponse(url="/jurado/login")

    conn = get_db()
    cur = conn.cursor()

    query = """
        SELECT teams.id, teams.team_name, teams.github_username,
               teams.veredito, teams.analisado_em, avaliacoes.nota
        FROM teams
        LEFT JOIN avaliacoes
            ON avaliacoes.team_id = teams.id AND avaliacoes.judge_id = ?
        WHERE teams.leader_email_verified = 1
    """
    params = [jurado["id"]]

    if filtro == "suspeito":
        query += " AND teams.veredito = ?"
        params.append("suspeito")
    elif filtro == "ok":
        query += " AND teams.veredito = ?"
        params.append("ok")

    query += " ORDER BY teams.veredito IS NULL, teams.veredito DESC, teams.team_name"

    cur.execute(query, params)
    equipes_raw = cur.fetchall()
    conn.close()

    equipes = []
    for e in equipes_raw:
        e = dict(e)
        if e["analisado_em"]:
            data_utc = datetime.fromisoformat(e["analisado_em"])
            e["analisado_em"] = formatar_data(data_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(BRASILIA))
        equipes.append(e)

    return templates.TemplateResponse(
        request, "jurado_dashboard.html",
        {"jurado": jurado, "equipes": equipes, "filtro": filtro},
    )

@app.get("/equipe/login", response_class=HTMLResponse)
async def equipe_login_form(request: Request):
    # Se a equipe já estiver autenticada, vai direto para a área dela.
    equipe = get_equipe_logada(request)

    if equipe:
        return RedirectResponse(
            url=f"/equipe/{equipe['id']}",
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "equipe_login.html",
        {},
    )


@app.post("/equipe/login")
async def equipe_login_enviar(
    request: Request,
    email: str = Form(...),
):
    email = email.strip().lower()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, team_name, leader_email, leader_email_verified
        FROM teams
        WHERE LOWER(TRIM(leader_email)) = ?
        """,
        (email,),
    )

    team = cur.fetchone()
    conn.close()

    if not team:
        return templates.TemplateResponse(
            request,
            "equipe_login.html",
            {
                "erro": "Este e-mail não está cadastrado como líder de nenhuma equipe.",
                "email": email,
            },
        )

    if not team["leader_email_verified"]:
        return templates.TemplateResponse(
            request,
            "equipe_login.html",
            {
                "erro": "Este e-mail ainda não foi verificado. Verifique seu e-mail antes de entrar.",
                "email": email,
            },
        )

    state = secrets.token_urlsafe(32)

    client_id = os.getenv("GITHUB_CLIENT_ID", "").strip()
    redirect_uri = f"{BASE_URL}/auth/callback"

    github_auth_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )

    response = RedirectResponse(
        url=github_auth_url,
        status_code=303,
    )

    response.set_cookie(
        key="equipe_login_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
    )

    # Guarda temporariamente qual equipe corresponde ao e-mail informado.
    response.set_cookie(
        key="equipe_login_team_id",
        value=str(team["id"]),
        httponly=True,
        max_age=600,
        samesite="lax",
    )

    return response

def get_equipe_logada(request: Request):
    session_token = request.cookies.get("equipe_session")

    if not session_token:
        return None

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT teams.id,
               teams.team_name,
               teams.leader_name,
               teams.leader_email,
               teams.github_username
        FROM team_sessions
        JOIN teams
            ON teams.id = team_sessions.team_id
        WHERE team_sessions.session_token = ?
          AND team_sessions.expires_at > ?
        """,
        (
            session_token,
            datetime.utcnow().isoformat(),
        ),
    )

    team = cur.fetchone()

    conn.close()

    return team

@app.get("/equipe/logout")
async def equipe_logout(request: Request):

    session_token = request.cookies.get("equipe_session")

    if session_token:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "DELETE FROM team_sessions WHERE session_token = ?",
            (session_token,),
        )

        conn.commit()
        conn.close()

    response = RedirectResponse(
        url="/",
        status_code=303,
    )

    response.delete_cookie(
        key="equipe_session",
        httponly=True,
        samesite="lax",
    )

    return response

async def analisar_e_salvar(team_id: int):
    """
    Busca dados do GitHub, calcula o veredito, salva no banco
    e retorna um dicionário com o resultado (ou um erro).
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT github_username, team_name FROM teams WHERE id = ?",
        (team_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row or not row["github_username"]:
        return {"erro": "Esta equipe ainda não conectou o GitHub."}

    username = row["github_username"]
    repo_full_name = f"{username}/hackathon-ifpr"
    headers = {"Authorization": f"Bearer {GITHUB_PAT}"} if GITHUB_PAT else {}

    async with httpx.AsyncClient() as client:
        repo_response = await client.get(
            f"https://api.github.com/repos/{repo_full_name}",
            headers=headers,
        )

        if repo_response.status_code == 404:
            return {"erro": f"Repositório {repo_full_name} não encontrado "
                             f"(deve ser público e se chamar exatamente hackathon-ifpr)."}

        if repo_response.status_code != 200:
            return {"erro": f"Erro ao consultar a API do GitHub (status {repo_response.status_code})."}

        repo_data = repo_response.json()

        commits_response = await client.get(
            f"https://api.github.com/repos/{repo_full_name}/commits",
            params={"per_page": 100},
            headers=headers,
        )

        if commits_response.status_code == 409:
            return {"erro": f"O repositório {repo_full_name} existe mas ainda não tem "
                             f"nenhum commit — a equipe precisa enviar código."}

        if commits_response.status_code != 200:
            return {"erro": f"Erro ao consultar commits na API do GitHub (status {commits_response.status_code})."}

        commits_data = commits_response.json()

    repo_created_at = datetime.fromisoformat(
        repo_data["created_at"].replace("Z", "+00:00")
    ).astimezone(BRASILIA)

    suspeitas = []
    if repo_created_at < EVENT_START:
        suspeitas.append(
            f"Repositório criado em {formatar_data(repo_created_at)}, "
            f"antes do início do evento ({formatar_data(EVENT_START)})"
        )

    commits_resumo = []
    for c in commits_data:
        data_commit = datetime.fromisoformat(
            c["commit"]["author"]["date"].replace("Z", "+00:00")
        ).astimezone(BRASILIA)

        fora_da_janela = data_commit < EVENT_START or data_commit > EVENT_END
        if fora_da_janela:
            suspeitas.append(
                f"Commit {c['sha'][:7]} realizado em "
                f"{formatar_data(data_commit)}, fora da janela do evento"
            )

        commits_resumo.append({
            "sha": c["sha"][:7],
            "autor": c["commit"]["author"]["name"],
            "data": formatar_data(data_commit),
            "mensagem": c["commit"]["message"],
            "fora_da_janela": fora_da_janela,
        })

    veredito = "suspeito" if suspeitas else "ok"
    analisado_em = datetime.utcnow()

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE teams SET veredito = ?, analisado_em = ? WHERE id = ?",
        (veredito, analisado_em.isoformat(), team_id),
    )
    conn.commit()
    conn.close()

    return {
        "equipe": row["team_name"],
        "repositorio": repo_full_name,
        "criado_em": repo_created_at,
        "veredito": veredito,
        "suspeitas": suspeitas,
        "commits": commits_resumo,
        "analisado_em": analisado_em.astimezone(BRASILIA),
    }

@app.get("/analise/{team_id}", response_class=HTMLResponse)
async def analisar_repositorio(team_id: int, request: Request):
    jurado = get_jurado_logado(request)
    equipe = get_equipe_logada(request)

    acesso_jurado = jurado is not None
    acesso_equipe = equipe is not None and equipe["id"] == team_id

    if not acesso_jurado and not acesso_equipe:
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Você não tem permissão para acessar esta análise.", "link_voltar": "/"},
        )

    link_voltar = "/jurado/dashboard" if acesso_jurado else f"/equipe/{team_id}"

    resultado = await analisar_e_salvar(team_id)

    if "erro" in resultado:
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": resultado["erro"], "link_voltar": link_voltar},
        )

    datas_commits = [c["data"] for c in resultado["commits"]]

    return templates.TemplateResponse(
        request, "analise.html",
        {
            **resultado,
            "datas_commits": datas_commits,
            "link_voltar": link_voltar,
        },
    )

@app.post("/jurado/atualizar-analises")
async def atualizar_analises(request: Request):
    jurado = get_jurado_logado(request)
    if not jurado:
        return RedirectResponse(url="/jurado/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM teams WHERE leader_email_verified = 1 AND github_username IS NOT NULL"
    )
    equipes = cur.fetchall()
    conn.close()

    for e in equipes:
        await analisar_e_salvar(e["id"])

    return RedirectResponse(url="/jurado/dashboard", status_code=303)

@app.get("/equipe/{team_id}", response_class=HTMLResponse)
async def area_equipe(
    team_id: int,
    request: Request,
    token: str | None = None,
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM teams WHERE id = ?",
        (team_id,),
    )

    team = cur.fetchone()

    if not team:
        conn.close()
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Equipe não encontrada."},
        )

    equipe_logada = get_equipe_logada(request)
    acesso_por_sessao = (
        equipe_logada is not None
        and equipe_logada["id"] == team_id
    )

    acesso_por_token = False
    if token:
        acesso_por_token = secrets.compare_digest(
            team["access_token"],
            token,
        )

    if not acesso_por_sessao and not acesso_por_token:
        conn.close()
        return templates.TemplateResponse(
            request, "erro.html",
            {"mensagem": "Você não tem permissão para acessar esta equipe."},
        )

    cur.execute(
        "SELECT * FROM team_members WHERE team_id = ?",
        (team_id,),
    )
    membros = cur.fetchall()
    conn.close()

    contributors = []
    if team["github_username"]:
        repo_full_name = f"{team['github_username']}/hackathon-ifpr"
        headers = {"Authorization": f"Bearer {GITHUB_PAT}"} if GITHUB_PAT else {}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/contributors",
                headers=headers,
            )
            if resp.status_code == 200:
                contributors = [
                    {"login": c["login"], "contributions": c["contributions"]}
                    for c in resp.json()
                ]

    return templates.TemplateResponse(
        request, "area_equipe.html",
        {
            "team": team,
            "membros": membros,
            "contributors": contributors,
            "token": token,
        },
    )

@app.post("/equipe/{team_id}/vincular-membros")
async def vincular_membros(
    team_id: int,
    request: Request,
    token: str | None = Form(None),
):
    form = await request.form()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM teams WHERE id = ?",
        (team_id,),
    )

    team = cur.fetchone()

    if not team:
        conn.close()

        return templates.TemplateResponse(
            request,
            "erro.html",
            {"mensagem": "Equipe não encontrada."},
        )

    # Verifica acesso pela sessão
    equipe_logada = get_equipe_logada(request)

    acesso_por_sessao = (
        equipe_logada is not None
        and equipe_logada["id"] == team_id
    )

    # Verifica acesso pelo token antigo
    acesso_por_token = False

    if token:
        acesso_por_token = secrets.compare_digest(
            team["access_token"],
            token,
        )

    if not acesso_por_sessao and not acesso_por_token:
        conn.close()

        return templates.TemplateResponse(
            request,
            "erro.html",
            {"mensagem": "Você não tem permissão para alterar esta equipe."},
        )

    cur.execute(
        """
        SELECT id
        FROM team_members
        WHERE team_id = ?
        """,
        (team_id,),
    )

    membros = cur.fetchall()

    for membro in membros:

        campo = f"github_username_{membro['id']}"

        valor = form.get(campo)

        if valor:
            valor = valor.strip()

            cur.execute(
                """
                UPDATE team_members
                SET github_username = ?
                WHERE id = ?
                """,
                (valor, membro["id"]),
            )

    conn.commit()
    conn.close()

    # Se entrou pelo link antigo, mantém o token
    if token:
        return RedirectResponse(
            url=f"/equipe/{team_id}?token={token}",
            status_code=303,
        )

    # Se entrou pelo login GitHub, não precisa do token
    return RedirectResponse(
        url=f"/equipe/{team_id}",
        status_code=303,
    )

@app.post("/jurado/nota/{team_id}")
async def registrar_nota(team_id: int, request: Request, nota: str = Form(...)):
    jurado = get_jurado_logado(request)
    if not jurado:
        return RedirectResponse(url="/jurado/login")

    try:
        nota_valor = float(nota)
    except (ValueError, TypeError):
        return RedirectResponse(url="/jurado/dashboard", status_code=303)

    if not (0 <= nota_valor <= 10):
        return RedirectResponse(url="/jurado/dashboard", status_code=303)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO avaliacoes (judge_id, team_id, nota)
        VALUES (?, ?, ?)
        ON CONFLICT(judge_id, team_id) DO UPDATE SET nota = excluded.nota
        """,
        (jurado["id"], team_id, nota_valor),
    )
    conn.commit()
    conn.close()

    return RedirectResponse(url="/jurado/dashboard", status_code=303)

@app.get("/resultados", response_class=HTMLResponse)
async def resultados(request: Request):
    if not RESULTS_RELEASED:
        return templates.TemplateResponse(
            request, "resultados_indisponivel.html", {},
        )

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT teams.team_name,
               AVG(avaliacoes.nota) AS media,
               COUNT(avaliacoes.nota) AS total_avaliacoes
        FROM teams
        JOIN avaliacoes ON avaliacoes.team_id = teams.id
        WHERE teams.leader_email_verified = 1
        GROUP BY teams.id
        ORDER BY media DESC
        """
    )
    ranking = cur.fetchall()
    conn.close()

    return templates.TemplateResponse(
        request, "resultados.html",
        {"ranking": ranking},
    )

def formatar_periodo(inicio_str: str, fim_str: str) -> str:
    inicio = datetime.fromisoformat(inicio_str)
    fim = datetime.fromisoformat(fim_str)
    return f"{inicio.strftime('%d/%m')} - {fim.strftime('%d/%m')}"


CRONOGRAMA = {
    "inscricoes": formatar_periodo(os.getenv("INSCRICOES_INICIO"), os.getenv("INSCRICOES_FIM")),
    "validacao": formatar_periodo(os.getenv("VALIDACAO_INICIO"), os.getenv("VALIDACAO_FIM")),
    "upload": formatar_periodo(os.getenv("UPLOAD_INICIO"), os.getenv("UPLOAD_FIM")),
    "avaliacao": formatar_periodo(os.getenv("AVALIACAO_INICIO"), os.getenv("AVALIACAO_FIM")),
    "resultados": datetime.fromisoformat(os.getenv("RESULTADOS_DATA")).strftime("%d/%m"),
}

CRONOGRAMA_MARCOS = [
    os.getenv("INSCRICOES_INICIO"),
    os.getenv("VALIDACAO_INICIO"),
    os.getenv("UPLOAD_INICIO"),
    os.getenv("AVALIACAO_INICIO"),
    os.getenv("RESULTADOS_DATA"),
]
