# ARCHITECTURE

## このリポジトリの構造

```
source.lock            解析対象の commit（機械可読な唯一の正）
  │
  ├─ scripts/fetch-source.zsh   → vendor/x-algorithm を pinned SHA で取得（git 管理外）
  │
analysis/factors.yaml     根拠台帳①: 投稿者が操作可能なランキング要因
analysis/code.yaml        根拠台帳②: コードそのもの（設計・実装技法）
analysis/components.yaml  根拠台帳③: パイプライン構成要素のカタログ
  │
  └─ scripts/verify-evidence.py → 全台帳の path:line:snippet を vendor の実ファイルと照合
                                  1 件でも不一致なら exit 1
```

### 台帳から解説ページへ

```
analysis/*.yaml  →  site/build.py  →  site/dist/*.html          （公開用フラグメント）
                         ↑        →  site/dist/preview/*.html   （ローカル閲覧用）
                  site/links.json（公開先 URL）
```

公開先が `<!doctype>` / `<head>` を付ける仕様なので、`dist/*.html` は骨組みを持たない。
そのまま `file://` で開くと charset 未宣言で日本語が化けるため、
閲覧用に charset 付きの完全な文書を `dist/preview/` にも出す。

ページに出る件数・部品名・役割は**すべて台帳から導出する**。手で書いた数字を混ぜると、
台帳を更新しても直らない箇所ができる。`site/dist/` は生成物なのでコミットしない。

`links.json` に無いキーが参照されたら生成を**中断する**（リンク切れのページを黙って出さないため）。

3 本の台帳はスキーマが違う（`factors.yaml` は `stage`/`author_controllable`/`direction`、
`code.yaml` は `topic`/`takeaway`、`components.yaml` は `kind`/`order`/`controlled_by`）が、
**evidence の照合は同じ関数 1 つ**（`check_evidence`）を通る。
台帳を足すときは `LEDGERS` に `LedgerSpec` を 1 つ加えるだけで、検証の厳しさは自動的に揃う。

3 本目を足したときの実測差分は `LEDGERS` への 1 エントリと enum 定義で **+25 行**、
`check_evidence` は無変更（ADR 0002 の設計どおり）。

`make ci` = `fetch` → `verify`。CI ゲートはこの 1 本。

**どこを触れば何が変わるか**

| 変えたいもの | 触る場所 |
|---|---|
| 解析対象の commit を上げる | `source.lock` の `COMMIT` と `analysis/factors.yaml` の `source_ref`（両方。片方だけだと verify が落ちる）と `SOURCE.md` |
| 要因を追加する | `analysis/factors.yaml` に 1 エントリ追加 → `make verify` |
| 台帳のスキーマを変える | `scripts/verify-evidence.py` の定数（`STAGES` 等）と `analysis/README.md` |

## 解析対象のパイプライン地図

`home-mixer`（Rust）が For You / Following フィードの合成本体。段階は次の順に並ぶ。

```
sources          候補の供給元（phoenix / simclusters / reverse_chron / popular_topics ...）
   ↓
hydrators        候補にメタデータを付ける（query_hydrators / candidate_hydrators）
   ↓
filters          候補を落とす（0/1 の足切り）
   ↓
scorers          スコアを付ける（ranking_scorer が重み付き和、phoenix が学習モデル）
   ↓
selectors        並べて切り出す（blender / top_k_score）
```

台帳の `stage` はこの段階名に対応する。

**主要ディレクトリ**（解析対象ルートからの相対）

| パス | 役割 |
|---|---|
| `home-mixer/sources/` | 候補ソース。フォロー内/外、話題、キャッシュ等 |
| `home-mixer/filters/` | 足切り。フォロー外 RT/リプライ除外、経過時間、重複排除、ミュートキーワード等 |
| `home-mixer/scorers/` | スコアリング。`ranking_scorer.rs` が重み付き和の本体 |
| `home-mixer/params/param.rs` | 重み等のパラメータ定義と**既定値** |
| `home-mixer/selectors/` | 最終的な並べ替えと切り出し |
| `home-mixer/candidate_pipeline/` | 上記の配線（どのフィードがどの段を通るか） |
| `visibility-filtering/` | 可視性フィルタ（安全性ラベルによる出し分け） |
| `phoenix/` | 学習モデル側のランカー |
| `under-the-hood/` | アカウント/投稿の扱いを可視化する仕組み |

## 意図的に持っていないもの

- 解析対象のビルド・実行環境。**コードを読むだけ**で、動かさない
- スコアの再現実装。既定値からスコアを計算しても本番の順位にはならない（`analysis/README.md` 参照）
