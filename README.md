# PowerPoint スライド自動生成エージェント

Microsoft Learn や指定された URL の情報を参照して、PowerPoint スライドを自動生成する Web アプリケーションです。

## 概要

このシステムは以下の機能を提供します：

- **自動スライド生成**: Microsoft Learn やカスタム URL を参照したスライド自動作成
- **カスタムデザイン**: ユーザーアップロードのスライドをマスターテンプレートとして利用
- **エージェントベースアーキテクチャ**: 複数の専用エージェントによる協調処理
- **Web インターフェース**: React TypeScript による直感的な操作画面
- **ユーザー認証**: Microsoft Entra ID による安全なアクセス管理
- **クラウド統合**: Azure Cosmos DB、Blob Storage との連携

## アーキテクチャ

### エージェント構成
- **オーケストレーションエージェント**: 全体の処理フローを制御
- **アジェンダ生成エージェント**: スライド構成の提案
- **情報収集エージェント**: Microsoft Learn 等からの情報取得 (Azure AI Foundry Agent Service)
- **スライド作成エージェント**: PowerPoint ファイルの生成 (python-pptx)
- **レビューエージェント**: 生成内容の品質チェック

### 技術スタック
- **バックエンド**: Python, A2A Python SDK, Semantic Kernel
- **フロントエンド**: TypeScript, React
- **認証**: Microsoft Entra ID
- **データベース**: Azure Cosmos DB
- **ストレージ**: Azure Blob Storage
- **AI サービス**: Azure AI Foundry Agent Service
- **監視**: OpenTelemetry
- **デプロイ**: Kubernetes

## ディレクトリ構成

```
.
├── backend/                     # Python バックエンドサービス
│   ├── agents/                  # エージェント実装
│   │   ├── agenda_agent/        # アジェンダ生成エージェント
│   │   ├── information_agent/   # 情報収集エージェント
│   │   ├── slide_agent/         # スライド作成エージェント
│   │   ├── review_agent/        # レビューエージェント
│   │   └── orchestration_agent/ # オーケストレーションエージェント
│   └── shared/                  # 共通ライブラリ
│       ├── models/              # データモデル
│       ├── storage/             # ストレージクライアント
│       └── auth/                # 認証ヘルパー
├── frontend/                    # React TypeScript フロントエンド
│   ├── src/                     # ソースコード
│   └── public/                  # 静的ファイル
├── docker/                      # Docker 設定
└── docs/                        # ドキュメント
```

## 主要機能

### 1. スライド生成フロー
1. ユーザーがプロンプト、参照 URL、デザインテンプレートを設定
2. アジェンダ生成エージェントがスライド構成を提案
3. ユーザー承認後、情報収集エージェントが詳細情報を収集
4. スライド作成エージェントが PowerPoint ファイルを生成
5. レビューエージェントが品質チェックとハルシネーション検証
6. Azure Blob Storage にアップロード後、ダウンロード URL を提供

### 2. ユーザー設定管理
- プロンプトテンプレートの管理
- LLM モデルの選択設定
- スライドマスターのアップロードと管理
- 参照 URL の登録

### 3. 認証とセキュリティ
- Microsoft Entra ID による SSO
- トークンベースの API 認証
- ユーザー別設定の分離

## セットアップ

### 前提条件
- Python 3.9+
- Node.js 18+
    - 以下の条件でテスト済み
    - Node.js v20.19.4
    - npm  v10.8.2
- Azure サブスクリプション
- Kubernetes クラスター (デプロイ用)

### 環境変数
```bash
# Azure 設定
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret

# ストレージ設定
COSMOS_DB_ENDPOINT=your_cosmos_endpoint
COSMOS_DB_KEY=your_cosmos_key
BLOB_STORAGE_CONNECTION_STRING=your_blob_connection

# AI サービス
AZURE_AI_FOUNDRY_ENDPOINT=your_ai_foundry_endpoint
AZURE_AI_FOUNDRY_KEY=your_ai_foundry_key
```

### ローカル開発

#### バックエンド
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn orchestration_agent.main:app --reload
```

#### フロントエンド
```bash
cd frontend
npm install
npm start
```
