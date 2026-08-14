# 解析対象のピン留め

| 項目 | 値 |
|---|---|
| リポジトリ | https://github.com/xai-org/x-algorithm |
| commit | `a389166f6cf5da70a286b568c87695d4dcdce3a1` |
| commit 日時 | 2026-08-13 17:23:56 +0000 |
| commit 件名 | Open-source X Recommendation Algorithm |
| ライセンス | Apache-2.0 |
| 取得日 | 2026-08-14 |
| 規模 | 2,015 files / 約 23 MB（scala 556 / rs 442 / py 406 / java 313） |

## ピン留めの意味

台帳 `analysis/factors.yaml` の `path:line:snippet` は**この commit に対してのみ**有効。
上流が更新されたら、SHA を上げる PR で `make verify` を通し、壊れた evidence を洗い出してから
台帳を追従させる。SHA と台帳は常に同じ commit で動かす。

## 取得

```sh
make fetch
```

`vendor/x-algorithm` へ `--depth 1` の固定 SHA fetch を行う（`.gitignore` 済み）。
