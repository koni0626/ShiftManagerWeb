import getpass
from sqlalchemy import select
from app import models as m
from app.db import SessionLocal
from app.services.auth_service import hasher


def main():
    login = input("Login ID: ").strip().casefold()
    name = input("Display name: ").strip()
    password = getpass.getpass("Password (12+ characters): ")
    if not login or not name or len(password) < 12:
        raise SystemExit("Invalid input")
    with SessionLocal() as db:
        if db.scalar(select(m.User).where(m.User.login_id == login)):
            raise SystemExit("Login ID already exists")
        db.add(
            m.User(
                login_id=login,
                name=name,
                role="system_admin",
                password_hash=hasher.hash(password),
            )
        )
        db.commit()
    print("Administrator created")


if __name__ == "__main__":
    main()
