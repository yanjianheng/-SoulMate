from app.db.sqlite_store import init_db


if __name__ == "__main__":
    db_path = init_db()
    print(f"Database initialized: {db_path}")
