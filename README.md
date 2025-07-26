# jujutsu-summarize-hook

このリポジトリはClaude Codeと連携するJujutsu（jj）用のフックとAI機能を提供します。

## 機能

- **自動コミット**: ファイル編集後にAIが生成したサマリーで自動コミット
- **自動ブランチ作成**: ユーザープロンプトから新しいブランチを自動作成
- **日本語対応**: 日本語でのコミットメッセージとブランチ名生成
- **複数LLMプロバイダー対応**: OpenAI、Anthropic、ローカルモデル等をサポート

## 必要条件

- Python 3.9以上
- [Jujutsu (jj)](https://github.com/martinvonz/jj) 
- [Claude Code](https://claude.ai/code)
- [mise](https://mise.jdx.dev/) (推奨)
- [uv](https://docs.astral.sh/uv/) (推奨)

## インストール

### 1. プロジェクトのセットアップ

```bash
# 開発環境のセットアップ
mise install
uv sync

# パッケージのインストール
uv pip install -e .
```

### 2. Claude Codeフックの設定

プロジェクトディレクトリにフックをインストール:

```bash
jj-hook install --path .
```

現在のディレクトリにインストール:

```bash
jj-hook install
```

### 3. LLMプロバイダーの設定

環境変数でAPIキーを設定:

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# 使用するモデルの指定（オプション）
export JJ_HOOK_MODEL="gpt-4"
export JJ_HOOK_LANGUAGE="japanese"
```

## 使い方

### フックが自動実行されるタイミング

1. **ファイル編集後**: Edit、Write、MultiEditツール使用後に自動コミット
2. **プロンプト送信時**: 作業系プロンプトで新しいブランチを自動作成

### ワークフロー例

```bash
# Claude Codeでプロンプトを送信
"ユーザー認証機能を追加して"
# → 自動的に新しいブランチが作成される

# Claude Codeでファイルを編集
# → 編集完了後、AIが生成したメッセージで自動コミット
```

## 設定

### 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `JJ_HOOK_MODEL` | `gpt-3.5-turbo` | 使用するLLMモデル |
| `JJ_HOOK_LANGUAGE` | `japanese` | プロンプト言語 |
| `JJ_HOOK_MAX_TOKENS` | `100` | 最大トークン数 |
| `JJ_HOOK_TEMPERATURE` | `0.1` | 生成温度 |

### サポートされるLLMプロバイダー

- OpenAI (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic (claude-3-sonnet, claude-3-haiku, etc.)
- ローカルモデル (Ollama等)
- その他LiteLLMでサポートされる全プロバイダー

## 開発

### 開発環境のセットアップ

```bash
# 依存関係のインストール
mise install
uv sync --dev

# コードフォーマット
uv run ruff format .

# 型チェック
uv run mypy src/

# テスト実行
uv run pytest
```

### プロジェクト構造

```
src/jj_hook/
├── __init__.py
├── cli.py              # CLIエントリーポイント
├── summarizer.py       # AI機能
├── config.py          # 設定管理
└── hooks/
    ├── __init__.py
    ├── post_tool_use.py     # ファイル編集後フック
    └── user_prompt_submit.py # プロンプト送信時フック
```


