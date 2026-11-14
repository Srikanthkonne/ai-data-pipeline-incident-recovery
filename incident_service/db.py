import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()


def get_db_connection():
    """
    Create and return a PostgreSQL connection for the incident service.

    The connection settings are loaded from environment variables so the
    service can run locally now and move into Docker later without changing
    application code.
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
