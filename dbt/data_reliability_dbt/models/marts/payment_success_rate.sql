with payment_summary as (

    select
        payment_method,
        count(*) as total_transactions,
        sum(case when status = 'SUCCESS' then 1 else 0 end) as successful_transactions,
        sum(case when status = 'FAILED' then 1 else 0 end) as failed_transactions,
        sum(case when status = 'PENDING' then 1 else 0 end) as pending_transactions

    from {{ ref('stg_transactions') }}

    group by payment_method

)

select
    payment_method,
    total_transactions,
    successful_transactions,
    failed_transactions,
    pending_transactions,
    round(
        successful_transactions * 100.0 / nullif(total_transactions, 0),
        2
    ) as success_rate
from payment_summary
