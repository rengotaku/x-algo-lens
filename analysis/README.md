# 台帳の書き方

## 原則

**台帳に書けない主張は、この repo では主張しない。**

「コードを読んだ結果こう思う」は解析ではなく感想。1 要因につき最低 1 件、
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
