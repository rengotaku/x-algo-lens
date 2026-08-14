---
adr: 0001
title: 解析成果は散文ではなく機械検証可能な根拠台帳に置き、解析対象を commit でピン留めする
status: accepted
superseded_by: null
date: 2026-08-14
issues: []
tags: [evidence-ledger, verify, vendor, pinning]
description: 解析結果を factors.yaml の path:line:snippet に固定し、pinned commit の実ファイルと機械照合することで「読んだつもりの要約」を構造的に排除する。
---

# ADR 0001: 解析成果は散文ではなく機械検証可能な根拠台帳に置き、解析対象を commit でピン留めする

## 背景

xai-org/x-algorithm は 2,015 ファイル・4 言語（Scala / Rust / Python / Java）規模で、
全体を読み切って頭に入れることはできない。必然的に「関連しそうな箇所を探して読む」進め方になる。

この進め方の主要な失敗モードは 2 つある。

1. **読んだつもりで書く** — grep がヒットした、ファイル名がそれらしい、という段階で
   要約を書いてしまう。出力はもっともらしいので、後から読む人間には区別がつかない。
   解析が精緻に見えるほど誤りが発見されにくくなる。
2. **上流の更新で根拠が静かに腐る** — 行番号や実装は上流の commit で動く。
   ピン留めが無いと、書いた時点では正しかった記述がいつの間にか実体と乖離する。

散文のレポートはこのどちらも検知できない。

## 決定

- 解析成果の本体を `analysis/factors.yaml` の構造化台帳にする。1 要因 = 1 エントリで、
  **最低 1 件の evidence（`path` / `line` / `snippet`）を必須**にする。
- 解析対象は `source.lock` の `COMMIT` で 40 桁 SHA にピン留めし、`make fetch` は
  その SHA でのみ取得する（取得後に HEAD を照合し、不一致なら異常終了）。
- `make verify` が全 evidence を vendor の実ファイルと突き合わせ、
  ファイル欠落・行範囲外・snippet 不一致・`source_ref` と `source.lock` の乖離のいずれかがあれば
  **exit 1**。`make ci` = `fetch` + `verify` をゲートにする。
- `vendor/` は git 管理外。リポジトリには**根拠の座標だけ**が入り、対象コードは入らない。

これにより「snippet を書き写した = 実際にその行を開いた」が構造的に強制される。

## 捨てた案

- **Markdown のレポートに引用を貼る** — 引用は劣化コピーで、貼った時点から実体と切り離される。
  上流更新時にどこが壊れたかを機械的に列挙できない。
- **解析対象を submodule で持つ** — SHA 固定は満たすが、clone コストが常時かかり、
  「読むだけ」という位置づけに対して重い。`.gitignore` した `vendor/` + lock ファイルで足りる。
- **evidence を行番号だけにする（snippet 無し）** — 上流更新で行がズレたとき、
  「別の行を指したまま検証は通る」状態になる。snippet があれば必ず落ちる。
- **evidence 無しの要因も低 confidence で載せる** — 台帳の価値は「載っているものは全部裏が取れている」
  という不変条件にあり、例外を作った時点で全体の信頼度が読み手から見て不明になる。
  未確認事項は `notes` と調査タスクに置く。

## 変えてよい前提 / 壊すと危ない前提

- **変えてよい**:
  - 台帳の enum（`stage` / `direction` / `confidence` の値）。`verify-evidence.py` の定数と
    `analysis/README.md` を同時に更新すれば足りる
  - `source.lock` の `COMMIT`（上流追従。`factors.yaml` の `source_ref` と同時に上げる）
  - 台帳のフォーマット（YAML であること自体は本質ではない）
- **壊すと危ない**:
  - **evidence 必須**と **snippet 照合**。どちらかを緩めると、この repo の唯一の品質保証が消える
  - **verify の fail-closed**。vendor が無い・HEAD がズレている場合に「検証をスキップして成功」に
    倒すと、実質的に検証していない状態が緑で通る
  - **`source_ref` と `source.lock` の一致チェック**。片方だけ更新した状態を許すと、
    台帳がどの commit に対する主張なのか特定できなくなる
