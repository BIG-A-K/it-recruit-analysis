---
name: company-ir
description: 企業1社のIR数値を法定開示から取得・正規化してCSV（sources/metrics/segments）へupsertする。EDINET/SECの既存CLIを優先し、失敗時だけ公式IRサイトをクロールする。「IRデータを取得して」「財務データを更新して」「EDINETから取って」で使う。
argument-hint: "company_id [fiscal-year=YYYY] [project-root=<path>] [mode=standalone|worker]"
---

# 企業IRデータ収集

調査台帳の `ir` フェーズを実行し、`data/sources.csv` / `metrics.csv` / `segments.csv` を更新する。
比較・集計する数値はCSVだけに書き、MDXへは書かない。台帳の扱いは [ledgerの規約](../company-analysis/references/ledger.md) に従う。
`mode=worker` ではCSV更新と確認だけを担当し、台帳を編集せず [worker結果契約](../company-analysis/references/worker-contract.md) に従って統括agentへ返す。

## 入力

| 引数 | 未指定時 |
| --- | --- |
| `company_id` または企業名（必須） | — |
| `fiscal-year=<年度>` | 取得可能な最新年度を含む3期以上 |
| `project-root=<path>` | `data/` を持つ現在地、次に `../it-recruit` |
| `mode=standalone｜worker` | `standalone` |

## 事前に読む資料

- `docs/data/schema.md` — 列・主キー・参照整合性
- [references/edinet.md](references/edinet.md) — EDINET取得の標準経路とフォールバック
- 海外の開示主体は [foreign-companies.md](../company-analysis/references/foreign-companies.md)

## ワークフロー

### 1. 台帳を開く

`ledger/<company_id>.yaml` を読み、採用主体・開示主体と `ir` の調査行を確認する。

- `mode=standalone`: `phases.ir` を `in_progress` にする。台帳がない場合だけ、[ledgerの規約](../company-analysis/references/ledger.md) に従って `ir` フェーズの行だけを持つ台帳を新規作成する。
- `mode=worker`: 台帳は読み取り専用。台帳がない、企業境界が未確定、または `ir` の行が不足している場合はファイルを作らず `outcome: blocked` を返す。

**完了条件**: `ir` フェーズの全調査行が台帳にある。

### 2. 取得経路と検索期間を決める

開示主体で経路を選ぶ。

| 開示主体 | 手順 |
| --- | --- |
| EDINET提出企業 | [references/edinet.md](references/edinet.md) |
| 海外の開示主体 | [foreign-companies.md](../company-analysis/references/foreign-companies.md) |
| `edinet_code` が空 | CLIを実行せず「EDINET対象外」と記録し、公式IR資料でCSV対象項目を確認する |

検索期間はどちらの経路でも同じ規則で決める。

| 条件 | 期間 |
| --- | --- |
| ユーザー指定あり | その期間 |
| `fiscal-year=YYYY` | `YYYY-01-01` 〜 `(YYYY+1)-06-30`（終了日が未来なら実行日） |
| 未指定 | 実行日の400日前 〜 実行日 |

**完了条件**: 経路と期間が台帳の `via` に書ける形で確定している。

### 3. 既存CLIで取得し、失敗時はクロールする

CLIが失敗するか対象書類が見つからないときは、期間を勝手に変えない。使用した期間と失敗理由を記録し、開示主体の公式IRサイトをクロールして同じ対象年度の一次資料を探す。`mode=standalone` では台帳へ、`mode=worker` では最終YAMLの `items[].via` / `note` / `warnings` へ記録する。クロール手順は [references/edinet.md](references/edinet.md) に従う。

**完了条件**: CLIが正常終了したか、失敗内容を記録して公式IRサイトのクロールを完了している。どちらの経路でも `sources.csv` / `metrics.csv` / `segments.csv` の差分を確認済み。

### 4. CLI対象外とクロール取得分だけを補完する

法定開示にない公式IR資料、クロールで取得した一次資料、`company_annotations.csv` だけを、現行スキーマの主キーで補完する。
CLIが正常に書いた指標・セグメントを上書きしない。対象外の行、未知の列、既存の並びを壊さない。

**完了条件**: 追加した行すべてに `sources.csv` の `source_id` が対応している。

### 5. 指標の充足を確認する

`uv run coverage-report <company_id>` が利用できる場合はそれを実行する。未導入なら `metrics.csv` の開示主体の行を `metric_key` 別に数え、[mdx-templateの棒グラフ表](../company-article/references/mdx-template.md) の全キーと `HealthMetrics` の3キーがそろっているか確認する。

欠けているキーは、取得済みの法定開示か公式IR資料の該当箇所を読み直す。資料に値がある場合は出典とともに不足行を補完する。**開示自体がない場合だけ欠損**として扱い、報告する。

**完了条件**: 全キーについて「そろった」か「開示がない」のどちらかが確定している。

### 6. 台帳またはworker結果を確定する

- `mode=standalone`: `ir` の各行の `status` / `value` / `source` / `via` を埋め、`phases.ir` を `done` にして `updated_at` を更新する。
- `mode=worker`: 台帳を編集せず、各 `ir` 行、変更したartifact、実行コマンド、原本、カバレッジを [worker結果契約](../company-analysis/references/worker-contract.md) のYAMLで返す。

**完了条件**: `ir` の全行が `done` か `not_disclosed`。`mode=worker` では加えて、実際のCSV差分と `artifacts` の行数が一致している。

## やらないこと

- 検索結果のスニペット、IRまとめサイト、第三者サイトを根拠にしない。
- 推定値、前年度の流用、他社の値、親会社の値で欠損を埋めない。欠損はスキーマの `availability` で表し、数値列へ説明文字列を入れない。
- 企業ごとの一回限りの取得・変換コードを書かない。
- `net_cf` などサイトが算出する派生値をCSVへ保存しない。
- 評価・応募判断・投資判断をCSVへ保存しない。

## 出力

- 実行したCLI・引数・検索期間と、取得した原本の識別情報（`doc_id` またはアクセッション番号）。クロールへ切り替えた場合は失敗理由、起点URL、取得した一次資料のURL
- 追加・更新したIR年度と、CSVごとの行数
- 棒グラフ用 `metric_key` の年度別カバレッジと欠損キー
- `mode=standalone` では台帳の更新内容（`done` / `not_disclosed` の行数）
- `mode=worker` では [worker結果契約](../company-analysis/references/worker-contract.md) に適合するYAMLのみ

## 参照リソース

- [references/edinet.md](references/edinet.md): EDINET CLIの使い方と、失敗時のクロール手順。
- [worker-contract.md](../company-analysis/references/worker-contract.md): 並列workerの出力形式とwriter境界。
