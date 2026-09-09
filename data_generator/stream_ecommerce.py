import random
import time
import uuid
from datetime import datetime, timezone

from data_generator.generate_customers import (
    generate_customer,
    insert_customer,
)
from data_generator.generate_orders import insert_order
from data_generator.generate_payments import insert_payment

from kafka.producers.transaction_producer import (
    flush_producer,
    publish_transaction,
)


def create_transaction_event(payment):
    return {
        "transaction_id": f"txn_{uuid.uuid4().hex[:8]}",
        "customer_id": payment["customer_id"],
        "order_id": payment["order_id"],
        "payment_id": payment["payment_id"],
        "amount": float(payment["amount"]),
        "payment_method": payment["payment_method"],
        "status": payment["payment_status"],
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


def run_stream():
    print("Starting e-commerce event generator...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:

            # Occasionally create a new customer.
            if random.random() < 0.25:
                customer = generate_customer()
                customer = insert_customer(customer)

                print(
                    f"Created customer: "
                    f"{customer['customer_id']}"
                )

                # Create the order for this exact new customer.
                order = insert_order(
                    customer["customer_id"]
                )

            else:
                # Otherwise use an existing customer.
                order = insert_order()

            print(
                f"Created order: "
                f"{order['order_id']} "
                f"customer={order['customer_id']}"
            )

            # Create payment for this exact order.
            payment = insert_payment(order)

            print(
                f"Created payment: "
                f"{payment['payment_id']} "
                f"order={payment['order_id']}"
            )

            transaction = create_transaction_event(
                payment
            )

            publish_transaction(
                transaction
            )

            print(
                f"Published transaction: "
                f"{transaction['transaction_id']}"
            )

            print("-" * 60)

            time.sleep(
                random.uniform(1, 3)
            )

    except KeyboardInterrupt:
        print("\nStopping generator...")

    finally:
        flush_producer()
        print("Kafka producer flushed.")


if __name__ == "__main__":
    run_stream()