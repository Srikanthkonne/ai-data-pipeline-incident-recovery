MERGE (bronze:Dataset {
  namespace: 's3://data-platform',
  name: 'bronze/transactions'
});

MERGE (job:Job {
  namespace: 'incident-platform',
  name: 'silver_transactions.adaptive_spark_plan.silver_transactions'
});

MERGE (silver:Dataset {
  namespace: 's3://data-platform',
  name: 'silver/transactions'
});

MATCH (bronze:Dataset {
  namespace: 's3://data-platform',
  name: 'bronze/transactions'
})
MATCH (job:Job {
  namespace: 'incident-platform',
  name: 'silver_transactions.adaptive_spark_plan.silver_transactions'
})
MERGE (bronze)-[:INPUT_TO]->(job);

MATCH (job:Job {
  namespace: 'incident-platform',
  name: 'silver_transactions.adaptive_spark_plan.silver_transactions'
})
MATCH (silver:Dataset {
  namespace: 's3://data-platform',
  name: 'silver/transactions'
})
MERGE (job)-[:OUTPUTS]->(silver);
