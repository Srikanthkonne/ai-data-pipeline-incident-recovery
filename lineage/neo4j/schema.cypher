CREATE CONSTRAINT dataset_identity IF NOT EXISTS
FOR (d:Dataset)
REQUIRE (d.namespace, d.name) IS UNIQUE;

CREATE CONSTRAINT job_identity IF NOT EXISTS
FOR (j:Job)
REQUIRE (j.namespace, j.name) IS UNIQUE;
