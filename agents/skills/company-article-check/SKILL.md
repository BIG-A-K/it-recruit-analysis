---
name: company-article-check
description: 企業MDX記事を読み取り専用で監査し、構成・出典・新卒採用・事業・IRデータとの不整合を行番号付きで報告する。「企業記事を監査して」「記事の問題を洗い出して」「company-article-check」で使う。記事の執筆・更新依頼には使わない。
argument-hint: "target=<company_id|path|changed|all> [project-root=<path>] [validate=none|check|build]"
---

# 企業記事の読み取り専用監査

企業記事とローカルに保存された根拠を照合し、修正すべき箇所を特定する。MDX、CSV、台帳、コードは変更しない。記事の執筆や修正は `company-article`、根拠の再調査は `company-research` または `company-ir` の担当とする。

## 入力

| 引数 | 未指定時 |
| --- | --- |
| `target=<company_id｜path｜changed｜all>` | 依頼から1社を特定できればその企業。特定できなければ確認する |
| `project-root=<path>` | `data/` と `site/src/pages/companies/` を持つ現在地、次に `../it-recruit` |
| `validate=none｜check｜build` | `check` |

- `company_id`: `site/src/pages/companies/<company_id>.mdx` の1記事を監査する。
- `path`: 指定された企業MDXを1記事監査する。
- `changed`: Gitの作業ツリー、ステージ、未追跡ファイルで変更・追加・削除された `site/src/pages/companies/*.mdx` を監査する。
- `all`: `site/src/pages/companies/*.mdx` をすべて監査する。

## 正本

規約が食い違う場合は、次の順で判定する。既存記事は実例であり、規約の正本にはしない。

1. [企業記事の執筆と検証](../company-article/SKILL.md)
2. [企業MDXテンプレート](../company-article/references/mdx-template.md)と[検算・記事の充足](../company-article/references/checklist.md)
3. [ledgerの規約](../company-analysis/references/ledger.md)、[外資系企業の規約](../company-analysis/references/foreign-companies.md)、`docs/content/companies.md`、`docs/data/README.md`、`docs/data/schema.md`
4. レイアウト、コンポーネント、データローダー、テストの実装

## ワークフロー

### 1. 対象を固定する

`project-root` を確定し、入力規則に従ってMDXパスを列挙する。`changed` ではGitの未ステージ・ステージ・未追跡をすべて確認し、企業MDX以外の変更は対象へ加えない。削除されたMDXも削除前パスの `company_id` を対象にし、企業マスターとの整合性を判定する。対象が0件なら、その事実を報告して停止する。重複したパスは1件にまとめる。

**完了条件**: 監査する `company_id` とMDXパスの一意な一覧、および対象を選んだ方法を示せる。

### 2. 規約とローカル根拠を読む

このスキルの [監査チェックリスト](references/checklist.md) と「正本」に挙げた資料を読む。各記事について、存在する範囲で次を読む。

- `site/src/pages/companies/<company_id>.mdx`
- `ledger/<company_id>.yaml`
- `data/companies.csv`、`company_industries.csv`、`company_relations.csv`
- `data/metrics.csv`、`segments.csv`、`sources.csv`
- コンポーネントが参照する場合だけ、`data/company_profiles.csv` などの表示用フォールバック
- 記事が別の開示主体を指定する場合、その主体の上記CSV行と台帳
- 判定に関係する `CompanyLayout.astro`、企業コンポーネント、データローダー、テスト

台帳がない、または未完了のフェーズがある場合も監査は続ける。ただし、その根拠が必要な項目を推測で埋めず `未評価` とする。

**完了条件**: 記事ごとに、読み込んだ根拠と存在しなかった根拠を列挙できる。

### 3. 根拠の境界を固定する

判定根拠は、対象記事、リポジトリ内の資料、ユーザーが提示した情報に限定する。外部URLを開かず、リンク先の到達性、現在の掲載内容、最新性を検証済みとみなさない。

記事中のリンクは「出典が近くに示されているか」の判定には使えるが、「リンク先が主張を裏付けるか」の判定には、台帳やCSVに対応する記録が必要となる。根拠が不足する場合は、事実を補完せず、必要な資料を示して `未評価` とする。

**完了条件**: 各判定を、実際に読んだローカル根拠へ結び付けられる。外部確認が必要な事項を `OK` と断定していない。

### 4. 記事とデータを監査する

`references/checklist.md` の A〜G 群を順に適用する。条件付き要素は、企業の上場区分、開示状況、採用主体と開示主体、セグメント開示の有無を先に確認してから判定する。タグの有無だけでなく、渡された `companyId` とCSV行を追い、空欄、`確認中`、空の表・グラフが生成されないかまで確認する。

各項目を `OK` / `WARN` / `NG` / `該当無し` / `未評価` のいずれかで埋める。規約違反と、規約どおりか判断できない情報不足を混同しない。

**完了条件**: 対象記事とチェック項目の全組み合わせに判定があり、`WARN` / `NG` / `未評価` には記事ごとの根拠がある。

### 5. 自動検証を実行する

`validate=check` または `build` では、次を実行する。

```bash
uv run pytest tests/test_data_integrity.py
npm --prefix site run check
```

`validate=build` では、さらに次を実行する。

```bash
npm --prefix site run build
```

失敗を対象記事へ帰属できる場合だけ、その記事の判定へ反映する。無関係な既存失敗は「全体検証の失敗」として分ける。実行しなかったコマンドを成功扱いしない。

**完了条件**: 各コマンドについて、実行済み・未実行、終了結果、対象記事との関係を区別して記録している。

### 6. 監査レポートを出す

単一記事では全チェック項目を表示する。複数記事では、記事別集計と項目別集計を表示した後、`WARN` / `NG` / `未評価` をすべて列挙する。指摘は `NG`、`WARN`、`未評価` の順に並べる。

**完了条件**: 各指摘にチェックID、引用、ファイルと行番号、違反した規約、観測した根拠、具体的な修正方針または追加で必要な根拠がある。

## 出力形式

```markdown
## 監査対象

- 対象: <company_id または scope>
- 記事: <path一覧>
- ローカル根拠: <読み込んだ台帳・CSV等>
- 検証: <command: PASS / FAIL / 未実行>

## 指摘

### NG

1. **[C2] 職種別の勤務地・待遇が不足**
   対象: `site/src/pages/companies/example.mdx:L42-L46`
   引用: 「<該当箇所>」
   規約: `company-article/references/mdx-template.md` の「採用情報・新卒情報」
   根拠: `ledger/example.yaml` には職種別勤務地が記録されているが、記事の表に反映されていない。
   修正: 表へ勤務地列を追加し、台帳に記録された各職種との対応を反映する。

### WARN

<同じ形式。なければ「なし」>

### 未評価

<不足している根拠と、再評価に必要な資料を同じ形式で示す。なければ「なし」>

## チェック結果

| # | 項目 | 判定 | コメント |
| --- | --- | --- | --- |
| A1 | 記事と企業IDの同一性 | OK | ... |
| ... | ... | ... | ... |

## 総評

<公開を妨げる問題、主要な改善点、未評価リスクを1〜3文で要約>
```

複数記事の `## チェック結果` は次の2表に置き換える。

```markdown
### 記事別集計

| 記事 | OK | WARN | NG | 該当無し | 未評価 |
| --- | ---: | ---: | ---: | ---: | ---: |

### 項目別集計

| # | OK | WARN | NG | 該当無し | 未評価 | 非OKの記事 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
```

## ルール

- **読み取り専用**: MDX、CSV、台帳、コード、Gitの状態を変更しない。修正依頼へ自動的に移行しない。
- 指摘には、対象記事の引用と `L42` または `L42-L46` 形式の位置を必ず付ける。CSVや台帳の不整合では、そのファイルの行またはキーも示す。
- 修正案に未提示の企業名、数値、日付、原因、意図を追加しない。値が必要なら `〈要再調査: 新卒採用の対象年度〉` のように、確認対象を示す。
- 規約に反する状態は `NG`、理解を妨げない改善提案は `WARN`、企業の条件上不要な項目は `該当無し`、ローカル根拠不足で判断できない項目は `未評価` とする。
- 台帳の `not_disclosed` は、確認した公式資料と範囲が記録されている場合だけ根拠に使う。台帳がないことや未調査を「非公表」と読み替えない。
- Gitの更新日時やMDXの `originalPublishedAt` を、採用情報・IR情報の最新性の根拠にしない。
- 既存記事の多数派を正解とみなさない。正本と異なる既存表現は、レガシーであってもそのまま指摘する。
- 外部リンクの内容や到達性は検証範囲外と明記する。URLがあるだけで内容を確認済みと書かない。
- 監査中にIR取得、CSV upsert、Web調査を開始しない。不足根拠の担当が明確なら `company-research`、`company-ir`、`company-article` のどれへ引き渡すべきかを示す。
- テストやビルドを実行した場合はコマンドと結果を記録する。未実行なら、記述上・静的な監査だけを行ったと明示する。

## 参照リソース

- [references/checklist.md](references/checklist.md): 判定ID、判定対象、基準となる規約。
- [企業記事の執筆と検証](../company-article/SKILL.md): 記事作成側の正本。
- [企業MDXテンプレート](../company-article/references/mdx-template.md): セクション順、書式、文体、条件付き省略。
- [検算・記事の充足](../company-article/references/checklist.md): 数値検算と記事充足の正本。
- [ledgerの規約](../company-analysis/references/ledger.md): ローカル調査根拠と `not_disclosed` の判定規則。
- [外資系企業の規約](../company-analysis/references/foreign-companies.md): 採用主体・開示主体・報告セグメントの分離規則。
