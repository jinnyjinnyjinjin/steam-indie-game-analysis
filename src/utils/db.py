import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).parents[2] / ".env")


def get_connection():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.cursor().execute("SET search_path TO public")
    return conn


def get_engine():
    engine = create_engine(
        os.environ["DATABASE_URL"],
        isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as c:
        c.execute(text("SET search_path TO public"))
    return engine
