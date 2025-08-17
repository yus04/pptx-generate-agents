# デプロイメントガイド

## ローカル開発環境のセットアップ

### 前提条件
- Python 3.11+
- Node.js 18+
- Azure サブスクリプション
- Docker & Docker Compose (オプション)

### 環境変数の設定

1. `.env.example` を `.env` にコピーして設定値を入力してください：

```bash
cp .env.example .env
```

2. 必要な環境変数：
   - Azure AD 認証情報
   - Cosmos DB 接続情報
   - Blob Storage 接続情報
   - Azure AI Foundry エンドポイント

### バックエンドのセットアップ

```bash
cd backend
pip install -r requirements.txt

# 環境変数を設定してから各エージェントを起動
python -m uvicorn agents.orchestration_agent.main:a2a_app --host 0.0.0.0 --port 8000 &
python -m uvicorn agents.agenda_agent.main:a2a_app --host 0.0.0.0 --port 8001 &
python -m uvicorn agents.information_agent.main:a2a_app --host 0.0.0.0 --port 8002 &
python -m uvicorn agents.slide_agent.main:a2a_app --host 0.0.0.0 --port 8003 &
python -m uvicorn agents.review_agent.main:a2a_app --host 0.0.0.0 --port 8004 &
```

### フロントエンドのセットアップ

```bash
cd frontend
npm install
npm start
```

## Docker Compose を使用したデプロイ

```bash
# 環境変数を設定
cp .env.example .env
# .env を編集

# すべてのサービスを起動
docker-compose up -d

# ログを確認
docker-compose logs -f
```

## Kubernetes デプロイ

### 前提条件
- Kubernetes クラスター
- kubectl が設定済み
- Azure Container Registry または Docker Hub

### イメージのビルドとプッシュ

```bash
# 各エージェント用のイメージをビルド
docker build -f docker/Dockerfile.orchestration -t your-registry/pptx-orchestration:latest .
docker build -f docker/Dockerfile.frontend -t your-registry/pptx-frontend:latest .
# 他のエージェントも同様に...

# レジストリにプッシュ
docker push your-registry/pptx-orchestration:latest
docker push your-registry/pptx-frontend:latest
```

### Kubernetes マニフェストの例

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pptx-orchestration
spec:
  replicas: 2
  selector:
    matchLabels:
      app: pptx-orchestration
  template:
    metadata:
      labels:
        app: pptx-orchestration
    spec:
      containers:
      - name: orchestration
        image: your-registry/pptx-orchestration:latest
        ports:
        - containerPort: 8000
        env:
        - name: AZURE_TENANT_ID
          valueFrom:
            secretKeyRef:
              name: azure-secrets
              key: tenant-id
        # 他の環境変数...
---
apiVersion: v1
kind: Service
metadata:
  name: pptx-orchestration-service
spec:
  selector:
    app: pptx-orchestration
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## モニタリングの設定

### OpenTelemetry

Jaeger または Azure Application Insights を使用してトレーシングを設定：

```bash
# Jaeger の場合
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 14268:14268 \
  jaegertracing/all-in-one:latest
```

### ログ集約

Azure Log Analytics または ELK Stack を推奨。

## トラブルシューティング

### よくある問題

1. **認証エラー**
   - Azure AD の設定を確認
   - クライアント ID とテナント ID が正しいか確認

2. **データベース接続エラー**
   - Cosmos DB の接続文字列を確認
   - ファイアウォール設定を確認

3. **エージェント間通信エラー**
   - ネットワーク設定を確認
   - A2A トークンシークレットが一致しているか確認

### ログの確認

```bash
# Docker Compose の場合
docker-compose logs orchestration-agent

# Kubernetes の場合
kubectl logs deployment/pptx-orchestration
```

## セキュリティ考慮事項

1. **機密情報の管理**
   - Azure Key Vault の使用を推奨
   - 環境変数での機密情報の直接指定を避ける

2. **ネットワークセキュリティ**
   - API エンドポイントへの適切なアクセス制御
   - HTTPS の使用

3. **認証・認可**
   - Azure AD の適切な設定
   - API トークンの定期的な更新

## スケーリング

### 水平スケーリング
- Kubernetes HPA の設定
- 各エージェントの独立したスケーリング

### 垂直スケーリング
- リソース制限の適切な設定
- メモリ・CPU 使用量の監視