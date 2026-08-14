.DEFAULT_GOAL := help
SHELL := /bin/zsh

VENDOR_DIR := vendor/x-algorithm

.PHONY: help
help: ## ターゲット一覧
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: fetch
fetch: ## 解析対象をピン留め commit で vendor/ へ取得
	@scripts/fetch-source.zsh

.PHONY: verify
verify: ## 台帳の evidence を実ファイルと照合（不一致があれば exit 1）
	@python3 scripts/verify-evidence.py

.PHONY: stats
stats: ## 台帳の集計（要因数・操作可能性の内訳）
	@python3 scripts/verify-evidence.py --stats

.PHONY: ci
ci: fetch verify ## CI 相当（取得 → 検証）

.PHONY: clean
clean: ## vendor/ を削除
	@rm -rf vendor
	@echo "removed vendor/"
