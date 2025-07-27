#!/usr/bin/env python3
"""jj-cc-hook CLI implementation - Jujutsu専用."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text

from .config import SummaryConfig
from .jujutsu_backend import JujutsuBackend
from .template_loader import load_template

console = Console()


def create_fallback_summary(cwd: str) -> str:
    """フォールバック用の簡単なサマリー生成。"""
    LANGUAGE = os.environ.get("JJ_CC_HOOK_LANGUAGE", "japanese")
    backend = JujutsuBackend(cwd)
    if backend.is_repository() and backend.has_uncommitted_changes():
        return "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"
    else:
        return ""


def get_project_root() -> Path:
    """プロジェクトのルートディレクトリを取得する。"""
    hooks_dir = Path(__file__).parent / "hooks"
    return hooks_dir


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
    """Jujutsu用フック設定を生成する。"""
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": "jj-cc-hook post-tool-use", "timeout": 30}
                    ],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": "jj-cc-hook pre-tool-use", "timeout": 15}
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

    for event_name, hooks_list in new_settings["hooks"].items():
        if event_name not in merged["hooks"]:
            merged["hooks"][event_name] = []

        # 既存のjj-cc-hookフックを削除（重複回避）
        merged["hooks"][event_name] = [
            hook
            for hook in merged["hooks"][event_name]
            if not any("jj-cc-hook" in cmd.get("command", "") for cmd in hook.get("hooks", []))
        ]

        merged["hooks"][event_name].extend(hooks_list)

    return merged


@click.group()
@click.version_option()
def cli() -> None:
    """Jujutsu専用のClaude Codeフック."""
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
    """jj-cc-hookをClaude Code設定に追加する。"""

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
        existing_settings = get_existing_settings(settings_file)
        hook_settings = create_hook_settings()
        merged_settings = merge_settings(existing_settings, hook_settings)

        if dry_run:
            console.print("\n[yellow]変更プレビュー:[/yellow]")
            console.print(json.dumps(hook_settings, indent=2, ensure_ascii=False))
            console.print(
                "\n[dim]実際に変更するには --dry-run オプションを外して実行してください[/dim]"
            )
            return

        settings_file.parent.mkdir(parents=True, exist_ok=True)

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(merged_settings, f, indent=2, ensure_ascii=False)

        console.print(
            Panel(
                Text(
                    "jj-cc-hook (Jujutsu専用) のインストールが完了しました！\n\n"
                    "有効になった機能:\n"
                    "• ファイル編集前の新リビジョン作成 (PreToolUse)\n"
                    "• ファイル編集後の自動コミット (PostToolUse)\n\n"
                    "コマンド:\n"
                    "• jj-cc-hook post-tool-use\n"
                    "• jj-cc-hook pre-tool-use",
                    style="bold green",
                ),
                title="🎉 インストール成功",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[red]エラーが発生しました: {e}[/red]")
        sys.exit(1)


@cli.command(name="post-tool-use")
def post_tool_use() -> None:
    """PostToolUse フックを実行する（Jujutsu専用）。"""
    from .hooks.post_tool_use import main as post_tool_use_main

    try:
        # 環境変数を明示的にJujutsuに設定
        os.environ["VCS_TYPE"] = "jj"
        post_tool_use_main()
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]PostToolUse フックでエラーが発生しました: {e}[/red]")
        sys.exit(2)


@cli.command(name="pre-tool-use")
def pre_tool_use() -> None:
    """PreToolUse フックを実行する（Jujutsu専用）。"""
    from .hooks.pre_tool_use import main as pre_tool_use_main

    try:
        # 環境変数を明示的にJujutsuに設定
        os.environ["VCS_TYPE"] = "jj"
        pre_tool_use_main()
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]PreToolUse フックでエラーが発生しました: {e}[/red]")
        sys.exit(2)


@cli.command(name="summarize")
def summarize() -> None:
    """AIを使用して変更を要約し、Jujutsuリビジョンを作成する。"""
    cwd = os.getcwd()
    LANGUAGE = os.environ.get("JJ_CC_HOOK_LANGUAGE", "japanese")

    try:
        backend = JujutsuBackend(cwd)
        
        if not backend.is_repository():
            msg = (
                "Jujutsuリポジトリではありません。スキップします。"
                if LANGUAGE == "japanese"
                else "Not a Jujutsu repository. Skipping."
            )
            console.print(f"[red]{msg}[/red]")
            sys.exit(0)

        if not backend.has_uncommitted_changes():
            msg = (
                "変更がありません。コミットをスキップします。"
                if LANGUAGE == "japanese"
                else "No changes found. Skipping commit."
            )
            console.print(f"[yellow]{msg}[/yellow]")
            sys.exit(0)

        console.print("[blue]AIがリビジョン説明を生成中...[/blue]")
        
        try:
            from .summarizer import JujutsuSummarizer

            summarizer = JujutsuSummarizer()
            success, summary = summarizer.generate_commit_summary(cwd)

            if not success:
                console.print(f"[red]サマリー生成に失敗しました: {summary}[/red]")
                summary = create_fallback_summary(cwd)
                if not summary:
                    console.print("[yellow]変更がありません。コミットをスキップします。[/yellow]")
                    sys.exit(0)

        except Exception as e:
            console.print(f"[red]予期しないエラー: {e}[/red]")
            summary = create_fallback_summary(cwd)
            if not summary:
                console.print("[yellow]変更がありません。コミットをスキップします。[/yellow]")
                sys.exit(0)

        commit_success, commit_result = backend.commit_changes(summary)

        if commit_success:
            console.print(f"[green]✅ 自動リビジョン作成完了: {summary}[/green]")
            if commit_result:
                console.print(f"詳細: {commit_result}")
        else:
            console.print(f"[red]❌ リビジョン作成に失敗しました: {commit_result}[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]エラーが発生しました: {e}[/red]")
        sys.exit(1)


def main() -> None:
    """CLIのメインエントリーポイント。"""
    cli()


if __name__ == "__main__":
    main()