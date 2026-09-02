CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    team_name TEXT UNIQUE,
    leader_name TEXT,
    leader_email TEXT UNIQUE,
    leader_email_verified BOOLEAN DEFAULT 0,
    verify_token TEXT,
    repo_full_name TEXT,
    github_username TEXT,
    access_token TEXT,
    veredito TEXT,
    analisado_em TEXT,
    nota_previa REAL
);

CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id),
    member_name TEXT,
    github_username TEXT,
    is_leader BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS team_sessions (
    id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id),
    session_token TEXT UNIQUE,
    created_at TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS judges (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE,
    name TEXT
);

CREATE TABLE IF NOT EXISTS judge_login_tokens (
    id INTEGER PRIMARY KEY,
    judge_id INTEGER REFERENCES judges(id),
    token TEXT UNIQUE,
    expires_at TEXT,
    used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS judge_sessions (
    id INTEGER PRIMARY KEY,
    judge_id INTEGER REFERENCES judges(id),
    session_token TEXT UNIQUE,
    created_at TEXT,
    expires_at TEXT
);

