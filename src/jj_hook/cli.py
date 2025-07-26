#!/usr/bin/env python3
"""jj-hook CLI implementation."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


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


def create_hook_settings(target_path: Path) -> dict:
    """フック設定を生成する。"""
    hooks_dir = get_project_root()
    
    # 絶対パスでフックスクリプトを参照
    post_tool_use_script = hooks_dir / "post_tool_use.py"
    pre_tool_use_script = hooks_dir / "pre_tool_use.py"
    
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"python {post_tool_use_script}",
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
                            "command": f"python {pre_tool_use_script}",
                            "timeout": 15
                        }
                    ]
                }
            ]
        }
    }
    
    return settings


def merge_settings(existing: dict, new_settings: dict) -> dict:
    """既存の設定と新しい設定をマージする。"""
    merged = existing.copy()
    
    if "hooks" not in merged:
        merged["hooks"] = {}
    
    # 新しいフック設定をマージ
    for event_name, hooks_list in new_settings["hooks"].items():
        if event_name not in merged["hooks"]:
            merged["hooks"][event_name] = []
        
        # 既存のフックと重複しないように追加
        for new_hook_config in hooks_list:
            # 同じmatcherのフックが既に存在するかチェック
            matcher = new_hook_config.get("matcher", "")
            existing_matchers = [
                hook.get("matcher", "") for hook in merged["hooks"][event_name]
            ]
            
            if matcher not in existing_matchers:
                merged["hooks"][event_name].append(new_hook_config)
    
    return merged


@click.group()
@click.version_option()
def cli() -> None:
    """Jujutsu hooks for Claude Code."""
    pass


@cli.command()
@click.option(
    "--path", 
    "-p", 
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（指定しない場合は現在のディレクトリ）"
)
def install(path: Optional[Path]) -> None:
    """指定されたディレクトリにjj-hookを設定する。"""
    
    # ターゲットパスの決定
    target_path = path if path is not None else Path.cwd()
    console.print(f"[green]フックをインストールします: {target_path}[/green]")
    
    try:
        # .claudeディレクトリの作成
        claude_dir = create_claude_settings_dir(target_path)
        settings_file = claude_dir / "settings.json"
        
        # フックスクリプトのコピー
        hooks_dir = get_project_root()
        target_hooks_dir = claude_dir / "hooks"
        
        if target_hooks_dir.exists():
            shutil.rmtree(target_hooks_dir)
        
        shutil.copytree(hooks_dir, target_hooks_dir)
        console.print(f"[green]フックスクリプトをコピーしました: {target_hooks_dir}[/green]")
        
        # 設定ファイルの更新
        existing_settings = get_existing_settings(settings_file)
        hook_settings = create_hook_settings(target_path)
        
        # settings.jsonのhook pathを相対パスに更新
        hook_settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"] = "$CLAUDE_PROJECT_DIR/.claude/hooks/post_tool_use.py"
        hook_settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "$CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_use.py"
        
        merged_settings = merge_settings(existing_settings, hook_settings)
        
        # 設定ファイルの書き込み
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(merged_settings, f, indent=2, ensure_ascii=False)
        
        console.print(Panel(
            Text("インストールが完了しました！\n\n以下の機能が有効になりました:\n• ファイル編集前の新ブランチ作成\n• ファイル編集後の自動コミット", 
                 style="bold green"),
            title="🎉 成功",
            border_style="green"
        ))
        
    except OSError as e:
        console.print(f"[red]エラー: ファイル操作に失敗しました: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]予期しないエラーが発生しました: {e}[/red]")
        sys.exit(1)


def main() -> None:
    """CLIのメインエントリーポイント。"""
    cli()


if __name__ == "__main__":
    main()