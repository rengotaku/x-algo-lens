# x-algo-lens

X（旧 Twitter）が Apache-2.0 で公開した推薦アルゴリズム [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) を読み、
**「投稿者が操作可能なランキング要因」だけを根拠付きで抽出する**ための解析リポジトリ。

## これは何で、何ではないか

| | |
|---|---|
| **やること** | 公開コードを読み、ランキングに効く要因を「該当ファイル:行 + その行の実文字列」まで固定した台帳にする |
| **やらないこと** | X 本番環境の再現・スコアの予測・「何点なら伸びる」の断定 |

公開されているのは本番システムの**コードとデフォルト値**であり、実際に稼働している学習済みモデル・
feature switch の本番値・リアルタイムのユーザー特徴量は含まれない。
本リポジトリの記述は「**コードにこう書いてある**」までしか主張しない。

## 中核: 根拠台帳（evidence ledger）

解析結果は散文ではなく `analysis/factors.yaml` に構造化して置く。1 要因 = 1 エントリで、
必ず `path` / `line` / `snippet`（その行に実在する文字列）を持つ。

`make verify` が、台帳の全 evidence を**ピン留めした commit の実ファイルと突き合わせて検証**する。
snippet が一致しない・行が存在しないエントリが 1 件でもあれば **exit 1**。

これは飾りではなく、この種の解析の主要な失敗モード（**読んだつもりで、それらしい要約を書く**）を
機械的に潰すためのもの。台帳に書けない主張は、この repo では主張しない。

## 使い方

```sh
make fetch    # ピン留めした commit で解析対象を vendor/ へ取得（vendor/ は git 管理外）
make verify   # 台帳の evidence を実ファイルと照合
make ci       # fetch + verify
```

## ディレクトリ

```
analysis/factors.yaml   根拠台帳（本体）
analysis/README.md      台帳の書き方・スキーマ・判定基準
scripts/                取得と検証
docs/ARCHITECTURE.md    解析対象パイプラインの地図
docs/adr/               設計判断
SOURCE.md               解析対象のピン留め（URL / commit / ライセンス）
vendor/                 解析対象の clone（git 管理外）
```

## ライセンス

本リポジトリのコード・文書は解析成果物。解析対象 `xai-org/x-algorithm` は Apache-2.0。
引用は出典（ファイル:行）を必ず添える。
