---
id: "0001"
title: "AIクローラー向けのデータ公開基盤を整備する"
status: open
priority: medium
created: 2026-08-05
updated: 2026-08-05
tags: [enhancement, ai, data]
---

## 背景・概要

企業記事と構造化データをAIが発見・取得・引用しやすい形で公開する。
人間向け記事とAI向け記事を別々に管理せず、既存のCSVとMDXを正本として
HTML、Markdown、JSON、CSVなどの公開形式を生成し、内容の不一致を防ぐ。

## 仕様・要件

- `data/*.csv` のうち公開可能な正規化済みデータを公開する
- 企業単位でデータと出典を取得できるJSONエンドポイントを提供する
- 必要に応じて、MDXとCSVからAI向け企業ファクトシートをMarkdownで生成する
- `llms.txt`、`sitemap.xml`、`robots.txt` から公開コンテンツへの導線を設ける
- HTMLからJSON・Markdownへ代替表現を案内する
- 数値の年度、単位、連結・単体、基準日、欠損、計算値を機械判読できる形で表現する
- `source_id` を維持し、各データから出典へ到達できるようにする

## 考慮・調査事項

- `llms.txt` は補助的な慣習であり、AIクローラーによる利用は保証されない
- AI専用の重複記事を手作業で管理せず、CSVとMDXから生成する
- 本番オリジン、canonical URL、JSON-LD、ライセンス、更新日時を先に定義する
- `data/raw/`、個人情報、再配布できない原資料は公開しない
- CSV Injection、キャッシュ、データ量、URLの永続性を確認する
- `scripts/sync-r2.sh` は現状CSV用のContent-Typeを前提としているため、JSONやMarkdownの配置先を分ける
- 公開データのスキーマとJOIN方法を文書化する

## 完了条件

- [ ] 公開対象データとライセンスが決定されている
- [ ] 公開CSVにスキーマ、更新日時、出典情報への導線がある
- [ ] 企業別JSONからプロフィール、業績、セグメント、採用情報、出典を取得できる
- [ ] HTML上の主要な事実から安定した出典アンカーへ移動できる
- [ ] sitemap、robots、canonical、構造化データが本番URLで正しく生成される
- [ ] `llms.txt` が主要記事とデータセットを案内している
- [ ] AI向けMarkdownを提供する場合、CSV・MDXから自動生成される
- [ ] データ整合性テストとAstroビルドが成功する

## メモ

既存の正本は `data/*.csv`、企業記事は
`site/src/pages/companies/*.mdx`。企業別JSONや `llms.txt` は
Astroの静的エンドポイントとして生成する案を優先する。
