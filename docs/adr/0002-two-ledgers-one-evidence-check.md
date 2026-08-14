---
adr: 0002
title: 台帳は観点ごとに分けるが、evidence の照合ロジックは 1 つに保つ
status: accepted
superseded_by: null
date: 2026-08-14
issues: [5]
tags: [evidence-ledger, verify, schema, code-analysis]
description: ランキング要因とコード自体の観察はスキーマを分けて別台帳にし、evidence 照合だけは共通の関数を通すことで検証の厳しさを揃える。
---

# ADR 0002: 台帳は観点ごとに分けるが、evidence の照合ロジックは 1 つに保つ

## 背景

ADR 0001 で作った `analysis/factors.yaml` は「投稿者が操作可能なランキング要因」専用の
スキーマ（`stage` / `author_controllable` / `direction`）を持つ。

その後、コードそのもの（設計・実装技法・エンジニアリングとしての判断）を扱いたくなった。
これは `author_controllable` を持たないし、`direction`（boost / suppress / gate）も意味を成さない。
一方で「読んだつもりで書く」失敗モードは同じかそれ以上に起きやすく、
evidence の必須性と機械照合は同じ強さで必要になる。

## 決定

**スキーマは分け、evidence の照合は共通化する。**

- `analysis/code.yaml` を新設し、`topic` / `title` / `summary` / `takeaway` / `confidence` を持たせる。
  `factors.yaml` とはフィールドが重ならない（共通なのは `id` / `evidence` / `summary` / `confidence`）。
- `verify-evidence.py` に `LedgerSpec`（ファイル名・エントリのキー・ID 接頭辞・必須キー・enum・集計キー）を導入し、
  台帳を `LEDGERS` タプルに列挙する形にする。
- **`check_evidence` は 1 つだけ**。全台帳がこの関数を通る。台帳を足すときに書くのは `LedgerSpec` の
  1 エントリだけで、検証の厳しさは自動的に揃う。
- `id` 接頭辞で台帳を区別する（`F001` = 要因、`C001` = コード観察）。

## 捨てた案

- **1 つの台帳に両方を入れ、任意フィールドで区別する** — `author_controllable` が要因にだけ必要になり、
  「無くてもよいフィールド」が増える。必須チェックが緩むと、書き手が埋めるべき欄を埋めなくても通ってしまう。
- **台帳ごとに verify スクリプトを分ける** — 片方だけ検証が緩い状態が起きうる。
  そうなると「この repo の主張は全部裏が取れている」という不変条件が読み手から見て確認できなくなる。
  これは台帳方式の価値そのものを損なう。
- **コード観察は散文の Markdown に書く** — ADR 0001 で退けた理由がそのまま当てはまる。
  実際、初回投入 45 件のうち 1 件は行番号がずれており、`make verify` が検出した。
  散文で書いていれば誰も気づかないまま残った。

## 変えてよい前提 / 壊すと危ない前提

- **変えてよい**:
  - `TOPICS` の顔ぶれ（実際に `algorithm` は初回投入時に追加した）
  - `code.yaml` の固有フィールド（`takeaway` の要否など）
  - 3 本目の台帳を足すこと（`LEDGERS` に 1 エントリ追加するだけで済むようにしてある）
- **壊すと危ない**:
  - **`check_evidence` が 1 箇所であること**。台帳ごとに照合を書き分けた時点で、
    緩い方が抜け道になる
  - **`evidence` の必須性**。「観察は面白いが根拠が無い」を 1 件でも通すと、
    読み手はどのエントリが裏取り済みか区別できなくなる
  - **`source_ref` と `source.lock` の一致チェックを全台帳に適用すること**。
    台帳ごとに違う commit を指せる状態は、行番号の意味を壊す
