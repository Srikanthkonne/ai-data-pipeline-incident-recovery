with successful_transactions as (

    select
        transaction_id,
        amount,
        event_time

    from {{ ref('stg_transactions') }}

    where status = 'SUCCESS'

),

daily_revenue as (

    select
        cast(event_time as date) as transaction_date,
        count(*) as successful_transaction_count,
        round(sum(amount), 2) as total_revenue,
        round(avg(amount), 2) as average_transaction_amount

    from successful_transactions

    group by cast(event_time as date)

)

select *
from daily_revenue
