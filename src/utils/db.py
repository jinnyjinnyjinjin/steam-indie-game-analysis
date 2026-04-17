import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")


def get_connection():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.cursor().execute("SET search_path TO public")
    return conn
