FROM apache/spark:3.5.1-python3

USER root

ENV SPARK_VERSION=3.5

RUN python3 -m pip install \
    --no-cache-dir \
    pydeequ==1.5.0

USER spark