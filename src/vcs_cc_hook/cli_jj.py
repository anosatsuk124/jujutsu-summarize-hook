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

from .jujutsu_backend import JujutsuBackend

console = Console()


def check_github_copilot_auth() -> tuple[bool, str]:
    """GitHub Copilot認証状態をチェックする。"""
    try:
        import litellm
        
        # 軽量なテストリクエストで認証状態を確認
        from .summarizer import JujutsuSummarizer, SummaryConfig
        config = SummaryConfig()
        
        # JJ専用環境変数を優先チェック
        model_env = (
            os.environ.get("JJ_CC_HOOK_MODEL") or
            os.environ.get("VCS_CC_HOOK_MODEL") or
            os.environ.get("JJ_HOOK_MODEL")  # 下位互換
        )
        if model_env:
            config.model = model_env
            
        summarizer = JujutsuSummarizer(config=config)
        if not config.model.startswith("github_copilot/"):
            return False, "GitHub Copilotモデルが設定されていません"
        
        # 短いテストリクエスト
        response = litellm.completion(
            model=config.model,
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

        console.print("\n[blue]GitHub Copilot認証を開始します...[/blue]")
        
        from .summarizer import JujutsuSummarizer, SummaryConfig
        config = SummaryConfig()
        
        # JJ専用環境変数を優先チェック
        model_env = (
            os.environ.get("JJ_CC_HOOK_MODEL") or
            os.environ.get("VCS_CC_HOOK_MODEL") or
            os.environ.get("JJ_HOOK_MODEL")  # 下位互換
        )
        if model_env:
            config.model = model_env
            
        summarizer = JujutsuSummarizer(config=config)
        if not config.model.startswith("github_copilot/"):
            console.print(
                "[yellow]警告: JJ_CC_HOOK_MODELがGitHub Copilotモデルに設定されていません[/yellow]"
            )
            console.print(f"現在の設定: {config.model}")
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


def get_slash_command_content(template_name: str = "slash_command") -> str:
    """スラッシュコマンドの内容を取得する。"""
    from .template_loader import TemplateLoader
    
    template_loader = TemplateLoader(vcs_type="jj")
    
    # テンプレートから内容を読み込み
    try:
        content = template_loader.load_template(template_name)
        return content
    except FileNotFoundError:
        # フォールバック内容
        return """# Jujutsu Commit Organizer

このサブエージェントを実行する:

```
jj-cc-hook organize
```

このサブエージェントはJujutsuリポジトリのコミット履歴を解析し、整理の提案を行います。
"""


def create_fallback_summary(cwd: str) -> str:
    """フォールバック用の簡単なサマリー生成。"""
    language = os.environ.get("JJ_CC_HOOK_LANGUAGE", "japanese")
    backend = JujutsuBackend(cwd)
    if backend.is_repository() and backend.has_uncommitted_changes():
        return "ファイルを編集" if language == "japanese" else "Edit files"
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
    language = os.environ.get("JJ_CC_HOOK_LANGUAGE", "japanese")

    try:
        backend = JujutsuBackend(cwd)

        if not backend.is_repository():
            msg = (
                "Jujutsuリポジトリではありません。スキップします。"
                if language == "japanese"
                else "Not a Jujutsu repository. Skipping."
            )
            console.print(f"[red]{msg}[/red]")
            sys.exit(0)

        if not backend.has_uncommitted_changes():
            msg = (
                "変更がありません。コミットをスキップします。"
                if language == "japanese"
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


@cli.command()
@click.argument(
    "provider", type=click.Choice(["github-copilot"]), required=False, default="github-copilot"
)
@click.option("--check", "-c", is_flag=True, help="認証状態のみ確認")
def auth(provider: str, check: bool) -> None:
    """LLMプロバイダーの認証を行う（Jujutsu専用）。
    
    PROVIDER: 認証するプロバイダー (github-copilot)
    
    例:
    \b
    jj-cc-hook auth github-copilot    # GitHub Copilot認証を実行
    jj-cc-hook auth --check           # 認証状態を確認
    """
    if check:
        console.print("[blue]認証状態を確認中...[/blue]")
        
        if provider == "github-copilot":
            is_authenticated, status = check_github_copilot_auth()
            
            if is_authenticated:
                console.print(f"[green]✅ GitHub Copilot: {status}[/green]")
            else:
                console.print(f"[red]❌ GitHub Copilot: {status}[/red]")
        
        return

    if provider == "github-copilot":
        console.print(f"[blue]🔐 {provider} 認証を開始します[/blue]")
        
        success = authenticate_github_copilot()
        
        if success:
            console.print("[green]✅ 認証が完了しました！[/green]")
            console.print("[dim]これで jj-cc-hook を使用する準備が整いました。[/dim]")
        else:
            console.print("[red]❌ 認証に失敗しました[/red]")
            sys.exit(1)


@cli.command(name="install-agent")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="グローバル設定（~/.claude/）にインストール",
)
@click.option("--dry-run", is_flag=True, help="実際の変更は行わず、変更内容のプレビューのみ表示")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
)
def install_agent(is_global: bool, dry_run: bool, path: Optional[Path]) -> None:
    """Jujutsu専用のサブエージェント (jj-commit-organizer) をClaude Codeに追加する。"""
    
    if is_global and path:
        console.print("[red]エラー: --globalと--pathは同時に指定できません[/red]")
        sys.exit(1)

    if is_global:
        agents_dir = Path.home() / ".claude" / "agents"
        install_location = "グローバル設定"
    else:
        target_path = path if path is not None else Path.cwd()
        claude_dir = create_claude_settings_dir(target_path)
        agents_dir = claude_dir / "agents"
        install_location = f"ローカル設定 ({target_path})"

    agent_file = agents_dir / "jj-commit-organizer.md"

    console.print(f"[blue]インストール先: {install_location}[/blue]")
    console.print(f"[dim]エージェントファイル: {agent_file}[/dim]")

    try:
        # エージェント内容を取得
        from .template_loader import TemplateLoader
        template_loader = TemplateLoader(vcs_type="jj")
        try:
            agent_content = template_loader.load_template("agent_content")
        except FileNotFoundError:
            # フォールバック内容
            agent_content = """# jj-commit-organizer

Jujutsuリポジトリのコミット履歴を解析し、コミットの整理を提案するサブエージェントです。

## 主な機能

- コミット履歴の解析
- 小さなコミットの統合提案
- 関連するコミットのグループ化
- コミット整理の実行

## 使用方法

このサブエージェントを実行してください:

```
jj-cc-hook analyze --interactive
```

または、直接呼び出し:

```
Task(description="jj-commit-organizer でコミット履歴を整理", prompt="Jujutsuリポジトリのコミット履歴を解析し、整理の提案をお願いします", subagent_type="jj-commit-organizer")
```
"""

        if dry_run:
            console.print("\n[yellow]作成予定の内容:[/yellow]")
            console.print(agent_content)
            console.print(
                "\n[dim]実際に作成するには --dry-run オプションを外して実行してください[/dim]"
            )
            return

        agents_dir.mkdir(parents=True, exist_ok=True)

        with open(agent_file, "w", encoding="utf-8") as f:
            f.write(agent_content)

        console.print(
            Panel(
                Text(
                    "jj-commit-organizer サブエージェントのインストールが完了しました！\n\n"
                    "使用方法:\n"
                    "• Claude Code内で 'jj-commit-organizer' と呼び出し\n"
                    "• Task(subagent_type=\"jj-commit-organizer\") でプログラム的に実行\n"
                    "• /jj-commit-organizer スラッシュコマンド（別途インストール要）\n\n"
                    f"インストール先: {agent_file}",
                    style="bold green",
                ),
                title="🎉 サブエージェント インストール成功",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[red]エラーが発生しました: {e}[/red]")
        sys.exit(1)


@cli.command(name="install-slash-command")
@click.option(
    "--global",
    "is_global", 
    is_flag=True,
    help="グローバル設定（~/.claude/）にインストール",
)
@click.option("--dry-run", is_flag=True, help="実際の変更は行わず、変更内容のプレビューのみ表示")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
)
def install_slash_command(is_global: bool, dry_run: bool, path: Optional[Path]) -> None:
    """Jujutsu専用のスラッシュコマンド (/jj-commit-organizer) をClaude Codeに追加する。"""
    
    if is_global and path:
        console.print("[red]エラー: --globalと--pathは同時に指定できません[/red]")
        sys.exit(1)

    if is_global:
        slash_commands_dir = Path.home() / ".claude" / "slash_commands"
        install_location = "グローバル設定"
    else:
        target_path = path if path is not None else Path.cwd()
        claude_dir = create_claude_settings_dir(target_path)
        slash_commands_dir = claude_dir / "slash_commands"
        install_location = f"ローカル設定 ({target_path})"

    slash_command_file = slash_commands_dir / "jj-commit-organizer.md"

    console.print(f"[blue]インストール先: {install_location}[/blue]")
    console.print(f"[dim]スラッシュコマンドファイル: {slash_command_file}[/dim]")

    try:
        # スラッシュコマンド内容を取得
        slash_command_content = get_slash_command_content()

        if dry_run:
            console.print("\n[yellow]作成予定の内容:[/yellow]")
            console.print(slash_command_content)
            console.print(
                "\n[dim]実際に作成するには --dry-run オプションを外して実行してください[/dim]"
            )
            return

        slash_commands_dir.mkdir(parents=True, exist_ok=True)

        with open(slash_command_file, "w", encoding="utf-8") as f:
            f.write(slash_command_content)

        console.print(
            Panel(
                Text(
                    "/jj-commit-organizer スラッシュコマンドのインストールが完了しました！\n\n"
                    "使用方法:\n"
                    "• Claude Code内で '/jj-commit-organizer' と入力\n"
                    "• 自動的にJujutsuコミット整理機能が実行されます\n\n"
                    f"インストール先: {slash_command_file}",
                    style="bold green",
                ),
                title="🎉 スラッシュコマンド インストール成功",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(f"[red]エラーが発生しました: {e}[/red]")
        sys.exit(1)


@cli.command(name="install-all")
@click.option(
    "--global",
    "is_global",
    is_flag=True,
    help="グローバル設定（~/.claude/）にインストール",
)
@click.option("--dry-run", is_flag=True, help="実際の変更は行わず、変更内容のプレビューのみ表示")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help="インストール先のディレクトリパス（--globalと併用不可）",
)
def install_all(is_global: bool, dry_run: bool, path: Optional[Path]) -> None:
    """Jujutsu専用のすべてのコンポーネント（フック、サブエージェント、スラッシュコマンド）を一括インストールする。"""
    
    if is_global and path:
        console.print("[red]エラー: --globalと--pathは同時に指定できません[/red]")
        sys.exit(1)

    install_location = "グローバル設定" if is_global else f"ローカル設定 ({path or Path.cwd()})"
    
    console.print(f"[blue]🚀 jj-cc-hook 一括インストールを開始します[/blue]")
    console.print(f"[blue]インストール先: {install_location}[/blue]")
    
    if dry_run:
        console.print("\n[yellow]⚠️  ドライランモード - 実際の変更は行いません[/yellow]")

    try:
        # 1. フックのインストール
        console.print("\n[cyan]1. Claude Code フックのインストール...[/cyan]")
        
        # install コマンドの処理を直接実行
        if is_global:
            settings_file = Path.home() / ".claude" / "settings.json"
        else:
            target_path = path if path is not None else Path.cwd()
            claude_dir = create_claude_settings_dir(target_path)
            settings_file = claude_dir / "settings.json"

        existing_settings = get_existing_settings(settings_file)
        hook_settings = create_hook_settings()
        merged_settings = merge_settings(existing_settings, hook_settings)

        if not dry_run:
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(merged_settings, f, indent=2, ensure_ascii=False)
        
        console.print("   [green]✅ フックのインストール完了[/green]")

        # 2. サブエージェントのインストール
        console.print("\n[cyan]2. サブエージェント (jj-commit-organizer) のインストール...[/cyan]")
        
        if is_global:
            agents_dir = Path.home() / ".claude" / "agents"
        else:
            target_path = path if path is not None else Path.cwd()
            claude_dir = create_claude_settings_dir(target_path) 
            agents_dir = claude_dir / "agents"

        agent_file = agents_dir / "jj-commit-organizer.md"

        from .template_loader import TemplateLoader
        template_loader = TemplateLoader(vcs_type="jj")
        try:
            agent_content = template_loader.load_template("agent_content")
        except FileNotFoundError:
            agent_content = """# jj-commit-organizer

Jujutsuリポジトリのコミット履歴を解析し、コミットの整理を提案するサブエージェントです。

## 使用方法

このサブエージェントを実行してください:

```
jj-cc-hook analyze --interactive
```
"""

        if not dry_run:
            agents_dir.mkdir(parents=True, exist_ok=True)
            with open(agent_file, "w", encoding="utf-8") as f:
                f.write(agent_content)
        
        console.print("   [green]✅ サブエージェントのインストール完了[/green]")

        # 3. スラッシュコマンドのインストール
        console.print("\n[cyan]3. スラッシュコマンド (/jj-commit-organizer) のインストール...[/cyan]")
        
        if is_global:
            slash_commands_dir = Path.home() / ".claude" / "slash_commands"
        else:
            target_path = path if path is not None else Path.cwd()
            claude_dir = create_claude_settings_dir(target_path)
            slash_commands_dir = claude_dir / "slash_commands"

        slash_command_file = slash_commands_dir / "jj-commit-organizer.md"
        slash_command_content = get_slash_command_content()

        if not dry_run:
            slash_commands_dir.mkdir(parents=True, exist_ok=True)
            with open(slash_command_file, "w", encoding="utf-8") as f:
                f.write(slash_command_content)
        
        console.print("   [green]✅ スラッシュコマンドのインストール完了[/green]")

        # 完了メッセージ
        console.print(
            Panel(
                Text(
                    "🎉 jj-cc-hook (Jujutsu専用) の一括インストールが完了しました！\n\n"
                    "インストールされたコンポーネント:\n"
                    "✅ Claude Code フック (PreToolUse, PostToolUse)\n"
                    "✅ jj-commit-organizer サブエージェント\n"
                    "✅ /jj-commit-organizer スラッシュコマンド\n\n"
                    "使用方法:\n"
                    "• ファイル編集で自動フック実行\n"
                    "• Claude Code内で 'jj-commit-organizer' と呼び出し\n"
                    "• '/jj-commit-organizer' スラッシュコマンド実行\n"
                    "• jj-cc-hook auth github-copilot (認証設定)\n\n"
                    f"インストール先: {install_location}",
                    style="bold green",
                ),
                title="🚀 一括インストール成功",
                border_style="green",
            )
        )

        if dry_run:
            console.print("\n[yellow]💡 実際にインストールするには --dry-run オプションを外して再実行してください[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ インストール中にエラーが発生しました: {e}[/red]")
        sys.exit(1)


def main() -> None:
    """CLIのメインエントリーポイント。"""
    cli()


if __name__ == "__main__":
    main()
