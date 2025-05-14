# ベースイメージとして公式のPythonイメージを使用
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ローカルのrequirements.txtをコンテナにコピー
COPY requirements.txt .

# Pythonの依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコンテナにコピー
COPY . .

# 環境変数の設定（Flaskアプリを起動するため）
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# コンテナのポート5000を公開
EXPOSE 5000

# Flaskアプリケーションを起動
CMD ["python", "app.py"]
# CMD ["flask", "run"]
