# ADR 索引

<!-- generate-adr-index.zsh による自動生成。手で編集しない -->

| ADR | タイトル | status | date | 要旨 |
|---|---|---|---|---|
| [0001](0001-evidence-ledger-with-pinned-source.md) | 解析成果は散文ではなく機械検証可能な根拠台帳に置き、解析対象を commit でピン留めする | accepted | 2026-08-14 | 解析結果を factors.yaml の path:line:snippet に固定し、pinned commit の実ファイルと機械照合することで「読んだつもりの要約」を構造的に排除する。 |
| [0002](0002-two-ledgers-one-evidence-check.md) | 台帳は観点ごとに分けるが、evidence の照合ロジックは 1 つに保つ | accepted | 2026-08-14 | ランキング要因とコード自体の観察はスキーマを分けて別台帳にし、evidence 照合だけは共通の関数を通すことで検証の厳しさを揃える。 |
