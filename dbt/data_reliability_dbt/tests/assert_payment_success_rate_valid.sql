select
    payment_method,
    success_rate
from {{ ref('payment_success_rate') }}
where success_rate < 0
   or success_rate > 100
