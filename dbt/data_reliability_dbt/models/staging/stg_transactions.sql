with silver_transactions as (

    select
        transaction_id,
        customer_id,
        order_id,
        payment_id,
        amount,
        payment_method,
        status,
        event_time,
        kafka_key,
        kafka_topic,
        kafka_partition,
        kafka_offset,
        kafka_timestamp,
        ingestion_timestamp,
        silver_processed_at

    from read_parquet(
        's3://data-platform/silver/transactions/*.parquet'
    )

)

select *
from silver_transactions
