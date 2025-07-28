# vcs-cc-hook

このリポジトリはClaude Codeと連携するJujutsu（jj）とGit両方に対応したAI機能付きフックを提供し、自動検出とVCS固有最適化を行います。

## 機能

- **マルチVCS対応**: JujutsuとGitリポジトリの自動検出とサポート
- **自動新規ブランチ/リビジョン作成**: ファイル編集前に新しいブランチ（Git）またはリビジョン（Jujutsu）を自動作成
- **自動コミット**: ファイル編集後にAIが生成したサマリーで自動コミット
- **AIによるコミット履歴整理**: `vcs-cc-hook organize`を使用したコミット履歴の分析と整理
- **サブエージェント統合**: VCS固有サブエージェント（jj-commit-organizer、git-commit-organizer、vcs-commit-organizer）によるインテリジェントなコミット管理
- **Slash Command対応**: VCS固有および汎用コミット整理用の複数スラッシュコマンド
- **テンプレートシステム**: 様々な言語とシナリオ用のカスタマイズ可能なプロンプトテンプレート
- **GitHub Copilot連携**: OAuth認証による組み込みGitHub Copilotサポート
- **多言語対応**: 英語と日本語でのコミットメッセージとブランチ名生成
- **複数LLMプロバイダー対応**: OpenAI、Anthropic、GitHub Copilot、ローカルモデル等をサポート
- **一括インストール**: 全コンポーネント（フック、サブエージェント、スラッシュコマンド）の一括インストール
- **3つのコマンドオプション**: VCS固有（`jj-cc-hook`、`git-cc-hook`）および汎用（`vcs-cc-hook`）コマンド

## 必要条件

- Python 3.9以上
- [uv](https://docs.astral.sh/uv/)
- [Jujutsu (jj)](https://github.com/martinvonz/jj) または [Git](https://git-scm.com/)
- [Claude Code](https://claude.ai/code)
- [mise](https://mise.jdx.dev/) (推奨)

## クイックスタート

### 1. リポジトリのクローン

```bash
git clone https://github.com/anosatsuk124/jujutsu-summarize-hook.git
```

### 2. インストール

```bash
cd jujutsu-summarize-hook
uv tool install .
```

### 3. 好きな場所でhooks/agentsのインストール（ローカルディレクトリ）

```bash
jj-hook install-all
```

## インストール (開発者向け)

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

#### 全機能を一括インストール

```bash
# hooks + sub-agent + slash command を一括インストール
jj-hook install-all

# プレビューモードで確認
jj-hook install-all --dry-run

# グローバルにインストール
jj-hook install-all --global
```

#### 個別インストール

```bash
# Sub-agent のみインストール
jj-hook install-agent

# Slash command のみインストール  
jj-hook install-slash-command
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

#### 基本ファイル編集ワークフロー

```bash
# Claude Codeでファイルを編集
# → 編集前: 新しいコミットを自動作成（`jj new`）
# → 編集後: AIが生成したメッセージで自動コミット
```

#### コミット履歴整理ワークフロー

```bash
# コミット履歴の分析と整理
jj-hook organize

# 出力例:
# 🔍 10コミットを分析中...
# ✅ 3つの整理機会を発見:
#   1. "fix typo"を"Add new feature"に統合 (信頼度: 0.9)
#   2. "remove debug"を"Add logging"に統合 (信頼度: 0.8)
#   3. コミット 5-7 用の機能ブランチを作成 (信頼度: 0.7)
```

#### サブエージェント統合ワークフロー

```bash
# サブエージェントのインストール
jj-hook install-agent --global

# Claude Codeで使用:
# "jj-commit-organizer サブエージェントを使ってコミット履歴を整理して"
# → サブエージェントがコミット履歴を分析
# → 整理推奨を提供
# → 承認された変更を実行
```

#### Slash Commandワークフロー

```bash
# スラッシュコマンドのインストール
jj-hook install-slash-command --global

# Claude Codeで使用:
# 入力: /jj-commit-organizer
# → 自動でサブエージェントを呼び出し
# → コミット履歴を分析・整理
# → 変更前のバックアップを作成
```

## 設定

### 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `JJ_HOOK_MODEL` | `gpt-3.5-turbo` | 使用するLLMモデル |
| `JJ_HOOK_LANGUAGE` | `english` | プロンプト言語 (`english` または `japanese`) |
| `JJ_HOOK_MAX_TOKENS` | `100` | AI応答の最大トークン数 |
| `JJ_HOOK_TEMPERATURE` | `0.1` | 生成温度 (0.0-1.0) |

### テンプレートシステム

テンプレートシステムは、様々なシナリオ向けにAIプロンプトのカスタマイズを可能にします：

- **テンプレートディレクトリ**: `src/jj_hook/templates/`
- **言語サポート**: テンプレートは`JJ_HOOK_LANGUAGE`で指定された言語を自動使用
- **テンプレート変数**: Pythonの`str.format()`構文を使用した変数置換をサポート

#### 利用可能なテンプレート

| テンプレート | 目的 | 変数 |
|----------|------|--------|
| `commit_message.md` | コミットメッセージ生成 | `changes`, `language` |
| `branch_name.md` | ブランチ名生成 | `prompt`, `language` |
| `commit_analysis.md` | コミット履歴分析 | `commits`, `language` |
| `revision_description.md` | リビジョン説明生成 | `file_path`, `content`, `language` |
| `agent_content.md` | サブエージェント定義 | `language` |

### サポートされるLLMプロバイダー

- **GitHub Copilot** (github_copilot/gpt-4) - 推奨
- OpenAI (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic (claude-3-sonnet, claude-3-haiku, etc.)
- ローカルモデル (Ollama等)
- その他LiteLLMでサポートされる全プロバイダー

## CLIコマンド

### 要約 (AIによるコミット)

```bash
# コミットされていない変更をAIで要約してコミット
jj-hook summarize

# 特定のパスからの変更を要約（例: サブディレクトリ）
jj-hook summarize --path ./src/my_module
```

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

# サブエージェントをグローバルにインストール
jj-hook install-agent --global

# サブエージェントを特定ディレクトリにインストール
jj-hook install-agent --path /path/to/project

# スラッシュコマンドをグローバルにインストール
jj-hook install-slash-command --global

# スラッシュコマンドを特定ディレクトリにインストール
jj-hook install-slash-command --path /path/to/project

# 全コンポーネントを一括インストール
jj-hook install-all --global

# 変更を加えずにインストールをプレビュー
jj-hook install-all --dry-run
```

### コミット履歴の整理

#### Slash Commandを使用（推奨）
Claude Codeで一番簡単にコミット整理を行う方法：

```bash
# Claude Codeで以下を入力
/jj-commit-organizer
```

#### サブエージェントを直接指定
```bash
# Claude Codeで以下のように指示
jj-commit-organizer サブエージェントを使ってコミット履歴を整理して
```

#### CLIコマンドで直接実行
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

# コミットサイズ分類の閾値を設定
jj-hook organize --tiny-threshold 5 --small-threshold 20

# アグレッシブモード（低信頼度推奨も含む）
jj-hook organize --aggressive

# パターンにマッチするコミットを除外
jj-hook organize --exclude-pattern "WIP" --exclude-pattern "temp"
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

### 新しいCLIコマンドオプション

このプロジェクトは3つのコマンドオプションを提供します：

#### VCS固有コマンド

```bash
# Jujutsu用
jj-cc-hook install-all
jj-cc-hook organize
jj-cc-hook summarize

# Git用  
git-cc-hook install-all
git-cc-hook organize
git-cc-hook summarize
```

#### 汎用コマンド

```bash
# VCS自動検出版
vcs-cc-hook install-all
vcs-cc-hook organize
vcs-cc-hook summarize
```

現在は既存の`jj-hook`コマンドと互換性を保ちつつ、より柔軟なマルチVCSサポートを提供しています。

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


## License

```
   Copyright 2025 Satsuki Akiba <anosatsuk124@gmail.com>

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
