#!/usr/bin/env python3
"""jj-hook CLI implementation."""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

import click
import litellm
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from rich.prompt import Confirm

console = Console()


def check_github_copilot_auth() -> tuple[bool, str]:
    """GitHub Copilot認証状態をチェックする。"""
    try:
        import litellm
        from jj_hook.summarizer import JujutsuSummarizer
        
        # 軽量なテストリクエストで認証状態を確認
        summarizer = JujutsuSummarizer()
        if not summarizer.config.model.startswith("github_copilot/"):
            return False, "GitHub Copilotモデルが設定されていません"
        
        # 短いテストリクエスト
        response = litellm.completion(
            model=summarizer.config.model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1,
            temperature=0.1,
            extra_headers={
                "editor-version": "vscode/1.85.1",
                "Copilot-Integration-Id": "vscode-chat"
            }
        )
        return True, "認証済み"
        
    except ImportError:
        return False, "litellmパッケージがインストールされていません"
    except Exception as e:
        error_msg = str(e)
        if "authenticate" in error_msg.lower() or "oauth" in error_msg.lower():
            return False, "認証が必要です"
        elif "subscription" in error_msg.lower():
            return False, "GitHub Copilotサブスクリプションが必要です"
        else:
            return False, f"認証エラー: {error_msg}"


def authenticate_github_copilot() -> bool:
    """GitHub Copilot OAuth認証を実行する。"""
    try:
        import litellm
        from jj_hook.summarizer import JujutsuSummarizer
        
        console.print("\n[blue]GitHub Copilot認証を開始します...[/blue]")
        
        summarizer = JujutsuSummarizer()
        if not summarizer.config.model.startswith("github_copilot/"):
            console.print("[yellow]警告: JJ_HOOK_MODELがGitHub Copilotモデルに設定されていません[/yellow]")
            console.print(f"現在の設定: {summarizer.config.model}")
            if not Confirm.ask("GitHub Copilot認証を続行しますか？"):
                return False
        
        console.print("[cyan]認証リクエストを送信中...[/cyan]")
        
        # 認証フローを開始するためのリクエスト
        response = litellm.completion(
            model="github_copilot/gpt-4",
            messages=[{"role": "user", "content": "Hello, this is a test for authentication."}],
            max_tokens=10,
            temperature=0.1,
            extra_headers={
                "editor-version": "vscode/1.85.1",
                "Copilot-Integration-Id": "vscode-chat"
            }
        )
        
        console.print("[green]✅ GitHub Copilot認証が完了しました！[/green]")
        console.print(f"[dim]レスポンス: {response.choices[0].message.content[:50]}...[/dim]")
        return True
        
    except ImportError:
        console.print("[red]❌ エラー: litellmパッケージがインストールされていません[/red]")
        return False
    except Exception as e:
        error_msg = str(e)
        if "Please visit" in error_msg and "enter code" in error_msg:
            console.print("[yellow]認証フローが開始されました。上記の指示に従って認証を完了してください。[/yellow]")
            
            if Confirm.ask("認証を完了しましたか？"):
                # 認証完了後の再試行
                try:
                    response = litellm.completion(
                        model="github_copilot/gpt-4",
                        messages=[{"role": "user", "content": "Test after auth"}],
                        max_tokens=5,
                        temperature=0.1,
                        extra_headers={
                            "editor-version": "vscode/1.85.1", 
                            "Copilot-Integration-Id": "vscode-chat"
                        }
                    )
                    console.print("[green]✅ 認証が正常に完了しました！[/green]")
                    return True
                except Exception as retry_error:
                    console.print(f"[red]❌ 認証後のテストに失敗: {retry_error}[/red]")
                    return False
            else:
                console.print("[yellow]認証をキャンセルしました[/yellow]")
                return False
        else:
            console.print(f"[red]❌ 認証エラー: {error_msg}[/red]")
            return False


def get_project_root() -> Path:
    """プロジェクトのルートディレクトリを取得する。"""
    # パッケージのhooksディレクトリのパスを取得
    hooks_dir = Path(__file__).parent / "hooks"
    return hooks_dir


def create_claude_settings_dir(target_path: Path) -> Path:
    """Claude設定ディレクトリを作成し、パスを返す。"""
    claude_dir = target_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    return claude_dir


def get_existing_settings(settings_file: Path) -> dict:
    """既存の設定ファイルを読み込む。存在しない場合は空の辞書を返す。"""
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[yellow]警告: 既存の設定ファイルの読み込みに失敗しました: {e}[/yellow]")
            return {}
    return {}


def create_hook_settings() -> dict:
    """フック設定を生成する。"""
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "jj-hook post-tool-use",
                            "timeout": 30
                        }
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {
                            "type": "command", 
                            "command": "jj-hook pre-tool-use",
                            "timeout": 15
                        }
                    ]
                }
            ]
        }
    }
    
    return settings


def merge_settings(existing: dict, new_settings: dict) -> dict:
    """既存の設定と新しい設定を安全にマージする。"""
    import copy
    
    merged = copy.deepcopy(existing)
    
    if "hooks" not in merged:
        merged["hooks"] = {}
    
    # 新しいフック設定をマージ
    for event_name, hooks_list in new_settings["hooks"].items():
        if event_name not in merged["hooks"]:
            merged["hooks"][event_name] = []
        
        # 既存のjj-hookフックを削除（重複回避）
        merged["hooks"][event_name] = [
            hook for hook in merged["hooks"][event_name]
            if not any(
                "jj-hook" in cmd.get("command", "")
                for cmd in hook.get("hooks", [])
            )
        ]
        
        # 新しいフック設定を追加
        merged["hooks"][event_name].extend(hooks_list)
    
    return merged


def backup_settings_file(settings_file: Path) -> Optional[Path]:
    """設定ファイルのバックアップを作成する。"""
    if not settings_file.exists():
        return None
    
    backup_file = settings_file.with_suffix(".json.backup")
    try:
        import shutil
        shutil.copy2(settings_file, backup_file)
        return backup_file
    except OSError:
        return None


@click.group()
@click.version_option()
def cli() -> None:
    """Jujutsu hooks for Claude Code."""
    pass


@cli.command()
@click.option(
    "--global", "is_global",
    is_flag=True,
    help="グローバル設定（~/.claude/settings.json）にインストール"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="実際の変更は行わず、変更内容のプレビューのみ表示"
)
@click.option(
    "--path", 
    "-p", 
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）"
)
def install(is_global: bool, dry_run: bool, path: Optional[Path]) -> None:
    """jj-hookをClaude Code設定に追加する。"""
    
    # 設定ファイルパスの決定
    if is_global and path:
        console.print("[red]エラー: --globalと--pathは同時に指定できません[/red]")
        sys.exit(1)
    
    if is_global:
        settings_file = Path.home() / ".claude" / "settings.json"
        install_location = "グローバル設定"
    else:
        target_path = path if path is not None else Path.cwd()
        claude_dir = create_claude_settings_dir(target_path)
        settings_file = claude_dir / "settings.json"
        install_location = f"ローカル設定 ({target_path})"
    
    console.print(f"[blue]インストール先: {install_location}[/blue]")
    console.print(f"[dim]設定ファイル: {settings_file}[/dim]")
    
    try:
        # 既存設定の読み込み
        existing_settings = get_existing_settings(settings_file)
        
        # 新しいフック設定を生成
        hook_settings = create_hook_settings()
        
        # 設定をマージ
        merged_settings = merge_settings(existing_settings, hook_settings)
        
        if dry_run:
            # プレビューモード
            console.print("\n[yellow]変更プレビュー:[/yellow]")
            console.print(json.dumps(hook_settings, indent=2, ensure_ascii=False))
            console.print(f"\n[dim]実際に変更するには --dry-run オプションを外して実行してください[/dim]")
            return
        
        # バックアップ作成
        backup_file = backup_settings_file(settings_file)
        if backup_file:
            console.print(f"[dim]バックアップ作成: {backup_file}[/dim]")
        
        # 設定ファイルの親ディレクトリを作成（グローバル設定の場合）
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 設定ファイルの書き込み
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(merged_settings, f, indent=2, ensure_ascii=False)
        
        console.print(Panel(
            Text("jj-hook のインストールが完了しました！\n\n"
                 "有効になった機能:\n"
                 "• ファイル編集前の新ブランチ作成 (PreToolUse)\n"
                 "• ファイル編集後の自動コミット (PostToolUse)\n\n"
                 "コマンド:\n"
                 "• jj-hook post-tool-use\n"
                 "• jj-hook pre-tool-use", 
                 style="bold green"),
            title="🎉 インストール成功",
            border_style="green"
        ))
        
    except OSError as e:
        console.print(f"[red]エラー: ファイル操作に失敗しました: {e}[/red]")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]エラー: JSON処理に失敗しました: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]予期しないエラーが発生しました: {e}[/red]")
        sys.exit(1)


@cli.command(name="post-tool-use")
def post_tool_use() -> None:
    """PostToolUse フックを実行する。"""
    from .hooks.post_tool_use import main as post_tool_use_main
    
    try:
        post_tool_use_main()
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]PostToolUse フックでエラーが発生しました: {e}[/red]")
        sys.exit(2)


@cli.command(name="pre-tool-use")
def pre_tool_use() -> None:
    """PreToolUse フックを実行する。"""
    from .hooks.pre_tool_use import main as pre_tool_use_main
    
    try:
        pre_tool_use_main()
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]PreToolUse フックでエラーが発生しました: {e}[/red]")
        sys.exit(2)


@cli.command(name="install-agent")
@click.option(
    "--global", "is_global",
    is_flag=True,
    help="グローバル設定（~/.claude/agents/）にインストール"
)
@click.option(
    "--path", 
    "-p", 
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）"
)
def install_agent(is_global: bool, path: Optional[Path]) -> None:
    """jj-commit-organizerサブエージェントをClaude Code設定に追加する。"""
    
    # 言語設定の取得
    language = os.environ.get("JJ_HOOK_LANGUAGE", "english")
    
    # インストール先の決定
    if is_global and path:
        error_msg = "エラー: --globalと--pathは同時に指定できません" if language == "japanese" else "Error: --global and --path cannot be used together"
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)
    
    if is_global:
        agents_dir = Path.home() / ".claude" / "agents"
        install_location = "グローバル設定" if language == "japanese" else "Global settings"
    else:
        target_path = path if path is not None else Path.cwd()
        agents_dir = target_path / ".claude" / "agents"
        install_location = f"ローカル設定 ({target_path})" if language == "japanese" else f"Local settings ({target_path})"
    
    location_label = "インストール先" if language == "japanese" else "Install location"
    directory_label = "ディレクトリ" if language == "japanese" else "Directory"
    console.print(f"[blue]{location_label}: {install_location}[/blue]")
    console.print(f"[dim]{directory_label}: {agents_dir}[/dim]")
    
    try:
        # ディレクトリ作成
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # サブエージェント定義ファイルのパス
        agent_file = agents_dir / "jj-commit-organizer.md"
        
        # 既存ファイルの確認
        if agent_file.exists():
            exists_msg = f"ファイル {agent_file} が既に存在します。上書きしますか？" if language == "japanese" else f"File {agent_file} already exists. Overwrite?"
            cancel_msg = "インストールをキャンセルしました" if language == "japanese" else "Installation cancelled"
            if not Confirm.ask(f"[yellow]{exists_msg}[/yellow]"):
                console.print(f"[dim]{cancel_msg}[/dim]")
                return
        
        # サブエージェント定義の内容（言語別）
        if language == "japanese":
            agent_content = """---
name: jj-commit-organizer
description: jj log や jj diff を観察し、適切なコミット単位をjj squash や jj bookmark createなどを使って整形する専用エキスパート。コミット履歴の論理的整理とリファクタリングをプロアクティブに実行する。
tools: Bash, Read, Grep, Glob
---

あなたはJujutsu VCS（jj）の専門家で、コミット履歴の整理とリファクタリングを担当します。

## 役割と責任

### 主要機能
1. **コミット履歴の分析**: `jj log` でコミット履歴を確認し、問題を特定
2. **差分の詳細調査**: `jj diff` で各コミットの変更内容を分析
3. **論理的整理の提案**: 関連するコミットをまとめ、適切な単位に再編成
4. **自動整形の実行**: `jj squash` や `jj bookmark create` を使用した実際の整理

### 分析対象
- 同一ファイルへの連続した小さな修正
- 関連する機能の複数回に分かれたコミット
- 意味のないコミットメッセージ（"fix", "wip", "tmp"など）
- タイポ修正やフォーマット変更の分離されたコミット
- 論理的に一つの変更であるべき分散したコミット

### 整理方針
- **機能単位**: 一つの機能や修正は一つのコミットに
- **論理的一貫性**: 関連する変更は同じコミットに統合
- **明確なメッセージ**: 各コミットの目的が明確になるように
- **レビュー可能性**: 変更が理解しやすい適切なサイズに

## 実行手順

### 1. 現状分析
```bash
# コミット履歴の確認（最新20件）
jj log -r 'present(@)::heads(trunk)' --limit 20

# 未プッシュのコミット確認
jj log -r '@::heads(trunk) & ~heads(main)'
```

### 2. 差分詳細調査
```bash
# 特定のコミットの変更内容
jj diff -r <commit-id>

# 複数コミット間の累積差分
jj diff -r <start>..<end>

# ファイル単位での変更履歴
jj log -p <file-path>
```

### 3. 整理実行
```bash
# 複数コミットをスカッシュ
jj squash -r <commit-range>

# コミットメッセージの編集
jj describe -r <commit-id> -m "新しいメッセージ"

# 新しいブックマークの作成
jj bookmark create <feature-name> -r <commit-id>
```

## 判断基準

### 統合すべきコミット
- 同一ファイルの連続修正
- タイポ修正とそのフィックス
- 機能追加とそのテスト
- ドキュメントと実装の対応関係
- デバッグ用コードの追加と削除

### 分離すべき変更
- 複数の独立した機能
- リファクタリングと新機能
- 設定変更と実装変更
- 依存関係更新と機能修正

## コミュニケーション

### 言語設定に応じた報告
環境変数 JJ_HOOK_LANGUAGE の設定（現在: japanese）に従って日本語で報告します。
```
📊 **コミット履歴分析結果**

検出した問題:
- feat: ユーザー登録機能 (3個の小さなコミットに分散)
- fix: タイポ修正 (本体変更と別コミット)
- docs: README更新 (機能追加と同時に行うべき)

提案する整理:
1. コミット A, B, C を統合 → "feat: ユーザー登録機能の実装"
2. コミット D, E を統合 → "fix: フォーム検証エラーメッセージ改善"
3. コミット F は独立して保持

実行予定のコマンド:
jj squash -r A::C
jj describe -r A -m "feat: ユーザー登録機能の実装"
```

### 実行確認
整理を実行する前に必ず確認を求め、承認後に実行します。危険な操作（HEAD^を超える大幅な履歴変更）は特に慎重に行います。

## ベストプラクティス

### セーフティ
- 整理前にバックアップブランチ作成
- 段階的な整理（一度に大量の変更を避ける）
- プッシュ済みコミットには触らない

### 品質向上
- 意味のあるコミットメッセージの提案
- Conventional Commits形式の適用
- 変更内容と目的の明確化

常にコミット履歴の品質向上を目指し、将来のメンテナンスや協働を考慮した整理を行います。"""
        else:  # english
            agent_content = """---
name: jj-commit-organizer
description: Specialized expert for observing jj log and jj diff, and organizing commits into appropriate units using jj squash and jj bookmark create. Proactively executes logical organization and refactoring of commit history.
tools: Bash, Read, Grep, Glob
---

You are a Jujutsu VCS (jj) expert specializing in commit history organization and refactoring.

## Role and Responsibilities

### Core Functions
1. **Commit History Analysis**: Review commit history with `jj log` and identify issues
2. **Detailed Diff Investigation**: Analyze each commit's changes using `jj diff`
3. **Logical Organization Proposals**: Group related commits and reorganize into appropriate units
4. **Automated Cleanup Execution**: Perform actual organization using `jj squash` and `jj bookmark create`

### Analysis Targets
- Consecutive small modifications to the same file
- Related features split across multiple commits
- Meaningless commit messages ("fix", "wip", "tmp", etc.)
- Separated typo fixes and formatting changes
- Logically unified changes dispersed across commits

### Organization Principles
- **Feature Units**: One feature or fix should be one commit
- **Logical Consistency**: Related changes should be integrated into the same commit
- **Clear Messages**: Each commit's purpose should be evident
- **Reviewability**: Changes should be appropriately sized for understanding

## Execution Procedures

### 1. Current State Analysis
```bash
# Check commit history (latest 20 entries)
jj log -r 'present(@)::heads(trunk)' --limit 20

# Check unpushed commits
jj log -r '@::heads(trunk) & ~heads(main)'
```

### 2. Detailed Diff Investigation
```bash
# Changes in specific commit
jj diff -r <commit-id>

# Cumulative diff between multiple commits
jj diff -r <start>..<end>

# Change history per file
jj log -p <file-path>
```

### 3. Organization Execution
```bash
# Squash multiple commits
jj squash -r <commit-range>

# Edit commit message
jj describe -r <commit-id> -m "New message"

# Create new bookmark
jj bookmark create <feature-name> -r <commit-id>
```

## Decision Criteria

### Commits to Merge
- Consecutive modifications to the same file
- Typo fixes and their corrections
- Feature additions and their tests
- Documentation and implementation correspondence
- Debug code additions and removals

### Changes to Separate
- Multiple independent features
- Refactoring and new features
- Configuration changes and implementation changes
- Dependency updates and feature fixes

## Communication

### English Reporting
```
📊 **Commit History Analysis Results**

Detected Issues:
- feat: User registration feature (scattered across 3 small commits)
- fix: Typo correction (separate from main change)
- docs: README update (should be with feature addition)

Proposed Organization:
1. Merge commits A, B, C → "feat: Implement user registration feature"
2. Merge commits D, E → "fix: Improve form validation error messages"
3. Keep commit F independent

Planned Commands:
jj squash -r A::C
jj describe -r A -m "feat: Implement user registration feature"
```

### Execution Confirmation
Always request confirmation before executing organization, and proceed only after approval. Exercise particular caution with dangerous operations (major history changes beyond HEAD^).

## Best Practices

### Safety
- Create backup branches before organization
- Gradual organization (avoid massive changes at once)
- Don't touch pushed commits

### Quality Improvement
- Propose meaningful commit messages
- Apply Conventional Commits format
- Clarify change content and purpose

Always aim to improve commit history quality, considering future maintenance and collaboration."""
        
        # ファイル書き込み
        with open(agent_file, "w", encoding="utf-8") as f:
            f.write(agent_content)
        
        console.print(Panel(
            Text("🤖 jj-commit-organizer サブエージェントのインストールが完了しました！\n\n"
                 "使用方法:\n"
                 "• Claude Code で「jj-commit-organizer サブエージェントを使ってコミット履歴を整理して」\n"
                 "• 「コミット履歴を確認して適切に整理してください」\n\n"
                 "機能:\n"
                 "• jj log と jj diff による履歴分析\n"
                 "• jj squash や jj bookmark create による自動整理\n"
                 "• 日本語での分析結果報告", 
                 style="bold green"),
            title="🎉 サブエージェント インストール成功",
            border_style="green"
        ))
        
    except OSError as e:
        console.print(f"[red]エラー: ファイル操作に失敗しました: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]予期しないエラーが発生しました: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("provider", type=click.Choice(["github-copilot"]), required=False, default="github-copilot")
@click.option("--check", "-c", is_flag=True, help="認証状態のみ確認")
def auth(provider: str, check: bool) -> None:
    """LLMプロバイダーの認証を行う。
    
    PROVIDER: 認証するプロバイダー (github-copilot)
    
    例:
    \b
    jj-hook auth github-copilot    # GitHub Copilot認証を実行
    jj-hook auth --check           # 認証状態を確認
    """
    
    if provider == "github-copilot":
        if check:
            # 認証状態のチェック
            console.print(f"[blue]GitHub Copilot認証状態を確認中...[/blue]")
            
            with console.status("[cyan]チェック中...", spinner="dots"):
                is_authenticated, status_msg = check_github_copilot_auth()
            
            if is_authenticated:
                console.print(Panel(
                    Text(f"✅ 認証状態: {status_msg}", style="bold green"),
                    title="GitHub Copilot認証",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    Text(f"❌ 認証状態: {status_msg}", style="bold red"),
                    title="GitHub Copilot認証",
                    border_style="red"
                ))
                console.print("\n[yellow]認証を行うには: [bold]jj-hook auth github-copilot[/bold][/yellow]")
        else:
            # 認証の実行
            console.print(Panel(
                Text("GitHub Copilot OAuth認証を開始します", style="bold blue"),
                title="🔐 認証",
                border_style="blue"
            ))
            
            # 現在の環境変数を表示
            model = os.environ.get("JJ_HOOK_MODEL", "未設定")
            console.print(f"[dim]現在のモデル設定: {model}[/dim]")
            
            if model != "github_copilot/gpt-4":
                console.print("[yellow]推奨設定:[/yellow]")
                console.print("[dim]export JJ_HOOK_MODEL=\"github_copilot/gpt-4\"[/dim]\n")
            
            success = authenticate_github_copilot()
            
            if success:
                console.print(Panel(
                    Text("🎉 GitHub Copilot認証が正常に完了しました！\n\nこれで jj-hook のAI機能を使用できます。", 
                         style="bold green"),
                    title="認証完了",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    Text("認証に失敗しました。以下を確認してください:\n\n"
                         "• GitHub Copilotサブスクリプションが有効か\n"
                         "• ネットワーク接続が正常か\n"
                         "• 認証フローが正しく完了したか", 
                         style="bold red"),
                    title="認証失敗",
                    border_style="red"
                ))
                sys.exit(1)


def is_jj_repository(cwd: str) -> bool:
    """現在のディレクトリがJujutsuリポジトリかどうかチェックする。"""
    try:
        result = subprocess.run(
            ["jj", "root"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_safety_conditions(cwd: str) -> List[str]:
    """安全性チェック。"""
    warnings = []
    
    try:
        # 未プッシュコミット数のチェック
        result = subprocess.run(
            ["jj", "log", "-r", "@::heads(main) & ~heads(origin/main)", "--no-graph"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            commit_count = len([line for line in result.stdout.split('\n') if line.strip()])
            if commit_count > 10:
                warnings.append(f"大量のコミット({commit_count}個)が対象です")
    except Exception:
        warnings.append("コミット数のチェックに失敗しました")
    
    return warnings


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="実際の統合は行わず、提案のみ表示"
)
@click.option(
    "--auto",
    is_flag=True,
    help="確認なしで自動実行"
)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="分析するコミット数の上限"
)
@click.option(
    "--tiny-threshold",
    type=int,
    default=5,
    help="極小コミットと判定する変更行数の閾値"
)
@click.option(
    "--small-threshold", 
    type=int,
    default=20,
    help="小さいコミットと判定する変更行数の閾値"
)
@click.option(
    "--confidence-threshold",
    type=float,
    default=0.7,
    help="実行する提案の最低信頼度（0.0-1.0）"
)
@click.option(
    "--exclude-pattern",
    multiple=True,
    help="統合対象外とするコミットメッセージの正規表現パターン"
)
@click.option(
    "--aggressive",
    is_flag=True,
    help="積極的な統合を行う（低信頼度の提案も実行）"
)
def organize(dry_run: bool, auto: bool, limit: int, tiny_threshold: int, small_threshold: int, 
            confidence_threshold: float, exclude_pattern: Tuple[str, ...], aggressive: bool) -> None:
    """AI分析を使用してコミット履歴を整理する。"""
    
    cwd = os.getcwd()
    language = os.environ.get("JJ_HOOK_LANGUAGE", "japanese")
    
    # Jujutsuリポジトリかチェック
    if not is_jj_repository(cwd):
        msg = "Jujutsuリポジトリではありません。" if language == "japanese" else "Not a Jujutsu repository."
        console.print(f"[red]{msg}[/red]")
        sys.exit(1)
    
    console.print(Panel(
        Text("🤖 AI分析によるコミット履歴整理", style="bold blue"),
        title="コミット履歴整理",
        border_style="blue"
    ))
    
    try:
        # CommitOrganizerインスタンス作成
        from .summarizer import CommitOrganizer, SummaryConfig
        
        config = SummaryConfig()
        config.prompt_language = language
        organizer = CommitOrganizer(config)
        
        # 設定可能なパラメータを適用
        organizer.tiny_threshold = tiny_threshold
        organizer.small_threshold = small_threshold
        organizer.exclude_patterns = list(exclude_pattern)
        organizer.aggressive_mode = aggressive
        
        # 積極モードの場合は信頼度閾値を下げる
        if aggressive:
            confidence_threshold = min(confidence_threshold, 0.5)
        
        # 安全性チェック
        with console.status("[cyan]安全性をチェック中...", spinner="dots"):
            warnings = check_safety_conditions(cwd)
        
        if warnings:
            console.print("[yellow]⚠️  警告:[/yellow]")
            for warning in warnings:
                console.print(f"  • {warning}")
            
            if not auto and not Confirm.ask("続行しますか？"):
                console.print("[dim]操作をキャンセルしました[/dim]")
                return
        
        # バックアップ作成
        if not dry_run:
            with console.status("[cyan]バックアップを作成中...", spinner="dots"):
                backup_success, backup_name = organizer.create_backup_bookmark(cwd)
            
            if backup_success:
                console.print(f"[dim]✅ バックアップ作成: {backup_name}[/dim]")
            else:
                console.print(f"[yellow]⚠️  バックアップ作成に失敗: {backup_name}[/yellow]")
        
        # AI分析によるコミット履歴分析
        with console.status("[cyan]AI分析中...", spinner="dots"):
            analysis_success, proposals = organizer.analyze_commits(cwd, limit)
        
        if not analysis_success:
            console.print("[red]AI分析に失敗しました[/red]")
            sys.exit(1)
        
        # 信頼度による提案フィルタリング
        filtered_proposals = [p for p in proposals if p.confidence_score >= confidence_threshold]
        
        if not proposals:
            console.print(Panel(
                "📊 分析完了\n"
                "• 統合が推奨されるコミットはありません\n"
                "• コミット履歴は既に適切に整理されています",
                title="分析結果",
                border_style="green"
            ))
            return
            
        if not filtered_proposals:
            console.print(Panel(
                f"📊 分析完了\n"
                f"• 全{len(proposals)}件の提案が信頼度閾値（{confidence_threshold:.1%}）未満です\n"
                f"• --aggressive オプションまたは --confidence-threshold を下げて再実行してください",
                title="分析結果",
                border_style="yellow"
            ))
            return
        
        # フィルタリング後の提案を使用
        proposals = filtered_proposals
        
        # 提案の表示
        console.print(Panel(
            f"📊 分析完了\n"
            f"• 分析対象: {limit}個のコミット\n"
            f"• 安全性警告: {len(warnings)}個\n"
            f"• 統合提案: {len(proposals)}件\n"
            f"• バックアップ: {'作成済み' if not dry_run and backup_success else 'スキップ'}",
            title="分析結果",
            border_style="green"
        ))
        
        # 各提案の詳細表示と選択
        selected_proposals = []
        
        for i, proposal in enumerate(proposals, 1):
            console.print(f"\n[bold blue]提案 {i}:[/bold blue]")
            console.print(f"[dim]統合対象:[/dim] {', '.join(proposal.source_commits)}")
            console.print(f"[dim]統合先:[/dim] {proposal.target_commit}")
            console.print(f"[dim]理由:[/dim] {proposal.reason}")
            console.print(f"[dim]推奨メッセージ:[/dim] {proposal.suggested_message}")
            console.print(f"[dim]信頼度:[/dim] {proposal.confidence_score:.1%}")
            
            if not auto and not dry_run:
                # 個別選択
                if Confirm.ask(f"この提案を実行しますか？", default=False):
                    selected_proposals.append(proposal)
            else:
                selected_proposals.append(proposal)
        
        if dry_run:
            console.print("\n[yellow]--dry-run モードのため、実際の変更は行いません[/yellow]")
            if not auto:
                console.print(f"[dim]選択された提案: {len(selected_proposals)}件[/dim]")
            return
        
        # 自動実行の場合は全体確認
        if auto and selected_proposals:
            console.print(f"\n[blue]自動実行モード: {len(selected_proposals)}件の統合を実行します[/blue]")
        elif not selected_proposals:
            console.print("\n[yellow]実行する提案が選択されませんでした[/yellow]")
            return
        
        # 統合実行
        executed_count = 0
        failed_count = 0
        
        for i, proposal in enumerate(selected_proposals, 1):
            console.print(f"\n[cyan]統合 {i}/{len(selected_proposals)}を実行中...[/cyan]")
            
            with console.status(f"[cyan]統合中... ({i}/{len(selected_proposals)})", spinner="dots"):
                success, message = organizer.execute_squash(cwd, proposal)
            
            if success:
                console.print(f"[green]✅ 完了: {message}[/green]")
                executed_count += 1
            else:
                console.print(f"[red]❌ 失敗: {message}[/red]")
                failed_count += 1
                
                if not auto and failed_count > 0:
                    if not Confirm.ask("エラーが発生しましたが続行しますか？"):
                        break
        
        # 結果表示
        console.print(Panel(
            f"🎉 整理完了\n"
            f"• 実行成功: {executed_count}件\n"
            f"• 実行失敗: {failed_count}件\n"
            f"• 選択済み: {len(selected_proposals)}件\n"
            f"• 全提案数: {len(proposals)}件",
            title="実行結果",
            border_style="green" if failed_count == 0 else "yellow"
        ))
        
        if executed_count > 0:
            console.print("\n[green]✅ コミット履歴の整理が完了しました[/green]")
            console.print("[dim]`jj log` でコミット履歴を確認してください[/dim]")
        
    except ImportError as e:
        console.print(f"[red]依存関係エラー: {e}[/red]")
        console.print("[dim]`uv sync` で依存関係を更新してください[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]エラーが発生しました: {e}[/red]")
        sys.exit(1)


def main() -> None:
    """CLIのメインエントリーポイント。"""
    cli()


if __name__ == "__main__":
    main()