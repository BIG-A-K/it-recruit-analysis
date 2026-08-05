# EDINET取得の標準経路

国内のEDINET提出企業から、`sources.csv` / `metrics.csv` / `segments.csv` を更新する手順。
検索期間は `company-ir` のワークフロー手順2の規則で決める。

## 手順

1. `companies.csv` に対象企業の `company_id` があることを確認する。新規企業は先にこのマスタ行を確定する。
2. `EDINET_API` が使えるなら、原本が取得済みでも次を実行する。`edinet-fetch` は取得済み原本を再ダウンロードせず、主キーでupsertする。

   ```bash
   uv run --env-file .env edinet-fetch <company_id> \
     --start <YYYY-MM-DD> \
     --end <YYYY-MM-DD>
   ```

3. 通常は最新の有価証券報告書だけを処理する。`--all` はユーザーが期間内の全書類を明示したときだけ使う。
4. APIを使わず取得済み原本を再変換する場合だけ、原本ディレクトリと対応する `sources.csv` 行の存在を確認してから次を使う。

   ```bash
   uv run edinet-normalize <company_id> <doc_id> \
     --period-end <YYYY-MM-DD>
   ```

## CLIが期待どおり動かないとき

| 状況 | 対応 |
| --- | --- |
| CLIが失敗した | 原因、実行コマンド、検索期間を記録し、開示主体の公式IRサイトのクロールへ切り替える |
| 取得・正規化が未対応のXBRL要素で失敗した | 失敗内容を記録して公式IRサイトのクロールへ切り替え、CLIの未対応箇所を報告する |
| 対象書類が見つからない | 期間を勝手に変えず、使用した期間を記録して公式IRサイトのクロールへ切り替える |
| EDINETにない公式IR資料を補完したい | 先に `sources.csv` をupsertし、その `source_id` を使ってIR行をupsertする |

## クロールへのフォールバック

1. `companies.csv` の公式URLから同一法人のIR・ライブラリ・決算資料ページをたどる。
2. 対象年度の有価証券報告書を優先し、なければ決算資料、統合報告書の順で一次資料を取得する。
3. 資料名、対象年度、公開日、URL、確認日、EDINET失敗理由を記録する。`mode=standalone` では台帳、`mode=worker` ではworkerの最終YAMLを保存先にする。
4. 原本を `sources.csv` に登録し、その `source_id` を使って `metrics.csv` / `segments.csv` の不足行だけを現行主キーでupsertする。

公式IRページと、そこから直接リンクされた公式文書だけを対象にする。検索結果のスニペット、IRまとめサイト、求人・投資情報サイトを根拠にしない。
CLIが正常に書いた指標とセグメントを、クロール取得分で上書きしない。
企業ごとの一回限りの変換コードを作らない。
