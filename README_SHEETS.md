# Google Sheets連携セットアップガイド

このガイドでは、Streamlit CloudでGoogle Sheetsにデータを保存する方法を詳しく説明します。

---

## 📋 必要なもの

1. Googleアカウント
2. GitHubアカウント
3. Streamlit Cloudアカウント（GitHubで登録）

所要時間: **約20-30分**

---

## ステップ1: Google Cloud Projectの作成

### 1-1. Google Cloud Consoleにアクセス

1. https://console.cloud.google.com/ にアクセス
2. Googleアカウントでログイン

### 1-2. 新しいプロジェクトを作成

1. 上部の「プロジェクトを選択」をクリック
2. 「新しいプロジェクト」をクリック
3. プロジェクト情報を入力:
   ```
   プロジェクト名: trade-analyzer
   組織: なし（個人使用の場合）
   ```
4. 「作成」をクリック
5. 作成されたプロジェクトを選択

---

## ステップ2: Google Sheets APIの有効化

### 2-1. APIを有効化

1. 左メニューから「APIとサービス」→「ライブラリ」を選択
2. 検索バーで「Google Sheets API」を検索
3. 「Google Sheets API」をクリック
4. 「有効にする」をクリック

### 2-2. 確認

- 「APIとサービス」→「有効なAPIとサービス」で確認
- 「Google Sheets API」が表示されていればOK

---

## ステップ3: サービスアカウントの作成

### 3-1. サービスアカウント作成

1. 左メニューから「APIとサービス」→「認証情報」を選択
2. 上部の「+ 認証情報を作成」をクリック
3. 「サービスアカウント」を選択
4. サービスアカウント情報を入力:
   ```
   サービスアカウント名: trade-analyzer-service
   サービスアカウントID: trade-analyzer-service（自動生成）
   説明: トレード分析アプリ用
   ```
5. 「作成して続行」をクリック
6. 「ロールを選択」は **スキップ**（「続行」をクリック）
7. 「完了」をクリック

### 3-2. JSONキーの作成

1. 作成したサービスアカウントをクリック
2. 「キー」タブを選択
3. 「鍵を追加」→「新しい鍵を作成」をクリック
4. **JSON** を選択
5. 「作成」をクリック

**重要**: JSONファイルが自動的にダウンロードされます。このファイルは大切に保管してください！

JSONファイルの中身（例）:
```json
{
  "type": "service_account",
  "project_id": "trade-analyzer-xxxxx",
  "private_key_id": "xxxxxxxxxxxxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBA...",
  "client_email": "trade-analyzer-service@trade-analyzer-xxxxx.iam.gserviceaccount.com",
  "client_id": "xxxxxxxxxxxxx",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
```

---

## ステップ4: Google Sheetsスプレッドシートの作成

### 4-1. 新しいスプレッドシートを作成

1. https://sheets.google.com にアクセス
2. 「空白」で新しいスプレッドシートを作成
3. タイトルを「トレード分析データ」に変更

### 4-2. サービスアカウントに共有

**重要**: この手順を忘れるとアプリがシートにアクセスできません！

1. 右上の「共有」ボタンをクリック
2. JSONファイルの `client_email` をコピー
   - 例: `trade-analyzer-service@trade-analyzer-xxxxx.iam.gserviceaccount.com`
3. 共有ユーザーに貼り付け
4. 権限を「編集者」に設定
5. 「送信」をクリック（メール通知はスキップ）

### 4-3. スプレッドシートIDを取得

ブラウザのURLから **スプレッドシートID** をコピー:

```
https://docs.google.com/spreadsheets/d/[ここがスプレッドシートID]/edit
                                      ^^^^^^^^^^^^^^^^^^^
```

例:
```
1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
```

このIDを保存しておいてください！

---

## ステップ5: GitHubへのアップロード

### 5-1. 必要なファイル

以下のファイルをGitHubリポジトリにアップロード:
- `trade_analyzer_sheets.py` （メインアプリ）
- `requirements_sheets.txt` （依存パッケージ）
- `README_SHEETS.md` （このファイル）

### 5-2. アップロード手順

1. GitHubで新しいリポジトリを作成（例: `trade-analyzer-cloud`）
2. 「Add file」→「Upload files」
3. 上記3ファイルをドラッグ&ドロップ
4. 「Commit changes」をクリック

---

## ステップ6: Streamlit Cloudでのデプロイ

### 6-1. アプリをデプロイ

1. https://streamlit.io/cloud にアクセス
2. GitHubでログイン
3. 「New app」をクリック
4. 設定を入力:
   ```
   Repository: あなたのユーザー名/trade-analyzer-cloud
   Branch: main
   Main file path: trade_analyzer_sheets.py
   App URL: trade-analyzer（任意）
   ```

**注意**: まだ「Deploy!」は押さないでください！

### 6-2. Secretsの設定（重要！）

1. 「Advanced settings」をクリック
2. 「Secrets」セクションを展開
3. 以下の内容を貼り付け:

```toml
# Google Cloud認証情報
[gcp_service_account]
type = "service_account"
project_id = "あなたのproject_id"
private_key_id = "あなたのprivate_key_id"
private_key = "-----BEGIN PRIVATE KEY-----\nあなたのprivate_key\n-----END PRIVATE KEY-----\n"
client_email = "あなたのclient_email"
client_id = "あなたのclient_id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "あなたのclient_x509_cert_url"

# スプレッドシートID
spreadsheet_id = "あなたのスプレッドシートID"
```

**記入例**:

```toml
[gcp_service_account]
type = "service_account"
project_id = "trade-analyzer-123456"
private_key_id = "abc123def456..."
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC...\n-----END PRIVATE KEY-----\n"
client_email = "trade-analyzer-service@trade-analyzer-123456.iam.gserviceaccount.com"
client_id = "123456789012345678901"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/api-client/..."

spreadsheet_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
```

### 6-3. JSONからのコピー方法

ダウンロードしたJSONファイルを開いて、各項目をコピー&ペーストします:

**注意点**:
- `private_key` は改行（\n）が含まれています。そのままコピーしてください
- 各項目は **ダブルクォート（"）で囲まない** でください（TOMLフォーマット）

### 6-4. デプロイ実行

1. Secretsの入力が完了したら「Save」
2. 「Deploy!」をクリック
3. 数分待つとアプリが起動します

---

## ステップ7: 動作確認

### 7-1. アプリにアクセス

デプロイが完了したら、発行されたURLにアクセス:
```
https://あなたのユーザー名-trade-analyzer-xxxxx.streamlit.app
```

### 7-2. 初回起動時

アプリが正常に起動すると、自動的にGoogle Sheetsに以下のシートが作成されます:
- `trades` （取引履歴）
- `active_trades` （アクティブポジション）
- `closed_trades` （決済済みトレード）
- `settings` （設定）
- `reason_definitions` （根拠定義）

### 7-3. スプレッドシートを確認

1. Google Sheetsで「トレード分析データ」を開く
2. 下部に5つのシートタブが作成されていることを確認
3. `settings` シートに初期設定が保存されていることを確認

---

## 📱 スマホでの使用

### ホーム画面に追加

**iPhone (Safari):**
1. アプリURLを開く
2. 下部の「共有」ボタン
3. 「ホーム画面に追加」
4. 名前を「トレード分析」に変更
5. 「追加」をタップ

**Android (Chrome):**
1. アプリURLを開く
2. 右上のメニュー（⋮）
3. 「ホーム画面に追加」
4. 「追加」をタップ

これで、アプリのようにワンタップで起動できます！

---

## 🔧 トラブルシューティング

### エラー1: "Google Sheets接続エラー"

**原因**: 認証情報が間違っている

**解決策**:
1. Streamlit Cloudのダッシュボードでアプリを選択
2. 「Settings」→「Secrets」を確認
3. JSONファイルと照合して修正
4. 「Save」→アプリを再起動

### エラー2: "Permission denied"

**原因**: サービスアカウントにスプレッドシートが共有されていない

**解決策**:
1. Google Sheetsでスプレッドシートを開く
2. 「共有」をクリック
3. サービスアカウントのメールアドレスを追加
4. 権限を「編集者」に設定

### エラー3: "Spreadsheet not found"

**原因**: スプレッドシートIDが間違っている

**解決策**:
1. スプレッドシートのURLからIDをコピー
2. Streamlit Cloudの Secrets で `spreadsheet_id` を修正
3. アプリを再起動

### エラー4: アプリが遅い

**原因**: Google Sheets APIの読み書きに時間がかかる

**解決策**:
- 無料プランでは多少遅くなります
- データ量が多い場合は、有料プランを検討
- または、ローカル実行（方法1）を使用

---

## 💾 データのバックアップ

### 自動バックアップ

Google Sheetsにデータが保存されるため、自動的にバックアップされます:
- Google Driveに保存される
- 編集履歴が保存される（復元可能）
- どのデバイスからもアクセス可能

### 手動エクスポート

必要に応じてExcel形式でダウンロード:
1. Google Sheetsでスプレッドシートを開く
2. 「ファイル」→「ダウンロード」→「Microsoft Excel (.xlsx)」

---

## 🔒 セキュリティ

### 認証情報の保護

- JSONキーは **絶対にGitHubにアップロードしない**
- Streamlit CloudのSecretsに保存する（暗号化される）
- JSONファイルは安全な場所に保管

### スプレッドシートの共有

- サービスアカウントのみに共有
- 他の人と共有する場合は、閲覧権限のみにする
- 編集権限は自分とサービスアカウントのみ

---

## 📊 データ構造

### trades シート
取引履歴データ

| 列名 | 説明 |
|------|------|
| trade_date | 約定日 |
| ticker_code | 銘柄コード |
| stock_name | 銘柄名 |
| trade_action | 売買区分 |
| quantity | 数量 |
| price | 単価 |
| total_amount | 金額 |

### active_trades シート
保有中のポジション

| 列名 | 説明 |
|------|------|
| ticker_code | 銘柄コード |
| entry_date | エントリー日 |
| entry_price | エントリー価格 |
| quantity | 数量 |
| entry_reason_category | エントリー根拠 |
| stop_loss_price | 損切り価格 |
| is_active | アクティブフラグ |

### closed_trades シート
決済済みトレード

| 列名 | 説明 |
|------|------|
| ticker_code | 銘柄コード |
| entry_date | エントリー日 |
| exit_date | 決済日 |
| profit_loss | 損益 |
| profit_loss_pct | 損益率 |
| entry_reason_category | エントリー根拠 |
| exit_reason_category | 決済根拠 |

### settings シート
アプリ設定

| 列名 | 説明 |
|------|------|
| total_capital | 総資産 |
| risk_per_trade_pct | リスク% |

### reason_definitions シート
根拠リストの定義

| 列名 | 説明 |
|------|------|
| reason_type | タイプ |
| category | カテゴリ |
| detail | 詳細 |
| is_active | 有効フラグ |

---

## 🎯 次のステップ

1. ✅ Google Cloud Projectを作成
2. ✅ サービスアカウントを作成してJSONキーをダウンロード
3. ✅ Google Sheetsを作成してサービスアカウントに共有
4. ✅ GitHubにファイルをアップロード
5. ✅ Streamlit CloudでSecretsを設定してデプロイ
6. ✅ スマホのホーム画面に追加
7. 🚀 トレード分析を開始！

---

## 💡 よくある質問

**Q: 無料で使えますか？**
A: はい、すべて無料です！
- Google Sheets: 無料
- Streamlit Cloud: 無料プラン（公開リポジトリ）
- GitHub: 無料

**Q: データは安全ですか？**
A: はい、Google Sheetsに保存されるため:
- Googleのセキュリティで保護
- 自動バックアップ
- 編集履歴から復元可能

**Q: 他の人もアクセスできますか？**
A: アプリのURLを知っている人はアクセスできますが、データは共有されます。個人使用を想定しています。

**Q: プライベートにできますか？**
A: Streamlit Cloudの有料プラン（$20/月）でプライベートリポジトリに対応できます。

**Q: データ量の制限はありますか？**
A: Google Sheetsは1シートあたり500万セルまで。通常の使用では十分です。

**Q: アプリが停止することはありますか？**
A: Streamlit Cloudは一定期間アクセスがないとスリープします。次回アクセス時に自動的に起動します（数秒かかります）。

---

## 📞 サポート

問題が解決しない場合:
1. このガイドをもう一度確認
2. エラーメッセージを確認
3. Streamlit Cloudのログを確認
4. Google Cloud Consoleで設定を確認

---

**設定完了後は、どこからでもスマホでトレード分析ができます！** 🎉
