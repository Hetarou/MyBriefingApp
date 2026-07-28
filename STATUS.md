# STATUS

## 現在地

- 実装順「1. 画面の枠だけ作る」が完了。UIのアクセシビリティ・操作性の追加磨き込みも実施済み。
- ローカル保存（タスク完了状態・勉強トピック選択）を実装済み。
- 実装順「3. 夜間RSSバッチ」のニュース部分を実装・動作確認済み（下記参照）。カレンダー・タスクはまだダミーのまま。
- 実装順2番「あなた向けニュースのタグ選択」を実装・動作確認済み（下記参照）。
- 実装順5番（勉強タブの問題をGemini APIで生成）と実装順6番（PWA対応）を、
  Cloudflare Pages + Pages Functionsを土台にまとめて実装済み。**ただしCloudflare側の
  デプロイ・環境変数設定が未完了のため、実機での動作確認はまだできていない**（下記参照）。

## 重要な注記：`BRIEFING-APP.md` は存在せず、`ROUTINE-01-skeleton.md` を仕様書として扱っている

このリポジトリ、および作業環境の `Downloads` フォルダを探したが、`BRIEFING-APP.md`
（実装順・データ仕様・設計方針を定めた一次仕様書として本来参照されるはずのファイル）は
見つからなかった。作者の判断により、**`ROUTINE-01-skeleton.md` を `BRIEFING-APP.md` の
代わりの仕様書として扱うことが確定した。** 今後の実装もこの前提で進める。

`ROUTINE-01-skeleton.md` は実装順1番（画面の枠）のみを詳細に定義しており、
実装順2番はどの文書にも定義されていなかったため、作者が2026-07-28に定義した：
「あなた向けで出すニュースの種類を、勉強タブのトピック選択と同じようなタグ形式で選べるようにする」。
実装順3〜6番（夜間RSSバッチ／Googleカレンダー連携／Claude API呼び出し／PWA対応）は
`ROUTINE-01-skeleton.md` に名称のみ触れられている。

## この実装でやったこと（実装順1番の範囲）

- `index.html`：1ファイル完結（HTML+CSS+JS）。タブ「今日／ニュース／勉強」、既定は「今日」
  - 今日タブ：予定・タスク・気になるニュースをそれぞれダミー3件
  - ニュースタブ：サブタブ「あなた向け／一般」、カード各5件（見出し・要約・出典・元記事リンク・更新時刻）
  - 勉強タブ：トピック選択チップ、「問題を作る」ボタン、問題カード3件（タップで解答表示）
  - スマホ縦画面基準のレイアウト、余白広め、ダークテーマ＋グラデーションアクセント
- `data/briefing-sample.json`：ダミーデータ本体。`index.html` は fetch でこれを読み込む（配列の直書きなし）
- 外部ライブラリ・npm・ビルド工程は使用していない
- 追加の磨き込み：タブ/サブタブの ARIA（role=tab/tabpanel）とキーボード操作（矢印キー・Home/End によるローミングタブインデックス）、
  `prefers-reduced-motion` 対応、ノッチ端末向け safe-area-inset 余白、ローディング用シマー、チップのタップ領域拡大

## ニュースの実データ連携（実装順3番の一部）

- `.github/workflows/update-news.yml`：毎日 20:00 UTC（JST 5:00）に起動する GitHub Actions。
  手動実行（workflow_dispatch）も可能
- `scripts/fetch_news.py`：Python標準ライブラリのみで実装（pip install不要）。
  - 一般ニュース：NHKニュース（`https://www.nhk.or.jp/rss/news/cat0.xml`）
  - あなた向け：ITmedia NEWS（`https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml`、テック中心。
    本物の個人最適化ではなく、固定のテック系フィードで代替している点に注意）
  - 取得失敗時は該当セクションのみ前回データを維持し、空データで上書きしない
  - リンクは `http`/`https` のみ許可（安全でないスキームは除外）
- `data/news-live.json`：バッチが書き込む先。`index.html` はニュースタブと今日タブの
  「気になるニュース」（一般の上位3件）をここから読む。`data/briefing-sample.json` からは
  ニュース関連（`news`キー・`today.topNews`）を削除済み
- セキュリティ対策：見出し・要約・出典は既存の `escapeHtml()` で描画、リンクは
  クライアント側でも `safeUrl()` でスキーム検証（`javascript:`等を除外）、
  GitHubへの書き込みは実行のたびに失効する `GITHUB_TOKEN` のみ使用（長期シークレット不要）
- **2026-07-27、GitHub Actions上での手動実行（workflow_dispatch）で動作確認済み。**
  実際にNHKニュース・ITmedia NEWSの記事が取得され、`data/news-live.json` が
  正しいスキーマでコミットされ、アプリの今日タブ・ニュースタブに実データが反映されることを確認した

## あなた向けニュースのタグ選択（実装順2番）

- `data/news-live.json` のスキーマ変更：`personal`（フラットな配列）を廃止し、
  `personalCategories`（`{id, label, items}` の配列）に変更
- `scripts/fetch_news.py`：`PERSONAL_CATEGORIES` に5カテゴリを定義し、それぞれ別のRSSを取得
  - テクノロジー：ITmedia NEWS
  - 経済／国際／スポーツ／エンタメ：NHKニュースの各カテゴリ別フィード（`cat2`,`cat5`,`cat6`,`cat7`）
  - カテゴリ単位で取得失敗時は該当カテゴリのみ前回データを維持
- `index.html`：ニュースタブの「あなた向け」サブタブ内に、勉強タブと同じ見た目のタグ（チップ）を追加。
  選択は単一選択で `localStorage`（`briefingApp.selectedNewsCategory`）に保存され、次回開いたときも復元される
- ブラウザで動作確認済み：タグ切り替え、選択の永続化、データが空のカテゴリでの空表示、
  「一般」サブタブが影響を受けないことを確認
- 経済／国際／スポーツ／エンタメの4カテゴリは、この変更をコミットした時点ではまだ
  実データが1回も取得されていない（プレースホルダーの空配列）。次回のバッチ実行
  （スケジュール、または手動のworkflow_dispatch）で実データに置き換わる

## Gemini APIによる問題生成 + PWA対応（実装順5番・6番）

個人専用でPWA化したい、という要望と、勉強タブの問題をAIで生成したいという要望を
まとめて実現するため、静的サイトのままではPWA（Service Worker）が動かせない
（`https://`等の安全なオリジンが必須）ことから、Cloudflare Pagesにデプロイする構成にした。

**構成**
- `functions/api/generate-questions.js`：Cloudflare Pages Function。
  `POST /api/generate-questions` に `{topic}` を送ると、Gemini API
  （`gemini-3.6-flash`、無料枠）を呼び出して問題3問を生成して返す
  - APIキーは`env.GEMINI_API_KEY`としてCloudflare側の環境変数（Secret）からのみ参照。
    コードにもリポジトリにも一切含まれない
  - `topic`は勉強タブの5種類の固定値のみ許可（自由入力不可）。ユーザー入力由来の
    テキストがプロンプトに一切含まれないため、プロンプトインジェクションの余地がない
  - レート制限を二重に実装：`QUIZ_KV`（KV名前空間）を使い、IP単位で1時間20回まで、
    全体で1日100回まで。超えた場合は429を返す
  - Gemini呼び出し失敗・レート制限超過など、あらゆる失敗時はエラーの詳細を返さず
    `{error: "..."}`とステータスコードのみ返す
- `index.html`：「問題を作る」ボタンはまず`/api/generate-questions`を呼び、
  失敗したら`data/briefing-sample.json`内の静的な問題バンク（下記）から選んだ問題に
  自動でフォールバックし、その旨を画面に小さく表示する
- `data/briefing-sample.json`：静的な問題バンクを3問→**40問**（5トピック×8問）に拡充。
  AI生成が使えない場合でも、ある程度のバリエーションが出るようにするため
- `manifest.json` / `icon.svg` / `icon-maskable.svg` / `sw.js`：PWA対応一式。
  Service Workerはアプリの殻（index.html等）をcache-first、
  `data/*.json`をstale-while-revalidate（キャッシュを即表示しつつ裏で更新）、
  `/api/*`は常にキャッシュせずネットワークに投げる方針

**重要な軌道修正（2026-07-28）**：当初「Cloudflare Pages + Pages Functions
（`functions/api/*.js`のファイルベースルーティング）」という構成で実装したが、
Cloudflareの現在のダッシュボードでは Pages が Workers（static assetsつき）に
統合されており、`/functions`フォルダの自動検出が効かず、
「Variables cannot be added to a Worker that only has static assets」
というエラーで環境変数を設定できなかった。そのため、以下の構成に書き直した：

- `functions/api/generate-questions.js` は削除
- `worker.js`：単一のWorkerスクリプト。`POST /api/generate-questions`は自前で処理し、
  それ以外は`env.ASSETS.fetch(request)`で静的ファイルを返す（ロジック自体は元のPages Function
  と同じ。プロンプト・レート制限・入力検証などの設計は変更なし）
- `wrangler.jsonc`：`main: "worker.js"`、`assets.directory: "./"`、
  `assets.binding: "ASSETS"` を定義。KVやシークレットはダッシュボード側で設定する前提
  （ファイルにはコミットしない）
- `.assetsignore`：`worker.js`・`wrangler.jsonc`・`scripts/`・`.github/`・`*.md`等を
  静的配信対象から除外（機密ではないが、公開する必要のないファイルのため）

**まだ動作確認できていないこと（Cloudflare側の手動セットアップが必要）**
このリポジトリのコードは書き終えているが、以下はアカウント操作が必要なため
作者側で行う必要がある：
1. Google AI StudioでGemini APIキーを発行（無料枠）
2. Cloudflareダッシュボードで「Compute」→「Workers & Pages」→「Create」から
   `Hetarou/MyBriefingApp` リポジトリ（`claude/briefing-app-skeleton`ブランチ）に接続
3. KV Namespaceを作成し（「Storage & Databases」→「Workers KV」、例：`briefing-app-quiz-kv`）、
   プロジェクトの Settings → Bindings で変数名 `QUIZ_KV` として紐付け
4. プロジェクトの Settings → Variables and Secrets で `GEMINI_API_KEY` を
   Secret（暗号化）として登録
5. `wrangler.jsonc`の追加により、Workerとしてコードを持つ状態になったはずなので、
   3・4の設定（特に環境変数）が可能になっているはずである。設定後、再デプロイして
   実際に問題生成が動くか・PWAとしてホーム画面に追加できるかを確認する

## 既知の制約

- `fetch("data/briefing-sample.json")` はローカルサーバー経由（`http://`）を前提にしている。
  ブラウザや設定によっては `file://` で直接開いた場合に fetch がブロックされることがある
  （今回の動作確認環境では `file://` でも正常に読み込めたが、環境によって挙動が異なりうる点は留意）

## やらないこと（今回のスコープ外）

- Google カレンダー連携（実装順4番）
- 外部ライブラリの利用、npm、ビルドツール
- 未読管理・通知・成績記録
- README 以外のドキュメントの追加
