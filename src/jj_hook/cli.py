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


def main() -> None:
    """CLIのメインエントリーポイント。"""
    cli()


if __name__ == "__main__":
    main()