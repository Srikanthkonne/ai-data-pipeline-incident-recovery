with successful_transactions as (

    select
        customer_id,
        amount,
        event_time

    from {{ ref('stg_transactions') }}

    where status = 'SUCCESS'

),

customer_ltv as (

    select
        customer_id,
        count(*) as successful_transaction_count,
        round(sum(amount), 2) as lifetime_revenue,
        round(avg(amount), 2) as average_transaction_amount,
        min(event_time) as first_successful_transaction_at,
        max(event_time) as last_successful_transaction_at

    from successful_transactions

    group by customer_id

)

select *
from customer_ltv
