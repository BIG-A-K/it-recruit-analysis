---
name: company-research
description: 企業1社の新卒募集要項と事業セグメントを公式サイト・IR資料から調査し、調査台帳へ記録する。MDXはまだ書かない。「採用情報を調べて」「募集要項を更新して」「事業セグメントを調べて」で使う。
argument-hint: "company_id [project-root=<path>] [scope=recruit|segments|all] [mode=standalone|worker]"
---

# 採用・事業セグメント調査

調査台帳の `recruit` / `segments` フェーズを実行する。`mode=standalone` の成果は台帳へ書き、MDXの作成・更新は `company-article` に任せる。台帳の扱いは [ledgerの規約](../company-analysis/references/ledger.md) に従う。
`mode=worker` では公式情報の調査だけを担当し、台帳を編集せず [worker結果契約](../company-analysis/references/worker-contract.md) に従って統括agentへ返す。

## 入力

| 引数 | 未指定時 |
| --- | --- |
| `company_id` または企業名（必須） | — |
| `project-root=<path>` | `ledger/` と `data/` を持つ現在地、次に `../it-recruit` |
| `scope=recruit｜segments｜all` | `all` |
| `mode=standalone｜worker` | `standalone` |

## ワークフロー

### 1. 台帳を開き、前提を確認する

`ledger/<company_id>.yaml` を読み、`scope` に対応する調査行を確認する。

- `scope=recruit` はIR完了を前提にしない。
- `scope=segments` または `all` の `mode=standalone` は、`phases.ir` が `done` でなければ先に `company-ir` を実行する（ユーザーがIR不要と明示したときだけ省略する）。
- `mode=worker` は台帳を読み取り専用とし、`phases.ir` の完了を待たない。セグメント定義は公式の法定開示・決算資料を直接確認し、並行実行中のIR workerの未確定結果に依存しない。
- 台帳がない場合、`mode=standalone` だけが [ledgerの規約](../company-analysis/references/ledger.md) に従って対象scopeの行を新規作成できる。`mode=worker` は `outcome: blocked` を返す。

`mode=standalone` では対象scopeの `phases` を `in_progress` にする。`mode=worker` では `phases` を変更しない。

**完了条件**: 対象scopeの全調査行が台帳にあり、前提の判断を報告している。

### 2. 公式サイトから募集要項を集める

`scope=recruit` または `all` のときだけ実行する。

公式採用サイト、新卒採用トップ、職種別募集要項を順に確認し、`recruit` の調査結果を埋める。保存先は `mode=standalone` では台帳、`mode=worker` では最終YAMLとする。
勤務地と待遇は職種別募集要項から取得する。共通ページや募集ページ末尾にだけ記載されている場合は、適用される職種が分かるように `subject` へ記録する。

**完了条件**: 公開中の新卒職種をすべて確認し、各職種の勤務地を含む全項目が「公式ページから取得（`done`）」または「公式ページに記載なし（`not_disclosed`）」のどちらかになり、共通条件は適用職種と対応している。`mode=standalone` では `phases.recruit` が `done`、`mode=worker` では全 `recruit` itemが最終YAMLで完了状態になっている。

### 3. セグメントごとの内容を書く

`scope=segments` または `all` のときだけ実行する。`mode=standalone` では `phases.segments` を `in_progress` にする。
公式コーポレートサイト・サービスサイトから、各事業の具体的なサービス名、ブランド名、提供内容、運営法人を調査結果へ書く。続いて法定開示・決算資料を読み、報告セグメントの名称・定義・事業区分・対象地域・組織再編を補足する。関連企業（親会社・主な子会社）も具体名で記録する。保存先は `mode=standalone` では台帳、`mode=worker` では最終YAMLとする。

公式サイト上の事業区分とIRの報告セグメントが異なる場合は独自に統合せず、対応関係と差異を記録する。

**完了条件**: 現行の全報告セグメントに具体的な事業・サービスが対応し、各説明に公式サイトとIR資料の出典がある。対応不能な区分は理由が記録されている。`mode=standalone` では `phases.segments` が `done`、`mode=worker` では全 `segments` itemが最終YAMLで完了状態になっている。

### 4. 台帳またはworker結果を確定する

- `mode=standalone`: 対象scopeの全行の `status` / `value` / `source` / `as_of` を確認し、担当 `phases` と `updated_at` を更新する。
- `mode=worker`: 台帳を編集せず、対象scopeの各行と確認した一次資料を [worker結果契約](../company-analysis/references/worker-contract.md) のYAMLで返す。

**完了条件**: 担当する全行が `done` か `not_disclosed`。

## やらないこと

- 検索結果のスニペット、求人媒体、第三者サイトで補完しない。
- 旧記事（`yukijya_doh`）は募集項目の探索にだけ使い、現在の公式ページで再確認する。
- セグメント別売上・利益の数値は `segments.csv`（`company-ir`）が正本。台帳へ複写しない。
- MDXを作成・更新しない。

## 出力

- 調査した職種数・セグメント数と、確認した公式URL・確認日
- 「公式ページに記載なし」とした項目の一覧
- 公式の事業区分とIR報告セグメントの対応関係と差異
- `mode=worker` では上記を [worker結果契約](../company-analysis/references/worker-contract.md) に格納したYAMLのみ

## 参照リソース

- [worker-contract.md](../company-analysis/references/worker-contract.md): 並列workerの出力形式とwriter境界。
