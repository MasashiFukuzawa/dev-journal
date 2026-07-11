---
name: dev-journal
description: >-
  GitHub Issue の完了履歴を収集・解析し、開発日誌を Web UI で閲覧・検索する。「最近何を開発したか振り返りたい」「完了 Issue の判断経緯を確認したい」ときに使う。一般的な GitHub Issue 操作や TODO 管理には使わない。
---

# Dev Journal

GitHub の完了 Issue を SQLite に保存し、Claude CLI が背景・決定・制約・今後の課題を整理する。設定や DB の内容を応答へ転載する前に、秘密情報を含まないことを確認する。

## 前提

- `gh` が認証済みであること
- `claude` CLI が利用できること
- `uv` が利用できること
- `${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal/config.yml` が存在すること
- `DEV_JOURNAL_HOME` が clone した runtime を指すか、`dev-journal` が `PATH` 上にあること

設定ファイルは次の優先順位で解決する。

1. CLI の `--config`
2. `DEV_JOURNAL_CONFIG`
3. `${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal/config.yml`

## 操作

安定 CLI から実行する。Skill plugin と runtime clone は別配布である。

```bash
dev-journal collect fetch-pending
dev-journal collect save --file /path/to/processed.json
dev-journal prune
dev-journal serve
```

通常は `run_collect_cycle()` が取得、Claude CLI による解析、保存、カテゴリ分類、古い記録の削除まで行う。外部公開が必要なら、既定の `127.0.0.1` を変更する前に認証、`allowed_hosts`、ネットワーク境界を確認する。

## データ配置

- 設定: `${XDG_CONFIG_HOME:-$HOME/.config}/dev-journal/config.yml`
- DB: `${XDG_DATA_HOME:-$HOME/.local/share}/dev-journal/journal.db`
- ログ・ロック: `${XDG_STATE_HOME:-$HOME/.local/state}/dev-journal/`

テストや検証では XDG 変数を一時ディレクトリへ向け、既存 DB を開かない。
