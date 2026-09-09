import uuid

import psycopg2
from faker import Faker

from data_generator.config import DB_CONFIG


fake = Faker()


def generate_customer():
    customer_id = f"cust_{uuid.uuid4().hex[:8]}"

    return {
        "customer_id": customer_id,
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.unique.email(),
        "country": fake.country(),
    }


def insert_customer(customer):
    connection = psycopg2.connect(**DB_CONFIG)

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO customers (
                    customer_id,
                    first_name,
                    last_name,
                    email,
                    country
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    customer["customer_id"],
                    customer["first_name"],
                    customer["last_name"],
                    customer["email"],
                    customer["country"],
                ),
            )

        connection.commit()

        return customer

    finally:
        connection.close()


if __name__ == "__main__":
    customer = generate_customer()
    customer = insert_customer(customer)

    print("Created customer:")
    print(customer)