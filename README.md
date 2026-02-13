# deploy-custom-llm

Render.com 上にデプロイする RAG 対応 LLM WebSocket サーバー。
FastAPI (llm-api) と Elasticsearch 8.17.4 の 3 サービス構成。

## ディレクトリ構成

```
.
├── render.yaml                # Render Blueprint（3サービス定義）
├── .gitignore
├── llm-api/                   # FastAPI WebSocket サーバー
│   ├── Dockerfile
│   ├── main.py                # WebSocket エンドポイント
│   ├── generate_answer.py     # RAG ロジック（検索・クエリ書き換え・ストリーミング応答）
│   ├── settings.py            # 環境変数設定
│   └── requirements.txt
├── elasticsearch/             # Elasticsearch サービス
│   ├── Dockerfile             # ES 8.17.4 + Python3
│   ├── entrypoint.sh          # ES 起動 → ヘルスチェック → setup.py 実行
│   ├── setup.py               # インデックス初期化（dense_vector mapping）
│   └── requirements.txt
└── es-init/                   # DB初期化 Worker（初回のみ使用）
    ├── Dockerfile
    ├── entrypoint.sh          # ES ヘルスチェック → create_database.py 実行
    ├── create_database.py     # Markdown → チャンク → ベクトル化 → ES投入
    ├── requirements.txt
    └── markdown/              # ★ 初期化用データをここに配置
        └── GeriatricMedicineAndGerontology/
            ├── Chapter1/Chapter1.md
            ├── Chapter2/Chapter2.md
            └── ...
```

## アーキテクチャ

- **llm-api** (Web Service): FastAPI WebSocket サーバー。クライアントからのプロンプトを受け取り、Elasticsearch でベクトル検索 → OpenAI でストリーミング回答を返す。
- **elasticsearch** (Private Service): ベクトル DB。Render 内部ネットワークのみアクセス可能（`http://elasticsearch:9200`）。Persistent Disk でデータ永続化。
- **es-init** (Worker): DB初期化用の使い捨てサービス。Markdown データをベクトル化して ES に投入する。**初回デプロイ後にデータ投入が完了したら `render.yaml` から削除する。**

## 環境変数

### llm-api

| 変数名 | 説明 | 設定方法 |
|---|---|---|
| `MY_SECRET_KEY` | WebSocket 認証トークン | Render Dashboard で設定 |
| `OPENAI_API_KEY` | OpenAI API キー | Render Dashboard で設定 |
| `ELASTICSEARCH_URL` | ES 接続先 | `render.yaml` で自動設定済み |
| `ELASTIC_USER` | ES ユーザー名（任意） | 認証有効時のみ |
| `ELASTIC_PASSWORD` | ES パスワード（任意） | 認証有効時のみ |

### elasticsearch

| 変数名 | 説明 | デフォルト |
|---|---|---|
| `ES_JAVA_OPTS` | JVM ヒープサイズ | `-Xms512m -Xmx512m` |

### es-init

| 変数名 | 説明 | 設定方法 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API キー（ベクトル化に使用） | Render Dashboard で設定 |
| `ELASTICSEARCH_URL` | ES 接続先 | `render.yaml` で自動設定済み |

## Render へのデプロイ

### 初回デプロイ

1. `es-init/markdown/` に初期化用の Markdown データを配置
2. GitHub に push
3. Render Dashboard → **New** → **Blueprint** → リポジトリを選択
4. `render.yaml` が自動検出され、3 サービスが作成される
5. 各サービスの環境変数を設定:
   - `llm-api`: `MY_SECRET_KEY`, `OPENAI_API_KEY`
   - `es-init`: `OPENAI_API_KEY`
6. デプロイ実行
7. `es-init` Worker のログでデータ投入完了を確認

### データ投入後

1. `render.yaml` から `es-init` セクションを削除
2. GitHub に push（es-init サービスは Render Dashboard から手動で削除）

データは Elasticsearch の Persistent Disk に永続化されるため、es-init は不要になります。

**注意**: Elasticsearch Private Service には有料プラン（Starter 以上）と Persistent Disk が必要です。ES サービスには最低 2GB RAM のプランを推奨します。

## ローカル開発

```bash
# 1. Elasticsearch を起動
docker run -d --name es-local \
  -p 9200:9200 \
  -e discovery.type=single-node \
  -e xpack.security.enabled=false \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.4

# 2. インデックスを作成
cd elasticsearch
pip install -r requirements.txt
python setup.py

# 3. データを投入（初回のみ）
cd ../es-init
pip install -r requirements.txt
OPENAI_API_KEY=sk-... ELASTICSEARCH_URL=http://localhost:9200 python create_database.py

# 4. FastAPI を起動
cd ../llm-api
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

`llm-api/.env` を作成して環境変数を設定してください:

```
MY_SECRET_KEY=your-secret-key
OPENAI_API_KEY=sk-...
ELASTICSEARCH_URL=http://localhost:9200
```

## WebSocket 通信フロー

```
Client                          Server
  |-- connect /llm/ws ----------->|
  |<--------- accept -------------|
  |-- {"token": "secret"} ------->|  認証
  |<-- {"status":"authenticated"} |
  |-- {"prompt": "質問..."} ----->|  プロンプト送信
  |<-- {"token": "回"} -----------|  ストリーミング応答
  |<-- {"token": "答"} -----------|
  |<-- {"token": "..."} ----------|
  |<-- {"status": "done"} --------|  応答完了
```
