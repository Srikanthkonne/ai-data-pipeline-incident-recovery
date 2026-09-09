import random
import uuid
from datetime import datetime, timezone

import psycopg2

from data_generator.config import DB_CONFIG


PAYMENT_METHODS = [
    "CREDIT_CARD",
    "DEBIT_CARD",
    "PAYPAL",
    "APPLE_PAY",
]

PAYMENT_STATUSES = [
    "SUCCESS",
    "FAILED",
    "PENDING",
]


def get_random_order(cursor):
    cursor.execute(
        """
        SELECT
            order_id,
            customer_id,
            total_amount
        FROM orders
        ORDER BY RANDOM()
        LIMIT 1
        """
    )

    result = cursor.fetchone()

    if result is None:
        raise RuntimeError("No orders exist in the database.")

    return result


def generate_payment(order_id, customer_id, total_amount):
    return {
        "payment_id": f"pay_{uuid.uuid4().hex[:8]}",
        "order_id": order_id,
        "customer_id": customer_id,
        "payment_method": random.choice(PAYMENT_METHODS),
        "payment_status": random.choice(PAYMENT_STATUSES),
        "amount": total_amount,
        "payment_timestamp": datetime.now(timezone.utc),
    }


def insert_payment(order=None):
    connection = psycopg2.connect(**DB_CONFIG)

    try:
        with connection.cursor() as cursor:
            if order is None:
                order_id, customer_id, total_amount = get_random_order(cursor)
            else:
                order_id = order["order_id"]
                customer_id = order["customer_id"]
                total_amount = order["total_amount"]

            payment = generate_payment(
                order_id,
                customer_id,
                total_amount,
            )

            cursor.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    order_id,
                    customer_id,
                    payment_method,
                    payment_status,
                    amount,
                    payment_timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payment["payment_id"],
                    payment["order_id"],
                    payment["customer_id"],
                    payment["payment_method"],
                    payment["payment_status"],
                    payment["amount"],
                    payment["payment_timestamp"],
                ),
            )

        connection.commit()
        return payment

    finally:
        connection.close()


if __name__ == "__main__":
    payment = insert_payment()

    print("Created payment:")
    print(payment)