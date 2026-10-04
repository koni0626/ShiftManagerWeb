"""Dedicated development PostgreSQL cluster. Does not touch the installed service."""

import json
import os
import secrets
import subprocess
from pathlib import Path
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
BIN = Path(os.environ.get("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))
PORT = 55434
LOCAL.mkdir(exist_ok=True)
config_file = LOCAL / "database.json"
if not config_file.exists():
    config_file.write_text(
        json.dumps({"admin": secrets.token_hex(24), "app": secrets.token_hex(24)})
    )
config = json.loads(config_file.read_text())


def run(*args, check=True):
    with (LOCAL / "postgres-setup.log").open("a", encoding="utf-8") as log:
        return subprocess.run(
            list(map(str, args)),
            check=check,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
        )


data = LOCAL / "pgdata"
if not (data / "PG_VERSION").exists():
    password_file = LOCAL / "init-password"
    password_file.write_text(config["admin"], encoding="ascii")
    try:
        result = run(
            BIN / "initdb.exe",
            "-D",
            data,
            "-U",
            "atelier_admin",
            "-A",
            "scram-sha-256",
            f"--pwfile={password_file}",
            "--encoding=UTF8",
            "--locale=C",
        )
    finally:
        password_file.unlink(missing_ok=True)
if run(BIN / "pg_ctl.exe", "-D", data, "status", check=False).returncode:
    run(
        BIN / "pg_ctl.exe",
        "-D",
        data,
        "-l",
        LOCAL / "postgres.log",
        "-o",
        f"-p {PORT} -h 127.0.0.1",
        "-w",
        "start",
    )
with psycopg.connect(
    host="127.0.0.1",
    port=PORT,
    user="atelier_admin",
    password=config["admin"],
    dbname="postgres",
    autocommit=True,
) as db:
    if not db.execute("SELECT 1 FROM pg_roles WHERE rolname='atelier_app'").fetchone():
        db.execute(
            sql.SQL(
                "CREATE ROLE atelier_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE"
            ).format(sql.Literal(config["app"]))
        )
    for name in ("atelier", "atelier_test"):
        if not db.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
        ).fetchone():
            db.execute(
                sql.SQL("CREATE DATABASE {} OWNER atelier_admin").format(
                    sql.Identifier(name)
                )
            )
env_file = ROOT / ".env"
if not env_file.exists():
    env_file.write_text(
        f"DATABASE_URL=postgresql+psycopg://atelier_app:{config['app']}@127.0.0.1:{PORT}/atelier\nMIGRATION_DATABASE_URL=postgresql+psycopg://atelier_admin:{config['admin']}@127.0.0.1:{PORT}/atelier\nCOOKIE_SECURE=false\n",
        encoding="utf-8",
    )
print(
    f"Dedicated PostgreSQL is ready at 127.0.0.1:{PORT}. Credentials are stored locally."
)
