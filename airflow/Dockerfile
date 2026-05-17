FROM apache/airflow:2.9.3-python3.12

USER root

# Install system deps for pymongo / pyarrow
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
