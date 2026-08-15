# 台帳の書き方

## 3 本の台帳

| ファイル | 対象 | 問い |
|---|---|---|
| `factors.yaml` | 投稿者が操作可能なランキング要因 | この投稿はどう扱われるか |
| `code.yaml` | コードそのもの（設計・実装技法） | この実装はどう作られているか |
| `components.yaml` | パイプラインの構成要素カタログ | 何がどの順で並んでいるか |

観点は独立している。`code.yaml` に「投稿者が操作できるか」を書かないし、
`factors.yaml` に「この trait 設計が良い」を書かない。混ぜると両方が薄まる。

`components.yaml` は**配線の目録**であって、レバーの説明ではない。
「フォロー外の RT が落ちる」ことの意味は `factors.yaml`（F005）にあり、
カタログ側は「その処理が 5 番目に並んでいる」ことを持つ。

**evidence の照合ロジックは両者で共通**（`verify-evidence.py` の `check_evidence` 1 箇所）。
片方だけ緩い検証にすると、台帳全体の信頼度が読み手から見て不明になる。

## 原則

**台帳に書けない主張は、この repo では主張しない。**

「コードを読んだ結果こう思う」は解析ではなく感想。1 エントリにつき最低 1 件、
`path` / `line` / `snippet` で固定した evidence を持たせる。`make verify` がこれを機械照合する。

grep がヒットしただけ・ファイル名から推測しただけの段階では台帳に載せない。
**開いて読み、その行の実文字列を snippet に書き写した**ものだけが載る。

## スキーマ

```yaml
source_ref: <解析対象の commit SHA。source.lock と一致必須>
factors:
  - id: F001                      # F + 3 桁。重複不可
    name: <短い名前>
    stage: source|hydrator|filter|scorer|selector|visibility|infra
    author_controllable: direct|indirect|none
    direction: boost|suppress|gate|neutral
    summary: <何が起きるか。数値は evidence で裏を取れる範囲だけ書く>
    evidence:
      - path: home-mixer/params/param.rs   # 解析対象ルートからの相対パス
        line: 282                          # 開始行（1 始まり）
        line_end: 289                      # 省略時は line と同じ
        snippet: 'param!(FavoriteWeight'   # line〜line_end のどこかに実在する文字列
    confidence: high|medium|low
    notes: <未確認事項・断定を避ける理由。任意>
```

## 各フィールドの判定基準

### `author_controllable`

投稿者が**投稿の作り方で動かせるか**。閲覧者側の設定や X 社の運用でしか動かないものは `no`。

| 値 | 意味 | 例 |
|---|---|---|
| `direct` | 投稿の形式・内容・投稿先の選択で直接動く | 単独ポストにするか返信にするか |
| `indirect` | 動かせるが、間接的または他要因に強く従属する | エンゲージメント重み（集められるとは限らない） |
| `none` | 投稿者からは動かせない | 閲覧者のミュートキーワード設定 |

`yes` / `no` を値に使わないのは、YAML 1.1 がこの 2 語を真偽値に解釈して
文字列比較を静かに壊すため（実際に踏んだ）。

**`none` を載せてよいのは「他の要因を読むために必要な文脈」だけ。**
たとえば「最終的に何枠あるか」「上位何件まで残るか」は投稿者から動かせないが、
これが分からないと他の要因が何を争っているのかを読めない（F009〜F012）。
単に投稿者が動かせないだけの処理は、載せずに調査 issue に置く。

### `direction`

- `boost` — スコアを押し上げる
- `suppress` — スコアを押し下げる
- `gate` — スコア以前に候補集合から出し入れする（0/1 の足切り）
- `neutral` — 構造の説明であって方向を持たない

`gate` と `boost` は混同しない。足切りは重みで補償できない。

### `confidence`

- `high` — コードに直接書いてあり、解釈の余地が小さい
- `medium` — コードは読めているが、本番での有効性や適用条件に不確実性がある
- `low` — 断片的な根拠しかない。原則ここに置くくらいなら調査タスクにする

## components.yaml のスキーマ

```yaml
components:
  - id: P001                    # P + 3 桁
    kind: filter                # source|hydrator|filter|scorer|selector
    name: AgeFilter             # コード上の型名そのまま
    order: 3                    # その kind の中での配線順（1 始まり）
    role: <何をするか。判定条件を含む 1〜2 文>
    controlled_by: author       # author|viewer|system
    author_note: <投稿者から見た意味。任意>
    evidence: [...]             # factors / code と同じ形式・同じ検証
    confidence: high
```

### `controlled_by` の判定

| 値 | 意味 | 例 |
|---|---|---|
| `author` | 投稿の作り方・内容で結果が変わる | 経過時間、投稿の形式 |
| `viewer` | 閲覧者の設定・履歴で決まる | ミュートキーワード、既読 |
| `system` | 運用・実験・データ整合のため | 重複排除、ホールドアウト |

`factors.yaml` の `author_controllable` とは別物。あちらは「レバーになるか」、
こちらは「誰の都合でその処理が効くか」を見る。

## 書いてはいけないこと

- **本番挙動の断定** — 公開されているのは既定値であって本番の feature switch 値ではない。
  「既定値では〜」と必ず限定する。
- **効果量の予測** — 「この重みだから X 倍伸びる」はコードから導けない。
  重みの比はスコア式の比であって、インプレッションの比ではない。
- **未確認の因果** — 「除外される」と「表示されない」は違う。パイプラインのどこで
  実際に配線されているかを確認していないなら `notes` にその旨を書く。

## 未確認事項の扱い

追い切れていない点は `notes` に残し、`F9xx` 番号で調査タスクとして issue 化する。
台帳から消して「無かったこと」にしない。
