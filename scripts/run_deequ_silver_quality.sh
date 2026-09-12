#!/usr/bin/env bash

set -euo pipefail

SPARK_CONTAINER="${SPARK_CONTAINER:-incident-platform-spark}"

HADOOP_AWS_VERSION="3.3.4"
DEEQU_VERSION="3.0.3-spark-3.5"
POSTGRES_JDBC_VERSION="42.7.4"

docker exec "${SPARK_CONTAINER}" \
  /opt/spark/bin/spark-submit \
  --master "local[*]" \
  --packages "org.apache.hadoop:hadoop-aws:${HADOOP_AWS_VERSION},com.amazon.deequ:deequ:${DEEQU_VERSION},org.postgresql:postgresql:${POSTGRES_JDBC_VERSION}" \
  --exclude-packages net.sourceforge.f2j:arpack_combined_all \
  --conf spark.driver.extraJavaOptions="-Divy.cache.dir=/tmp/.ivy2" \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  /opt/spark/work-dir/jobs/deequ_silver_quality.py
