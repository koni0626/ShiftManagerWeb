# 訪問のアトリエ Web版

既存の訪問シフト管理アプリを、会社・営業所・ユーザー権限を持つWebアプリへ展開するプロジェクトです。

2026年10月4日に、ログインから訪問予定の調整・公開・本人確認まで動くWeb版 0.1.0を実装しました。設計全体の完成状況は[実装状況](docs/IMPLEMENTATION_STATUS.md)を参照してください。

## ローカルで起動

前提はWindows、Python 3.14、Node.js、PostgreSQL 18の実行ファイルです。このPCでは既存のPostgreSQLサービスとは別に、ポート55434で開発用クラスタを起動します。

```powershell
cd E:\app\ShiftForWeb
.\scripts\Start-Dev.ps1
```

初めての空DBに架空サンプルを作る場合は `-Demo` を付けます。既存データがある場合はサンプルを追加しません。起動スクリプトは依存関係、専用PostgreSQL、マイグレーション、API、React開発サーバー、位置取得ワーカーを順に準備します。マイグレーション失敗時は新しいAPIを起動しません。

- Web画面：[http://127.0.0.1:5194](http://127.0.0.1:5194)
- API仕様：[http://127.0.0.1:8014/docs](http://127.0.0.1:8014/docs)
- サンプルのログインID：`owner`、`member`、`admin`。ランダムに発行したパスワードは `.local/demo-accounts.json` を確認。
- `.env`、DBファイル、資格情報、プロセスのログはGit管理対象外。デスクトップ版のSQLiteには接続しません。

サンプルを使わず初期管理者を作る場合は、マイグレーション後に `backend` から `..\.venv\Scripts\python -m app.cli.bootstrap_admin` を実行します。会社とオーナーは管理者の画面から登録し、オーナーがスタッフのメンバーアカウントを発行します。

停止は `scripts/Stop-Dev.ps1`、専用DBも停止する場合は `-Database` を付けます。APIコードや `.env` を変更した後は停止してから再起動してください。フロントエンドの変更は開発サーバーが反映します。

## 開発とテスト

```powershell
cd E:\app\ShiftForWeb\backend
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m alembic upgrade head

cd E:\app\ShiftForWeb\frontend
npm run build
npm run test:e2e
```

APIテストは `scripts/init_local.py` で準備される専用 `atelier_test` DBを使用します。画面テストはMicrosoft Edgeと、サンプルデータ入りの起動中アプリが必要です。

Python依存は `backend/requirements.lock`、フロントエンド依存は `frontend/package-lock.json` で固定しています。Web版用のマイグレーションは `backend/migrations/versions` に追加します。日常のAPIリクエストからDB構造を変更しません。

背景地図と位置取得は `.env.example` にある設定を使います。位置取得用のキーはサーバーだけが読み、ブラウザーへ返しません。ローカルサンプル以外への移行時は、地図提供元・HTTPS・Cookie・許可Origin・DB権限・バックアップを本番環境に合わせて設定します。

## 設計資料

- [基本設計書](DESIGN.md)：機能、3種類の権限、複数営業所への所属、勤務希望、訪問予定、顧客地図。
- [UI設計書](docs/UI_DESIGN.md)：デスクトップ版「訪問のアトリエ」を継承する色・書体・画面構成・共通部品、スマートフォンへの調整。
- [技術設計書](docs/TECHNICAL_DESIGN.md)：Python 3.14・FastAPI・SQLAlchemy・PostgreSQL・React、層の分離、認証、同時編集、地図連携、マイグレーション。
- [データとAPI設計書](docs/DATA_API.md)：テーブル、参照整合性、API、実装順序、受入条件。

デスクトップ版の参照元は `E:\app\shift` です。Web版は `E:\app\ShiftForWeb` に独立して構築します。
