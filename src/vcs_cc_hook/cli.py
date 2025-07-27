#!/usr/bin/env python3
"""jj-hook CLI implementation."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from .template_loader import load_template
from .vcs_backend import detect_vcs_backend, is_vcs_repository

console = Console()


def create_fallback_summary(cwd: str) -> str:
    """フォールバック用の簡単なサマリー生成。"""
    LANGUAGE = os.environ.get("JJ_HOOK_LANGUAGE", "english")
    backend = detect_vcs_backend(cwd)
    if backend and backend.has_uncommitted_changes():
        return "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"
    else:
        return ""


def is_jj_repository(cwd: str) -> bool:
    """現在のディレクトリがJujutsuリポジトリかどうかチェックする（下位互換用）。"""
    backend = detect_vcs_backend(cwd)
    return backend is not None and hasattr(backend, "is_repository") and backend.is_repository()


def has_uncommitted_changes(cwd: str) -> bool:
    """コミットされていない変更があるかチェックする。"""
    backend = detect_vcs_backend(cwd)
    return backend is not None and backend.has_uncommitted_changes()


def commit_changes(cwd: str, message: str) -> tuple[bool, str]:
    """変更をコミットする。"""
    backend = detect_vcs_backend(cwd)
    if backend:
        return backend.commit_changes(message)
    else:
        return False, "VCSリポジトリが見つかりません"


def check_github_copilot_auth() -> tuple[bool, str]:
    """GitHub Copilot認証状態をチェックする。"""
    try:
        import litellm

        from .summarizer import JujutsuSummarizer

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
                "Copilot-Integration-Id": "vscode-chat",
            },
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

        from .summarizer import JujutsuSummarizer

        console.print("\n[blue]GitHub Copilot認証を開始します...[/blue]")

        summarizer = JujutsuSummarizer()
        if not summarizer.config.model.startswith("github_copilot/"):
            console.print(
                "[yellow]警告: JJ_HOOK_MODELがGitHub Copilotモデルに設定されていません[/yellow]"
            )
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
                "Copilot-Integration-Id": "vscode-chat",
            },
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
            console.print(
                "[yellow]認証フローが開始されました。上記の指示に従って認証を完了してください。[/yellow]"
            )

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
                            "Copilot-Integration-Id": "vscode-chat",
                        },
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


def get_slash_command_content(language: str = "japanese") -> str:
    """Generate Markdown content for slash command from template file."""
    from pathlib import Path

    template_path = Path(__file__).parent / "templates" / "slash_command.md"

    try:
        with open(template_path, encoding="utf-8") as f:
            content = f.read()

        # Replace language placeholder
        return content.format(language=language)
    except FileNotFoundError:
        # Fallback to hardcoded content if template file not found
        if language == "japanese":
            return """jj-commit-organizerサブエージェントを使ってコミット履歴を分析し、適切に整理してください。

jj log と jj diff でコミット履歴を確認し、関連するコミットをまとめたり、意味のあるコミットメッセージに変更するなど、論理的な整理を行ってください。

具体的には：
1. 現在のコミット履歴を確認
2. 統合すべきコミットや分離すべき変更を特定
3. jj squash や jj describe を使った整理の提案
4. ユーザーの確認後に実際の整理作業を実行

安全のため、作業前にバックアップブランチの作成も行ってください。"""
        else:  # english
            return """Use the jj-commit-organizer sub-agent to analyze and organize the commit history appropriately.

Please review the commit history using jj log and jj diff, then logically organize it by grouping related commits and creating meaningful commit messages.

Specifically:
1. Check the current commit history
2. Identify commits to merge or changes to separate
3. Propose organization using jj squash and jj describe
4. Execute actual organization work after user confirmation

For safety, please create a backup branch before starting work."""


def create_claude_settings_dir(target_path: Path) -> Path:
    """Claude設定ディレクトリを作成し、パスを返す。"""
    claude_dir = target_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    return claude_dir


def get_existing_settings(settings_file: Path) -> dict[str, Any]:
    """既存の設定ファイルを読み込む。存在しない場合は空の辞書を返す。"""
    if settings_file.exists():
        try:
            with open(settings_file, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[yellow]警告: 既存の設定ファイルの読み込みに失敗しました: {e}[/yellow]")
            return {}
    return {}


def create_hook_settings() -> dict[str, Any]:
    """フック設定を生成する。"""
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": "jj-hook post-tool-use", "timeout": 30}
                    ],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": "jj-hook pre-tool-use", "timeout": 15}
                    ],
                }
            ],
        }
    }

    return settings


def merge_settings(existing: dict[str, Any], new_settings: dict[str, Any]) -> dict[str, Any]:
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
            hook
            for hook in merged["hooks"][event_name]
            if not any("jj-hook" in cmd.get("command", "") for cmd in hook.get("hooks", []))
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
    "--global",
    "is_global",
    is_flag=True,
    help="グローバル設定（~/.claude/settings.json）にインストール",
)
@click.option("--dry-run", is_flag=True, help="実際の変更は行わず、変更内容のプレビューのみ表示")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
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
            console.print(
                "\n[dim]実際に変更するには --dry-run オプションを外して実行してください[/dim]"
            )
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

        console.print(
            Panel(
                Text(
                    "jj-hook のインストールが完了しました！\n\n"
                    "有効になった機能:\n"
                    "• ファイル編集前の新ブランチ作成 (PreToolUse)\n"
                    "• ファイル編集後の自動コミット (PostToolUse)\n\n"
                    "コマンド:\n"
                    "• jj-hook post-tool-use\n"
                    "• jj-hook pre-tool-use",
                    style="bold green",
                ),
                title="🎉 インストール成功",
                border_style="green",
            )
        )

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
    "--global", "is_global", is_flag=True, help="グローバル設定（~/.claude/agents/）にインストール"
)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
)
def install_agent(is_global: bool, path: Optional[Path]) -> None:
    """jj-commit-organizerサブエージェントをClaude Code設定に追加する。"""

    # 言語設定の取得
    language = os.environ.get("JJ_HOOK_LANGUAGE", "english")

    # インストール先の決定
    if is_global and path:
        error_msg = (
            "エラー: --globalと--pathは同時に指定できません"
            if language == "japanese"
            else "Error: --global and --path cannot be used together"
        )
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)

    if is_global:
        agents_dir = Path.home() / ".claude" / "agents"
        install_location = "グローバル設定" if language == "japanese" else "Global settings"
    else:
        target_path = path if path is not None else Path.cwd()
        agents_dir = target_path / ".claude" / "agents"
        install_location = (
            f"ローカル設定 ({target_path})"
            if language == "japanese"
            else f"Local settings ({target_path})"
        )

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
            exists_msg = (
                f"ファイル {agent_file} が既に存在します。上書きしますか？"
                if language == "japanese"
                else f"File {agent_file} already exists. Overwrite?"
            )
            cancel_msg = (
                "インストールをキャンセルしました"
                if language == "japanese"
                else "Installation cancelled"
            )
            if not Confirm.ask(f"[yellow]{exists_msg}[/yellow]"):
                console.print(f"[dim]{cancel_msg}[/dim]")
                return

        agent_content = load_template("agent_content")

        # ファイル書き込み
        with open(agent_file, "w", encoding="utf-8") as f:
            f.write(agent_content)

        console.print(
            Panel(
                Text(
                    "🤖 jj-commit-organizer サブエージェントのインストールが完了しました！\n\n"
                    "使用方法:\n"
                    "• Claude Code で「jj-commit-organizer サブエージェントを使ってコミット履歴を整理して」\n"
                    "• 「コミット履歴を確認して適切に整理してください」\n\n"
                    "機能:\n"
                    "• jj log と jj diff による履歴分析\n"
                    "• jj squash や jj bookmark create による自動整理\n"
                    "• 日本語での分析結果報告",
                    style="bold green",
                ),
                title="🎉 サブエージェント インストール成功",
                border_style="green",
            )
        )

    except OSError as e:
        console.print(f"[red]エラー: ファイル操作に失敗しました: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]予期しないエラーが発生しました: {e}[/red]")
        sys.exit(1)


@cli.command(name="install-slash-command")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="グローバル設定（~/.claude/commands/）にインストール",
)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
)
def install_slash_command(is_global: bool, path: Optional[Path]) -> None:
    """jj-commit-organizerを呼び出すslash command（/jj-commit-organizer）をClaude Code設定に追加する。"""

    # 言語設定の取得
    language = os.environ.get("JJ_HOOK_LANGUAGE", "japanese")

    # インストール先の決定
    if is_global and path:
        error_msg = (
            "エラー: --globalと--pathは同時に指定できません"
            if language == "japanese"
            else "Error: --global and --path cannot be used together"
        )
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)

    if is_global:
        slash_commands_dir = Path.home() / ".claude" / "commands"
        install_location = "グローバル設定" if language == "japanese" else "Global settings"
    else:
        target_path = path if path is not None else Path.cwd()
        slash_commands_dir = target_path / ".claude" / "commands"
        install_location = (
            f"ローカル設定 ({target_path})"
            if language == "japanese"
            else f"Local settings ({target_path})"
        )

    location_label = "インストール先" if language == "japanese" else "Install location"
    directory_label = "ディレクトリ" if language == "japanese" else "Directory"
    console.print(f"[blue]{location_label}: {install_location}[/blue]")
    console.print(f"[dim]{directory_label}: {slash_commands_dir}[/dim]")

    try:
        # ディレクトリ作成
        slash_commands_dir.mkdir(parents=True, exist_ok=True)

        # Slash commandファイルのパス
        command_file = slash_commands_dir / "jj-commit-organizer.md"

        # 既存ファイルの確認
        if command_file.exists():
            exists_msg = (
                f"ファイル {command_file} が既に存在します。上書きしますか？"
                if language == "japanese"
                else f"File {command_file} already exists. Overwrite?"
            )
            cancel_msg = (
                "インストールをキャンセルしました"
                if language == "japanese"
                else "Installation cancelled"
            )
            if not Confirm.ask(f"[yellow]{exists_msg}[/yellow]"):
                console.print(f"[dim]{cancel_msg}[/dim]")
                return

        # Slash commandの内容を取得
        command_content = get_slash_command_content(language)

        # ファイル書き込み
        with open(command_file, "w", encoding="utf-8") as f:
            f.write(command_content)

        success_title = (
            "🎉 Slash Command インストール成功"
            if language == "japanese"
            else "🎉 Slash Command Installation Success"
        )
        usage_label = "使用方法" if language == "japanese" else "Usage"
        function_label = "機能" if language == "japanese" else "Features"

        if language == "japanese":
            console.print(
                Panel(
                    Text(
                        "⚡ /jj-commit-organizer slash command のインストールが完了しました！\n\n"
                        f"{usage_label}:\n"
                        "• Claude Code で「/jj-commit-organizer」と入力\n"
                        "• jj-commit-organizer サブエージェントが自動呼び出し\n"
                        "• コミット履歴の分析と整理を実行\n\n"
                        f"{function_label}:\n"
                        "• jj log と jj diff による履歴分析\n"
                        "• jj squash や jj describe による自動整理\n"
                        "• バックアップブランチの自動作成\n"
                        "• 日本語での分析結果報告",
                        style="bold green",
                    ),
                    title=success_title,
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    Text(
                        "⚡ /jj-commit-organizer slash command has been installed successfully!\n\n"
                        f"{usage_label}:\n"
                        '• Type "/jj-commit-organizer" in Claude Code\n'
                        "• Automatically invokes jj-commit-organizer sub-agent\n"
                        "• Executes commit history analysis and organization\n\n"
                        f"{function_label}:\n"
                        "• History analysis using jj log and jj diff\n"
                        "• Automatic organization with jj squash and jj describe\n"
                        "• Automatic backup branch creation\n"
                        "• Analysis results reported in English",
                        style="bold green",
                    ),
                    title=success_title,
                    border_style="green",
                )
            )

    except OSError as e:
        error_msg = (
            f"エラー: ファイル操作に失敗しました: {e}"
            if language == "japanese"
            else f"Error: File operation failed: {e}"
        )
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)
    except Exception as e:
        error_msg = (
            f"予期しないエラーが発生しました: {e}"
            if language == "japanese"
            else f"Unexpected error occurred: {e}"
        )
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)


@cli.command(name="install-all")
@click.option("--global", "is_global", is_flag=True, help="グローバル設定にインストール")
@click.option("--dry-run", is_flag=True, help="実際の変更は行わず、変更内容のプレビューのみ表示")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
)
def install_all(is_global: bool, dry_run: bool, path: Optional[Path]) -> None:
    """jj-hook の全機能（hooks, sub-agent, slash command）を一括インストールする。"""

    # 言語設定の取得
    language = os.environ.get("JJ_HOOK_LANGUAGE", "japanese")

    # インストール先の決定
    if is_global and path:
        error_msg = (
            "エラー: --globalと--pathは同時に指定できません"
            if language == "japanese"
            else "Error: --global and --path cannot be used together"
        )
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)

    if is_global:
        install_location = "グローバル設定" if language == "japanese" else "Global settings"
    else:
        target_path = path if path is not None else Path.cwd()
        install_location = (
            f"ローカル設定 ({target_path})"
            if language == "japanese"
            else f"Local settings ({target_path})"
        )

    if language == "japanese":
        console.print(
            Panel(
                Text("🚀 jj-hook 一括インストールを開始します", style="bold blue"),
                title="一括インストール",
                border_style="blue",
            )
        )
        console.print(f"[blue]インストール先: {install_location}[/blue]")
        console.print(f"[dim]DRY-RUNモード: {'有効' if dry_run else '無効'}[/dim]\n")
    else:
        console.print(
            Panel(
                Text("🚀 Starting jj-hook bulk installation", style="bold blue"),
                title="Bulk Installation",
                border_style="blue",
            )
        )
        console.print(f"[blue]Install location: {install_location}[/blue]")
        console.print(f"[dim]DRY-RUN mode: {'Enabled' if dry_run else 'Disabled'}[/dim]\n")

    installation_results = []

    try:
        # 1. Hooks インストール
        hooks_label = "1. フック設定" if language == "japanese" else "1. Hooks"
        console.print(f"[cyan]{hooks_label}をインストール中...[/cyan]")

        try:
            # hookのインストールロジックを実行
            if not dry_run:
                # 設定ファイルパスの決定
                if is_global:
                    settings_file = Path.home() / ".claude" / "settings.json"
                else:
                    target_path_hooks = path if path is not None else Path.cwd()
                    claude_dir = create_claude_settings_dir(target_path_hooks)
                    settings_file = claude_dir / "settings.json"

                # 既存設定の読み込み
                existing_settings = get_existing_settings(settings_file)

                # 新しいフック設定を生成
                hook_settings = create_hook_settings()

                # 設定をマージ
                merged_settings = merge_settings(existing_settings, hook_settings)

                # 設定ファイルの親ディレクトリを作成
                settings_file.parent.mkdir(parents=True, exist_ok=True)

                # 設定ファイルの書き込み
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump(merged_settings, f, indent=2, ensure_ascii=False)

                hooks_result = "✅ 完了" if language == "japanese" else "✅ Completed"
            else:
                hooks_result = "📋 プレビュー" if language == "japanese" else "📋 Preview"

            installation_results.append(("Hooks", True, hooks_result))
            console.print(f"  {hooks_result}")
        except Exception as e:
            error_msg = f"❌ エラー: {e}" if language == "japanese" else f"❌ Error: {e}"
            installation_results.append(("Hooks", False, error_msg))
            console.print(f"  {error_msg}")

        # 2. Sub-agent インストール
        subagent_label = "2. サブエージェント" if language == "japanese" else "2. Sub-agent"
        console.print(f"\n[cyan]{subagent_label}をインストール中...[/cyan]")

        try:
            if not dry_run:
                # sub-agentディレクトリの決定
                if is_global:
                    agents_dir = Path.home() / ".claude" / "agents"
                else:
                    target_path_agent = path if path is not None else Path.cwd()
                    agents_dir = target_path_agent / ".claude" / "agents"

                # ディレクトリ作成
                agents_dir.mkdir(parents=True, exist_ok=True)

                # サブエージェント定義ファイルのパス
                agent_file = agents_dir / "jj-commit-organizer.md"

                # サブエージェント定義の内容を生成
                agent_content = load_template("agent_content")

                # ファイル書き込み
                with open(agent_file, "w", encoding="utf-8") as f:
                    f.write(agent_content)

                subagent_result = "✅ 完了" if language == "japanese" else "✅ Completed"
            else:
                subagent_result = "📋 プレビュー" if language == "japanese" else "📋 Preview"

            installation_results.append(("Sub-agent", True, subagent_result))
            console.print(f"  {subagent_result}")
        except Exception as e:
            error_msg = f"❌ エラー: {e}" if language == "japanese" else f"❌ Error: {e}"
            installation_results.append(("Sub-agent", False, error_msg))
            console.print(f"  {error_msg}")

        # 3. Slash command インストール
        slash_label = "3. Slash Command" if language == "japanese" else "3. Slash Command"
        console.print(f"\n[cyan]{slash_label}をインストール中...[/cyan]")

        try:
            if not dry_run:
                # slash commandディレクトリの決定
                if is_global:
                    slash_commands_dir = Path.home() / ".claude" / "commands"
                else:
                    target_path_slash = path if path is not None else Path.cwd()
                    slash_commands_dir = target_path_slash / ".claude" / "commands"

                # ディレクトリ作成
                slash_commands_dir.mkdir(parents=True, exist_ok=True)

                # Slash commandファイルのパス
                command_file = slash_commands_dir / "jj-commit-organizer.md"

                # Slash commandの内容を取得
                command_content = get_slash_command_content(language)

                # ファイル書き込み
                with open(command_file, "w", encoding="utf-8") as f:
                    f.write(command_content)

                slash_result = "✅ 完了" if language == "japanese" else "✅ Completed"
            else:
                slash_result = "📋 プレビュー" if language == "japanese" else "📋 Preview"

            installation_results.append(("Slash Command", True, slash_result))
            console.print(f"  {slash_result}")
        except Exception as e:
            error_msg = f"❌ エラー: {e}" if language == "japanese" else f"❌ Error: {e}"
            installation_results.append(("Slash Command", False, error_msg))
            console.print(f"  {error_msg}")

        # 結果のサマリー表示
        successful_count = sum(1 for _, success, _ in installation_results if success)
        failed_count = len(installation_results) - successful_count

        if language == "japanese":
            title = "🎉 一括インストール完了" if failed_count == 0 else "⚠️ 一括インストール結果"
            summary_text = "📊 インストール結果\n\n"
            for component, success, result in installation_results:
                status_icon = "✅" if success else "❌"
                summary_text += f"{status_icon} {component}: {result}\n"

            summary_text += f"\n成功: {successful_count}/{len(installation_results)}件"

            if successful_count > 0:
                summary_text += "\n\n🚀 使用可能な機能:"
                if any(name == "Hooks" and success for name, success, _ in installation_results):
                    summary_text += "\n• ファイル編集時の自動コミット"
                if any(
                    name == "Sub-agent" and success for name, success, _ in installation_results
                ):
                    summary_text += "\n• jj-commit-organizer サブエージェント"
                if any(
                    name == "Slash Command" and success for name, success, _ in installation_results
                ):
                    summary_text += "\n• /jj-commit-organizer コマンド"
        else:
            title = (
                "🎉 Bulk Installation Complete"
                if failed_count == 0
                else "⚠️ Bulk Installation Results"
            )
            summary_text = "📊 Installation Results\n\n"
            for component, success, result in installation_results:
                status_icon = "✅" if success else "❌"
                summary_text += f"{status_icon} {component}: {result}\n"

            summary_text += f"\nSuccess: {successful_count}/{len(installation_results)} components"

            if successful_count > 0:
                summary_text += "\n\n🚀 Available Features:"
                if any(name == "Hooks" and success for name, success, _ in installation_results):
                    summary_text += "\n• Automatic commits on file edits"
                if any(
                    name == "Sub-agent" and success for name, success, _ in installation_results
                ):
                    summary_text += "\n• jj-commit-organizer sub-agent"
                if any(
                    name == "Slash Command" and success for name, success, _ in installation_results
                ):
                    summary_text += "\n• /jj-commit-organizer command"

        border_style = "green" if failed_count == 0 else "yellow"
        console.print(
            Panel(
                Text(summary_text, style="bold green" if failed_count == 0 else "bold yellow"),
                title=title,
                border_style=border_style,
            )
        )

        if dry_run:
            dry_run_msg = (
                "\n[yellow]--dry-run モードのため、実際の変更は行いませんでした[/yellow]"
                if language == "japanese"
                else "\n[yellow]--dry-run mode: No actual changes were made[/yellow]"
            )
            console.print(dry_run_msg)

    except Exception as e:
        error_msg = (
            f"一括インストール中にエラーが発生しました: {e}"
            if language == "japanese"
            else f"Error during bulk installation: {e}"
        )
        console.print(f"[red]{error_msg}[/red]")
        sys.exit(1)


@cli.command()
@click.argument(
    "provider", type=click.Choice(["github-copilot"]), required=False, default="github-copilot"
)
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
            console.print("[blue]GitHub Copilot認証状態を確認中...[/blue]")

            with console.status("[cyan]チェック中...", spinner="dots"):
                is_authenticated, status_msg = check_github_copilot_auth()

            if is_authenticated:
                console.print(
                    Panel(
                        Text(f"✅ 認証状態: {status_msg}", style="bold green"),
                        title="GitHub Copilot認証",
                        border_style="green",
                    )
                )
            else:
                console.print(
                    Panel(
                        Text(f"❌ 認証状態: {status_msg}", style="bold red"),
                        title="GitHub Copilot認証",
                        border_style="red",
                    )
                )
                console.print(
                    "\n[yellow]認証を行うには: [bold]jj-hook auth github-copilot[/bold][/yellow]"
                )
        else:
            # 認証の実行
            console.print(
                Panel(
                    Text("GitHub Copilot OAuth認証を開始します", style="bold blue"),
                    title="🔐 認証",
                    border_style="blue",
                )
            )

            # 現在の環境変数を表示
            model = os.environ.get("JJ_HOOK_MODEL", "未設定")
            console.print(f"[dim]現在のモデル設定: {model}[/dim]")

            if model != "github_copilot/gpt-4":
                console.print("[yellow]推奨設定:[/yellow]")
                console.print('[dim]export JJ_HOOK_MODEL="github_copilot/gpt-4"[/dim]\n')

            success = authenticate_github_copilot()

            if success:
                console.print(
                    Panel(
                        Text(
                            "🎉 GitHub Copilot認証が正常に完了しました！\n\nこれで jj-hook のAI機能を使用できます。",
                            style="bold green",
                        ),
                        title="認証完了",
                        border_style="green",
                    )
                )
            else:
                console.print(
                    Panel(
                        Text(
                            "認証に失敗しました。以下を確認してください:\n\n"
                            "• GitHub Copilotサブスクリプションが有効か\n"
                            "• ネットワーク接続が正常か\n"
                            "• 認証フローが正しく完了したか",
                            style="bold red",
                        ),
                        title="認証失敗",
                        border_style="red",
                    )
                )
                sys.exit(1)


@cli.command(name="summarize")
def summarize() -> None:
    """AIを使用して変更を要約し、コミットする。"""
    cwd = os.getcwd()
    LANGUAGE = os.environ.get("JJ_HOOK_LANGUAGE", "english")

    try:
        if not is_vcs_repository(cwd):
            msg = (
                "VCSリポジトリではありません。スキップします。"
                if LANGUAGE == "japanese"
                else "Not a VCS repository. Skipping."
            )
            console.print(f"[red]{msg}[/red]")
            sys.exit(0)

        if not has_uncommitted_changes(cwd):
            msg = (
                "変更がありません。コミットをスキップします。"
                if LANGUAGE == "japanese"
                else "No changes found. Skipping commit."
            )
            console.print(f"[yellow]{msg}[/yellow]")
            sys.exit(0)

        console.print("[blue]AIがコミットメッセージを生成中...[/blue]")
        try:
            from .summarizer import JujutsuSummarizer

            summarizer = JujutsuSummarizer()
            success, summary = summarizer.generate_commit_summary(cwd)

            if not success:
                error_msg = (
                    f"サマリー生成に失敗しました: {summary}"
                    if LANGUAGE == "japanese"
                    else f"Summary generation failed: {summary}"
                )
                console.print(f"[red]{error_msg}[/red]")
                summary = create_fallback_summary(cwd)
                if not summary:
                    # フォールバックでもサマリーが生成できない場合
                    msg = (
                        "変更がありません。コミットをスキップします。"
                        if LANGUAGE == "japanese"
                        else "No changes found. Skipping commit."
                    )
                    console.print(f"[yellow]{msg}[/yellow]")
                    sys.exit(0)

        except ImportError:
            console.print(
                "[yellow]警告: summarizerモジュールのインポートに失敗しました。フォールバックします。[/yellow]"
            )
            summary = create_fallback_summary(cwd)
            if not summary:
                msg = (
                    "変更がありません。コミットをスキップします。"
                    if LANGUAGE == "japanese"
                    else "No changes found. Skipping commit."
                )
                console.print(f"[yellow]{msg}[/yellow]")
                sys.exit(0)
        except Exception as e:
            error_msg = (
                f"予期しないエラー: {type(e).__name__}: {str(e)}"
                if LANGUAGE == "japanese"
                else f"Unexpected error: {type(e).__name__}: {str(e)}"
            )
            console.print(f"[red]{error_msg}[/red]")
            summary = create_fallback_summary(cwd)
            if not summary:
                msg = (
                    "変更がありません。コミットをスキップします。"
                    if LANGUAGE == "japanese"
                    else "No changes found. Skipping commit."
                )
                console.print(f"[yellow]{msg}[/yellow]")
                sys.exit(0)

        commit_success, commit_result = commit_changes(cwd, summary)

        if commit_success:
            success_msg = (
                f"✅ 自動コミット完了: {summary}"
                if LANGUAGE == "japanese"
                else f"✅ Auto-commit completed: {summary}"
            )
            console.print(f"[green]{success_msg}[/green]")
            if commit_result:
                console.print(f"詳細: {commit_result}")
        else:
            error_msg = (
                f"❌ コミットに失敗しました: {commit_result}"
                if LANGUAGE == "japanese"
                else f"❌ Commit failed: {commit_result}"
            )
            console.print(f"[red]{error_msg}[/red]")
            sys.exit(1)

    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]エラーが発生しました: {e}[/red]")
        sys.exit(1)


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
            timeout=10,
        )
        if result.returncode == 0:
            commit_count = len([line for line in result.stdout.split("\n") if line.strip()])
            if commit_count > 10:
                warnings.append(f"大量のコミット({commit_count}個)が対象です")
    except Exception:
        warnings.append("コミット数のチェックに失敗しました")

    return warnings


@cli.command()
@click.option("--dry-run", is_flag=True, help="実際の統合は行わず、提案のみ表示")
@click.option("--auto", is_flag=True, help="確認なしで自動実行")
@click.option("--limit", type=int, default=10, help="分析するコミット数の上限")
@click.option("--tiny-threshold", type=int, default=5, help="極小コミットと判定する変更行数の閾値")
@click.option(
    "--small-threshold", type=int, default=20, help="小さいコミットと判定する変更行数の閾値"
)
@click.option(
    "--confidence-threshold", type=float, default=0.7, help="実行する提案の最低信頼度（0.0-1.0）"
)
@click.option(
    "--exclude-pattern", multiple=True, help="統合対象外とするコミットメッセージの正規表現パターン"
)
@click.option("--aggressive", is_flag=True, help="積極的な統合を行う（低信頼度の提案も実行）")
def organize(
    dry_run: bool,
    auto: bool,
    limit: int,
    tiny_threshold: int,
    small_threshold: int,
    confidence_threshold: float,
    exclude_pattern: Tuple[str, ...],
    aggressive: bool,
) -> None:
    """AI分析を使用してコミット履歴を整理する。"""

    cwd = os.getcwd()
    language = os.environ.get("JJ_HOOK_LANGUAGE", "japanese")

    # VCSリポジトリかチェック
    if not is_vcs_repository(cwd):
        msg = "VCSリポジトリではありません。" if language == "japanese" else "Not a VCS repository."
        console.print(f"[red]{msg}[/red]")
        sys.exit(1)

    console.print(
        Panel(
            Text("🤖 AI分析によるコミット履歴整理", style="bold blue"),
            title="コミット履歴整理",
            border_style="blue",
        )
    )

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
            console.print(
                Panel(
                    "📊 分析完了\n"
                    "• 統合が推奨されるコミットはありません\n"
                    "• コミット履歴は既に適切に整理されています",
                    title="分析結果",
                    border_style="green",
                )
            )
            return

        if not filtered_proposals:
            console.print(
                Panel(
                    f"📊 分析完了\n"
                    f"• 全{len(proposals)}件の提案が信頼度閾値（{confidence_threshold:.1%}）未満です\n"
                    f"• --aggressive オプションまたは --confidence-threshold を下げて再実行してください",
                    title="分析結果",
                    border_style="yellow",
                )
            )
            return

        # フィルタリング後の提案を使用
        proposals = filtered_proposals

        # 提案の表示
        console.print(
            Panel(
                f"📊 分析完了\n"
                f"• 分析対象: {limit}個のコミット\n"
                f"• 安全性警告: {len(warnings)}個\n"
                f"• 統合提案: {len(proposals)}件\n"
                f"• バックアップ: {'作成済み' if not dry_run and backup_success else 'スキップ'}",
                title="分析結果",
                border_style="green",
            )
        )

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
                if Confirm.ask("この提案を実行しますか？", default=False):
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
            console.print(
                f"\n[blue]自動実行モード: {len(selected_proposals)}件の統合を実行します[/blue]"
            )
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
        console.print(
            Panel(
                f"🎉 整理完了\n"
                f"• 実行成功: {executed_count}件\n"
                f"• 実行失敗: {failed_count}件\n"
                f"• 選択済み: {len(selected_proposals)}件\n"
                f"• 全提案数: {len(proposals)}件",
                title="実行結果",
                border_style="green" if failed_count == 0 else "yellow",
            )
        )

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
