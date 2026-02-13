FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY create_database.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# markdown/ ディレクトリはこのDockerコンテキストに配置してからビルドする
# 例: es-init/markdown/Chapter1/Chapter1.md
COPY markdown/ ./markdown/

CMD ["./entrypoint.sh"]
