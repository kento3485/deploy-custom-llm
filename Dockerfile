# ベースイメージとしてPythonを使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピーしインストール（レイヤーキャッシュ活用のため先に実行）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコンテナにコピー
COPY . .

# サーバー実行ポートを指定 (Renderでは環境変数$PORTが使われることが多いが、デフォルトは8000)
ENV PORT 8000

# コンテナ起動時に実行するコマンド（UvicornでFastAPIを起動）
# main.py の app オブジェクトを実行します
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
