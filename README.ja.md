# jujutsu-summarize-hook

このリポジトリはClaude Codeと連携するJujutsu（jj）用のフックとAI機能を提供します。

## 機能

- **自動新規コミット作成**: `jj new`を使用してファイル編集前に新しいコミットを自動作成
- **自動コミット**: ファイル編集後にAIが生成したサマリーで自動コミット
- **コミット履歴整理**: jj-commit-organizer サブエージェントによる自動コミット整理
- **Slash Command**: `/jj-commit-organizer` コマンドで簡単アクセス
- **GitHub Copilot連携**: OAuth認証による組み込みGitHub Copilotサポート
- **日本語対応**: 日本語でのコミットメッセージとコミット名生成
- **複数LLMプロバイダー対応**: OpenAI、Anthropic、GitHub Copilot、ローカルモデル等をサポート

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

#### GitHub Copilot（推奨）

GitHub CopilotはAPIキーの管理が不要で、既存のGitHubアカウントを通じたシームレスな認証が可能なため推奨です。

```bash
# GitHub Copilotをモデルに設定
export JJ_HOOK_MODEL="github_copilot/gpt-4"

# GitHub Copilotで認証（ブラウザでOAuth認証）
jj-hook auth github-copilot

# 認証状態を確認
jj-hook auth --check
```

認証プロセスの流れ:
1. デフォルトブラウザでGitHub OAuthページが開きます
2. アプリケーションの認証を許可します
3. 認証トークンが安全に保存され、今後の使用に利用されます

#### その他のプロバイダー

環境変数でAPIキーを設定:

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"
export JJ_HOOK_MODEL="gpt-4"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"
export JJ_HOOK_MODEL="claude-3-sonnet-20240229"

# 言語設定（オプション）
export JJ_HOOK_LANGUAGE="japanese"
```

## 使い方

### フックが自動実行されるタイミング

1. **ファイル編集前**: Edit、Write、MultiEditツール使用前に新しいリビジョンを自動作成
2. **ファイル編集後**: Edit、Write、MultiEditツール使用後に自動コミット

### ワークフロー例

```bash
# Claude Codeでファイルを編集
# → 編集前: 新しいリビジョンを自動作成 (jj new -m "ファイル名を修正")
# → 編集後: AIが生成したメッセージで自動コミット
```

## 設定

### 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `JJ_HOOK_MODEL` | `gpt-3.5-turbo` | 使用するLLMモデル |
| `JJ_HOOK_LANGUAGE` | `english` | プロンプト言語 |
| `JJ_HOOK_MAX_TOKENS` | `100` | 最大トークン数 |
| `JJ_HOOK_TEMPERATURE` | `0.1` | 生成温度 |

### サポートされるLLMプロバイダー

- **GitHub Copilot** (github_copilot/gpt-4) - 推奨
- OpenAI (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic (claude-3-sonnet, claude-3-haiku, etc.)
- ローカルモデル (Ollama等)
- その他LiteLLMでサポートされる全プロバイダー

## CLIコマンド

### 認証

```bash
# GitHub Copilotで認証
jj-hook auth github-copilot

# 認証状態を確認
jj-hook auth --check
```

### インストール

```bash
# 現在のディレクトリにフックをインストール
jj-hook install

# 指定したディレクトリにインストール
jj-hook install --path /path/to/project

# グローバルにインストール
jj-hook install --global

# インストール内容をプレビュー（実際にはインストールしない）
jj-hook install --dry-run
```

### コミット履歴の整理

`organize` コマンドは jj-commit-organizer サブエージェントを使用してコミット履歴を分析・整理します：

```bash
# コミット履歴を分析・整理
jj-hook organize

# 変更を加えずにプレビュー
jj-hook organize --dry-run

# 確認なしに自動整理
jj-hook organize --auto

# 最新N個のコミットに分析を限定
jj-hook organize --limit 20
```

このコマンドの機能：
1. `jj log` を使用してコミット履歴を分析
2. 安全性チェックを実行
3. バックアップブックマークを作成
4. jj-commit-organizer サブエージェント用のプロンプトを生成
5. サブエージェントを使用してコミットを整理する手順を提供

jj-commit-organizer サブエージェントの機能：
- `jj squash --from <source> --into <target> -u` を使用して論理的に関連するコミットを統合
- `-m` オプションで適切なコミットメッセージを提案
- 機能ブランチ用のブックマークを作成
- 統合先メッセージを保持しながら順次コミット統合を実行

### フック手動実行

```bash
# post-tool-useフックを手動実行
jj-hook post-tool-use

# pre-tool-useフックを手動実行
jj-hook pre-tool-use
```

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
    ├── pre_tool_use.py      # ファイル編集前フック（リビジョン作成）
    └── post_tool_use.py     # ファイル編集後フック（自動コミット）
```

## フック詳細

### PreToolUse フック (pre_tool_use.py)
- **トリガー**: Edit、Write、MultiEditツール実行前
- **機能**: `jj new`を使用して新しいリビジョンを自動作成
- **動作**:
  - 一時ファイルや設定ファイルはスキップ
  - ワークスペースがクリーンな状態でのみ新しいリビジョンを作成
  - ファイルパスと予定される変更内容に基づいてリビジョン説明を生成
  - LiteLLMが利用可能な場合はAIを使用して意味のあるリビジョン名を作成

### PostToolUse フック (post_tool_use.py)
- **トリガー**: Edit、Write、MultiEditツール実行後
- **機能**: AIが生成したサマリーで変更を自動コミット
- **動作**:
  - `jj status`と`jj diff`の出力を分析して変更内容を理解
  - LiteLLMを使用して説明的なコミットメッセージを生成
  - AI生成に失敗した場合はシンプルなコミットメッセージにフォールバック
  - 実際の変更が検出された場合のみコミット


