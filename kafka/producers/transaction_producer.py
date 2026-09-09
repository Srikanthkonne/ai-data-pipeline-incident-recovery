import json

from confluent_kafka import Producer


KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TRANSACTION_TOPIC = "transactions"


producer = Producer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "ecommerce-transaction-producer",
    }
)


def delivery_report(error, message):
    if error is not None:
        print(f"Kafka delivery failed: {error}")
        return

    print(
        f"Kafka event delivered: "
        f"topic={message.topic()} "
        f"partition={message.partition()} "
        f"offset={message.offset()}"
    )


def publish_transaction(transaction):
    producer.produce(
        topic=TRANSACTION_TOPIC,
        key=transaction["customer_id"],
        value=json.dumps(
            transaction,
            default=str,
        ),
        callback=delivery_report,
    )

    producer.poll(0)


def flush_producer():
    producer.flush()