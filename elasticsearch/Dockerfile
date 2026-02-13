FROM docker.elastic.co/elasticsearch/elasticsearch:8.17.4

# Python3をインストール（setup.py実行用）
USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/setup/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/setup/requirements.txt

COPY setup.py /opt/setup/setup.py
COPY entrypoint.sh /opt/setup/entrypoint.sh
RUN chmod +x /opt/setup/entrypoint.sh

# elasticsearchユーザーに戻す
USER elasticsearch

# 単一ノード構成、セキュリティ無効（Private Service内部通信のみ）
ENV discovery.type=single-node
ENV xpack.security.enabled=false
ENV xpack.security.http.ssl.enabled=false
ENV xpack.security.transport.ssl.enabled=false
ENV ES_JAVA_OPTS="-Xms512m -Xmx512m"

EXPOSE 9200

ENTRYPOINT ["/opt/setup/entrypoint.sh"]
