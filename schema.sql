CREATE TABLE teams (
    id INTEGER PRIMARY KEY,
    team_name TEXT,
    leader_name TEXT,
    leader_email TEXT,
    leader_email_verified BOOLEAN DEFAULT 0,
    verify_token TEXT,
    repo_full_name TEXT,
    github_username TEXT
);

CREATE TABLE team_members (
    id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(id),
    member_name TEXT
);
