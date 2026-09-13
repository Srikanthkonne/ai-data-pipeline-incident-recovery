#!/usr/bin/env bash

set -euo pipefail

SPARK_CONTAINER="${SPARK_CONTAINER:-incident-platform-spark}"

HADOOP_AWS_VERSION="3.3.4"
AWS_SDK_BUNDLE_VERSION="1.12.262"
OPENLINEAGE_VERSION="1.53.0"

OPENLINEAGE_NAMESPACE="${OPENLINEAGE_NAMESPACE:-incident-platform}"
OPENLINEAGE_URL="${OPENLINEAGE_URL:-http://marquez-api:5000}"

docker exec "${SPARK_CONTAINER}" \
  /opt/spark/bin/spark-submit \
  --master "local[*]" \
  --packages "org.apache.hadoop:hadoop-aws:${HADOOP_AWS_VERSION},com.amazonaws:aws-java-sdk-bundle:${AWS_SDK_BUNDLE_VERSION},io.openlineage:openlineage-spark_2.12:${OPENLINEAGE_VERSION}" \
  --conf spark.driver.extraJavaOptions="-Divy.cache.dir=/tmp/.ivy2" \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --conf spark.extraListeners=io.openlineage.spark.agent.OpenLineageSparkListener \
  --conf spark.openlineage.transport.type=http \
  --conf spark.openlineage.transport.url="${OPENLINEAGE_URL}" \
  --conf spark.openlineage.namespace="${OPENLINEAGE_NAMESPACE}" \
  /opt/spark/work-dir/jobs/silver_transactions.py
