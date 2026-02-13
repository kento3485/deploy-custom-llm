"""
Elasticsearch ベクトルデータベース初期化スクリプト。
markdown/ ディレクトリ内の Markdown ファイルを読み込み、
チャンク分け → ベクトル化 → Elasticsearch に投入する。

環境変数:
  OPENAI_API_KEY        - OpenAI API キー
  ELASTICSEARCH_URL     - ES 接続先 (default: http://elasticsearch:9200)
  ELASTIC_USER          - ES ユーザー名 (空なら認証なし)
  ELASTIC_PASSWORD      - ES パスワード (空なら認証なし)
  MD_DIRECTORY_PATH     - Markdown ディレクトリ (default: ./markdown)
"""

import os

from elasticsearch import Elasticsearch
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import TokenTextSplitter
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_elasticsearch import ElasticsearchStore

# --- 設定 ---

ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://elasticsearch:9200")
ES_USER = os.environ.get("ELASTIC_USER", "")
ES_PASSWORD = os.environ.get("ELASTIC_PASSWORD", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MD_DIRECTORY_PATH = os.environ.get("MD_DIRECTORY_PATH", "./markdown/GeriatricMedicineAndGerontology")

INDEX_NAME = "geriatric_medicine_and_gerontology"

# --- ES クライアント ---

if ES_USER and ES_PASSWORD:
    es_client = Elasticsearch([ES_URL], basic_auth=(ES_USER, ES_PASSWORD), verify_certs=False)
else:
    es_client = Elasticsearch([ES_URL])

# --- 冪等チェック ---

if es_client.indices.exists(index=INDEX_NAME):
    doc_count = es_client.count(index=INDEX_NAME)["count"]
    if doc_count > 0:
        print(f"Index '{INDEX_NAME}' already has {doc_count} documents. Skipping.")
        exit(0)

# --- Markdown 読み込み＋チャンク分け ---

md_file_name_list = os.listdir(MD_DIRECTORY_PATH)
print(f"Found {len(md_file_name_list)} entries in {MD_DIRECTORY_PATH}")

chunks_of = {}
for md_file_name in md_file_name_list:
    md_file_path = os.path.join(MD_DIRECTORY_PATH, md_file_name, md_file_name + ".md")

    if not os.path.isfile(md_file_path):
        print(f"  Skipping {md_file_name} (no .md file found)")
        continue

    print(f"  Processing: {md_file_path}")

    loader = UnstructuredMarkdownLoader(md_file_path)
    markdown_document = loader.load()

    text_splitter = TokenTextSplitter(chunk_size=500, chunk_overlap=40)
    chunks = text_splitter.split_documents(markdown_document)

    chunks_of[md_file_name] = chunks

all_chunks = [chunk for chunks in chunks_of.values() for chunk in chunks]
print(f"Total chunks: {len(all_chunks)}")

if not all_chunks:
    print("No chunks to index. Exiting.")
    exit(0)

# --- ベクトル化 ＋ ES 投入 ---

embeddings = OpenAIEmbeddings(chunk_size=300, model="text-embedding-ada-002")

print(f"Indexing {len(all_chunks)} chunks into '{INDEX_NAME}' ...")
db = ElasticsearchStore.from_documents(
    all_chunks,
    embeddings,
    es_connection=es_client,
    index_name=INDEX_NAME,
)

# --- 確認 ---

doc_count = es_client.count(index=INDEX_NAME)["count"]
print(f"Done. Index '{INDEX_NAME}' now has {doc_count} documents.")
