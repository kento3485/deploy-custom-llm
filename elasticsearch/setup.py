"""
Elasticsearch index setup for RAG vector search.
This script is idempotent -- safe to run multiple times.
"""

from elasticsearch import Elasticsearch

ES_HOST = "http://localhost:9200"
INDEX_NAME = "geriatric_medicine_and_gerontology"

# OpenAI text-embedding-ada-002 produces 1536-dimensional vectors
EMBEDDING_DIMS = 1536

INDEX_SETTINGS = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "text": {
                "type": "text",
                "analyzer": "standard",
            },
            "vector": {
                "type": "dense_vector",
                "dims": EMBEDDING_DIMS,
                "index": True,
                "similarity": "cosine",
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "source": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "title": {"type": "text"},
                },
            },
        }
    },
}


def main():
    es = Elasticsearch(ES_HOST)

    info = es.info()
    print(f"Connected to Elasticsearch {info['version']['number']}")

    if es.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' already exists. Skipping creation.")
    else:
        es.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
        print(f"Index '{INDEX_NAME}' created successfully.")

    # TODO: ここにドキュメントチャンクのバルクインデックス処理を追加
    # Example:
    # from elasticsearch.helpers import bulk
    # documents = [
    #     {
    #         "text": "チャンクのテキスト...",
    #         "vector": [0.1, 0.2, ...],  # 1536次元のベクトル
    #         "metadata": {"source": "file.pdf", "chunk_index": 0, "title": "文書タイトル"},
    #     },
    # ]
    # actions = [{"_index": INDEX_NAME, "_source": doc} for doc in documents]
    # bulk(es, actions)

    print("Setup complete.")


if __name__ == "__main__":
    main()
