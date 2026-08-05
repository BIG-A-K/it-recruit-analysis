# SubAgent結果契約

`company-analysis` が並列起動するworkerの共通出力形式。workerは最終応答として、説明文やMarkdownコードフェンスを付けずに次の形のYAMLを1つだけ返す。すべてのトップレベルフィールドを必須とし、該当がなければ空配列 `[]` を使う。

```yaml
schema_version: 1
worker: company-ir-worker
company_id: example
outcome: done
items:
  - id: ir-revenue
    phase: ir
    status: done
    value: metrics.csv の revenue（2023〜2025年度、3行）
    subject: 連結
    as_of: 2023-03-31〜2025-03-31
    unit: JPY
    source: source-id または公式URL+公表日
    via: 実行したCLI・検索期間、または確認経路
    note: ""
artifacts:
  - path: data/metrics.csv
    action: updated
    added_rows: 3
    updated_rows: 0
commands:
  - uv run --env-file .env edinet-fetch example --start 2024-01-01 --end 2025-06-30
documents:
  - id: S100XXXX
    url: https://example.com/official-document.pdf
    published_at: 2025-06-30
checks:
  - name: metric coverage
    result: passed
warnings: []
```

## フィールド

| フィールド | 規則 |
| --- | --- |
| `schema_version` | 現在は `1` 固定 |
| `worker` | 起動されたagent名と一致させる |
| `company_id` | 親から渡された採用主体IDと一致させる |
| `outcome` | `done` / `partial` / `blocked` |
| `items` | 担当する台帳行だけを返す。各 `id` は既存台帳と一致させる |
| `items[].status` | `done` / `not_disclosed` / `pending`。未完了を完了扱いしない |
| `artifacts` | 実際に変更したファイルだけ。read-only workerは空配列 |
| `commands` | 実際に実行した取得・正規化・検証コマンド |
| `documents` | 根拠にした一次資料の識別子・公式URL・公表日 |
| `checks` | worker内で実施した充足確認・差分確認 |
| `warnings` | 欠損、曖昧さ、失敗、親agentによる確認が必要な事項 |

`outcome: done` は、担当する全 `items` が `done` または `not_disclosed` で、必要なartifact更新と確認が完了した場合だけ使う。1行でも `pending` があれば `partial`、処理を開始・継続できない場合は `blocked` にする。

担当するitemは親agentがtask promptで渡したIDに限定する。再開時に完了済みitemを再調査・再出力せず、割り当てられた未完了itemだけを返す。

## Writer境界

| 出力 | writer |
| --- | --- |
| IR用CSVと再取得可能な原本 | `company-ir-worker` |
| workerの最終YAML | 各worker |
| `ledger/<company_id>.yaml` | `company-analysis` 統括agentだけ |
| 企業MDX | `company-analysis` 統括agentが呼ぶ `company-article` だけ |

workerは台帳の `phases` や `updated_at` を変更しない。read-only workerはプロジェクトファイルを一切変更しない。

CSVへの書き込みは、正規化CLI（`edinet-normalize` / `sec-normalize`）と `uv run csv-upsert <table>` だけを使う。CSVをテキストとして直接編集しない。`csv-upsert` が報告する `N added, N updated` を `artifacts` の `added_rows` / `updated_rows` へそのまま記載する。

## 親agentの受入検査

親agentはworker結果をそのまま信用せず、次を確認してから台帳へ統合する。

- `schema_version`、`worker`、`company_id` が期待値と一致する。
- 全 `items[].id` が台帳に存在し、そのworkerの担当phaseに属する。
- `done` の行は値・対象・時点・出典がそろい、根拠が公式一次資料である。
- `not_disclosed` の行は確認した公式資料またはページと確認範囲が `note` にある。
- IR workerの `artifacts` と行数は実際のGit差分およびCSV主キーで再確認する。
- `pending` を含むphaseは `done` にしない。完了済みの別phaseを上書きしない。
