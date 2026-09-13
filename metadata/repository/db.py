import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()


def get_db_config():
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB", "ecommerce"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }


def get_connection():
    config = get_db_config()

    if not config["user"] or not config["password"]:
        raise RuntimeError(
            "POSTGRES_USER and POSTGRES_PASSWORD must be set."
        )

    return psycopg2.connect(**config)
