FROM python:3.12-slim

# Install system deps
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user matching Jupyter conventions
RUN useradd -m -u 1000 -s /bin/bash jovyan

WORKDIR /home/jovyan

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory structure
RUN mkdir -p /home/jovyan/work/exports && chown -R jovyan:jovyan /home/jovyan

USER jovyan

EXPOSE 8888

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--notebook-dir=/home/jovyan/work", \
     "--ServerApp.token=${JUPYTER_TOKEN:-}", \
     "--ServerApp.password=''"]
