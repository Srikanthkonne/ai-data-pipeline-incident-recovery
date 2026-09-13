with successful_transactions as (

    select
        customer_id,
        amount,
        event_time

    from {{ ref('stg_transactions') }}

    where status = 'SUCCESS'

),

customer_spend as (

    select
        customer_id,
        cast(event_time as date) as transaction_date,
        count(*) as successful_transaction_count,
        round(sum(amount), 2) as total_spend,
        round(avg(amount), 2) as average_transaction_amount

    from successful_transactions

    group by
        customer_id,
        cast(event_time as date)

)

select *
from customer_spend
