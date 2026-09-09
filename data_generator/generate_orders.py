import random
import uuid
from datetime import datetime, timezone

import psycopg2

from data_generator.config import DB_CONFIG


ORDER_STATUSES = [
    "PENDING",
    "CONFIRMED",
    "SHIPPED",
    "COMPLETED",
    "CANCELLED",
]


def get_random_customer(cursor):
    cursor.execute(
        """
        SELECT customer_id
        FROM customers
        ORDER BY RANDOM()
        LIMIT 1
        """
    )

    result = cursor.fetchone()

    if result is None:
        raise RuntimeError("No customers exist in the database.")

    return result[0]


def generate_order(customer_id):
    return {
        "order_id": f"order_{uuid.uuid4().hex[:8]}",
        "customer_id": customer_id,
        "order_status": random.choice(ORDER_STATUSES),
        "total_amount": round(random.uniform(10, 500), 2),
        "currency": "USD",
        "order_timestamp": datetime.now(timezone.utc),
    }


def insert_order(customer_id=None):
    connection = psycopg2.connect(**DB_CONFIG)

    try:
        with connection.cursor() as cursor:
            if customer_id is None:
                customer_id = get_random_customer(cursor)

            order = generate_order(customer_id)

            cursor.execute(
                """
                INSERT INTO orders (
                    order_id,
                    customer_id,
                    order_status,
                    total_amount,
                    currency,
                    order_timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    order["order_id"],
                    order["customer_id"],
                    order["order_status"],
                    order["total_amount"],
                    order["currency"],
                    order["order_timestamp"],
                ),
            )

        connection.commit()
        return order

    finally:
        connection.close()


if __name__ == "__main__":
    order = insert_order()

    print("Created order:")
    print(order)