#!/usr/bin/env python3
"""vcs-cc-hook CLI implementation - VCS汎用（自動検出 + 明示指定）."""

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

from .summarizer import SummaryConfig, JujutsuSummarizer
from .template_loader import load_template
from .vcs_backend import VCSBackend, detect_vcs_backend

console = Console()


def create_fallback_summary(cwd: str, vcs_backend: Optional[VCSBackend] = None) -> str:
    """フォールバック用の簡単なサマリー生成。"""
    LANGUAGE = os.environ.get("VCS_CC_HOOK_LANGUAGE", "japanese")
    backend = vcs_backend or detect_vcs_backend(cwd)
    if backend and backend.has_uncommitted_changes():
        return "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"
    else:
        return ""


def check_github_copilot_auth() -> tuple[bool, str]:
    """GitHub Copilot認証状態をチェックする。"""
    try:
        import litellm

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

        console.print("\n[blue]GitHub Copilot認証を開始します...[/blue]")

        summarizer = JujutsuSummarizer()
        if not summarizer.config.model.startswith("github_copilot/"):
            console.print(
                "[yellow]警告: VCS_CC_HOOK_MODELがGitHub Copilotモデルに設定されていません[/yellow]"
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


def get_slash_command_content(language: str = "japanese") -> str:
    """Generate Markdown content for slash command from template file."""
    try:
        return load_template("slash_command", language=language)
    except Exception:
        # Fallback to hardcoded content if template file not found
        if language == "japanese":
            return """vcs-commit-organizerサブエージェントを使ってコミット履歴を分析し、適切に整理してください。

VCS log と VCS diff でコミット履歴を確認し、関連するコミットをまとめたり、意味のあるコミットメッセージに変更するなど、論理的な整理を行ってください。

具体的には：
1. 現在のコミット履歴を確認
2. 統合すべきコミットや分離すべき変更を特定
3. VCS固有のコマンドを使った整理の提案
4. ユーザーの確認後に実際の整理作業を実行

安全のため、作業前にバックアップブランチの作成も行ってください。"""
        else:  # english
            return """Use the vcs-commit-organizer sub-agent to analyze and organize the commit history appropriately.

Please review the commit history using VCS log and diff commands, then logically organize it by grouping related commits and creating meaningful commit messages.

Specifically:
1. Check the current commit history
2. Identify commits to merge or changes to separate
3. Propose organization using VCS-specific commands
4. Execute actual organization work after user confirmation

For safety, please create a backup branch before starting work."""


def get_vcs_backend(cwd: str, vcs_type: Optional[str] = None) -> Optional[VCSBackend]:
    """VCSバックエンドを取得する（明示指定 or 自動検出）。"""
    if vcs_type:
        # 明示的に指定された場合
        if vcs_type == "git":
            from .git_backend import GitBackend
            backend: VCSBackend = GitBackend(cwd)
            if backend.is_repository():
                return backend
        elif vcs_type == "jj":
            from .jujutsu_backend import JujutsuBackend
            backend = JujutsuBackend(cwd)
            if backend.is_repository():
                return backend
        return None
    else:
        # 自動検出
        return detect_vcs_backend(cwd)


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
    """VCS汎用フック設定を生成する。"""
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": "vcs-cc-hook post-tool-use", "timeout": 30}
                    ],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Edit|Write|MultiEdit",
                    "hooks": [
                        {"type": "command", "command": "vcs-cc-hook pre-tool-use", "timeout": 15}
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

        # 既存のvcs-cc-hookフックを削除（重複回避）
        merged["hooks"][event_name] = [
            hook
            for hook in merged["hooks"][event_name]
            if not any("vcs-cc-hook" in cmd.get("command", "") for cmd in hook.get("hooks", []))
        ]

        merged["hooks"][event_name].extend(hooks_list)

    return merged


@click.group()
@click.version_option()
def cli() -> None:
    """VCS汎用のClaude Codeフック（Git/Jujutsu自動検出）."""
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
    """vcs-cc-hookをClaude Code設定に追加する。"""

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
                    "vcs-cc-hook (VCS汎用) のインストールが完了しました！\n\n"
                    "有効になった機能:\n"
                    "• Git/Jujutsu自動検出\n"
                    "• ファイル編集前の新ブランチ/リビジョン作成 (PreToolUse)\n"
                    "• ファイル編集後の自動コミット (PostToolUse)\n\n"
                    "コマンド:\n"
                    "• vcs-cc-hook post-tool-use [--vcs git|jj]\n"
                    "• vcs-cc-hook pre-tool-use [--vcs git|jj]",
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
@click.option("--vcs", type=click.Choice(["git", "jj"]), help="VCSタイプを明示指定")
def post_tool_use(vcs: Optional[str]) -> None:
    """PostToolUse フックを実行する（VCS汎用）。"""
    from .hooks.post_tool_use import main as post_tool_use_main

    try:
        # VCSタイプを環境変数に設定（明示指定または自動検出）
        if vcs:
            os.environ["VCS_TYPE"] = vcs
        post_tool_use_main()
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]PostToolUse フックでエラーが発生しました: {e}[/red]")
        sys.exit(2)


@cli.command(name="pre-tool-use")
@click.option("--vcs", type=click.Choice(["git", "jj"]), help="VCSタイプを明示指定")
def pre_tool_use(vcs: Optional[str]) -> None:
    """PreToolUse フックを実行する（VCS汎用）。"""
    from .hooks.pre_tool_use import main as pre_tool_use_main

    try:
        # VCSタイプを環境変数に設定（明示指定または自動検出）
        if vcs:
            os.environ["VCS_TYPE"] = vcs
        pre_tool_use_main()
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        console.print(f"[red]PreToolUse フックでエラーが発生しました: {e}[/red]")
        sys.exit(2)


@cli.command(name="summarize")
@click.option("--vcs", type=click.Choice(["git", "jj"]), help="VCSタイプを明示指定")
def summarize(vcs: Optional[str]) -> None:
    """AIを使用して変更を要約し、コミット/リビジョンを作成する。"""
    cwd = os.getcwd()
    LANGUAGE = os.environ.get("VCS_CC_HOOK_LANGUAGE", "japanese")

    try:
        backend = get_vcs_backend(cwd, vcs)

        if not backend:
            if vcs:
                msg = (
                    f"{vcs.upper()}リポジトリではありません。スキップします。"
                    if LANGUAGE == "japanese"
                    else f"Not a {vcs.upper()} repository. Skipping."
                )
            else:
                msg = (
                    "VCSリポジトリが見つかりません。スキップします。"
                    if LANGUAGE == "japanese"
                    else "No VCS repository found. Skipping."
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

        # VCSタイプに応じたメッセージ
        vcs_name = "Git" if isinstance(backend, type(backend)) and "git" in str(type(backend)).lower() else "Jujutsu"
        action = "コミットメッセージ" if "git" in str(type(backend)).lower() else "リビジョン説明"

        console.print(f"[blue]AIが{action}を生成中...[/blue]")

        try:
            from .summarizer import JujutsuSummarizer

            # VCS汎用の設定で初期化
            config = SummaryConfig()
            config.model = os.environ.get("VCS_CC_HOOK_MODEL", config.model)
            config.prompt_language = LANGUAGE

            summarizer = JujutsuSummarizer(config)
            success, summary = summarizer.generate_commit_summary(cwd)

            if not success:
                console.print(f"[red]サマリー生成に失敗しました: {summary}[/red]")
                summary = create_fallback_summary(cwd, backend)
                if not summary:
                    console.print("[yellow]変更がありません。コミットをスキップします。[/yellow]")
                    sys.exit(0)

        except Exception as e:
            console.print(f"[red]予期しないエラー: {e}[/red]")
            summary = create_fallback_summary(cwd, backend)
            if not summary:
                console.print("[yellow]変更がありません。コミットをスキップします。[/yellow]")
                sys.exit(0)

        commit_success, commit_result = backend.commit_changes(summary)

        if commit_success:
            action_done = "コミット" if "git" in str(type(backend)).lower() else "リビジョン作成"
            console.print(f"[green]✅ 自動{action_done}完了: {summary}[/green]")
            if commit_result:
                console.print(f"詳細: {commit_result}")
        else:
            action_failed = "コミット" if "git" in str(type(backend)).lower() else "リビジョン作成"
            console.print(f"[red]❌ {action_failed}に失敗しました: {commit_result}[/red]")
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
    """LLMプロバイダーの認証を行う。

    PROVIDER: 認証するプロバイダー (github-copilot)

    例:
    \b
    vcs-cc-hook auth github-copilot    # GitHub Copilot認証を実行
    vcs-cc-hook auth --check           # 認証状態を確認
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
                    "\n[yellow]認証を行うには: [bold]vcs-cc-hook auth github-copilot[/bold][/yellow]"
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
            model = os.environ.get("VCS_CC_HOOK_MODEL", "未設定")
            console.print(f"[dim]現在のモデル設定: {model}[/dim]")

            if model != "github_copilot/gpt-4":
                console.print("[yellow]推奨設定:[/yellow]")
                console.print('[dim]export VCS_CC_HOOK_MODEL="github_copilot/gpt-4"[/dim]\n')

            success = authenticate_github_copilot()

            if success:
                console.print(
                    Panel(
                        Text(
                            "🎉 GitHub Copilot認証が正常に完了しました！\n\nvcs-cc-hook のAI機能を使用できます。",
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
    """vcs-commit-organizerサブエージェントをClaude Code設定に追加する。"""

    # 言語設定の取得
    language = os.environ.get("VCS_CC_HOOK_LANGUAGE", "english")

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
        agent_file = agents_dir / "vcs-commit-organizer.md"

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
                    "🤖 vcs-commit-organizer サブエージェントのインストールが完了しました！\n\n"
                    "使用方法:\n"
                    "• Claude Code で「vcs-commit-organizer サブエージェントを使ってコミット履歴を整理して」\n"
                    "• 「コミット履歴を確認して適切に整理してください」\n\n"
                    "機能:\n"
                    "• VCS log と diff による履歴分析\n"
                    "• VCS固有コマンドによる自動整理\n"
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
    """vcs-commit-organizerを呼び出すslash command（/vcs-commit-organizer）をClaude Code設定に追加する。"""

    # 言語設定の取得
    language = os.environ.get("VCS_CC_HOOK_LANGUAGE", "japanese")

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
        command_file = slash_commands_dir / "vcs-commit-organizer.md"

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
                        "⚡ /vcs-commit-organizer slash command のインストールが完了しました！\n\n"
                        f"{usage_label}:\n"
                        "• Claude Code で「/vcs-commit-organizer」と入力\n"
                        "• vcs-commit-organizer サブエージェントが自動呼び出し\n"
                        "• コミット履歴の分析と整理を実行\n\n"
                        f"{function_label}:\n"
                        "• VCS log と diff による履歴分析\n"
                        "• VCS固有コマンドによる自動整理\n"
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
                        "⚡ /vcs-commit-organizer slash command has been installed successfully!\n\n"
                        f"{usage_label}:\n"
                        '• Type "/vcs-commit-organizer" in Claude Code\n'
                        "• Automatically invokes vcs-commit-organizer sub-agent\n"
                        "• Executes commit history analysis and organization\n\n"
                        f"{function_label}:\n"
                        "• History analysis using VCS log and diff\n"
                        "• Automatic organization with VCS-specific commands\n"
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


@cli.command(name="detect")
def detect() -> None:
    """現在のディレクトリのVCSタイプを検出・表示する。"""
    cwd = os.getcwd()
    backend = detect_vcs_backend(cwd)

    if backend:
        vcs_type = "Jujutsu" if "jujutsu" in str(type(backend)).lower() else "Git"
        console.print(f"[green]検出されたVCS: {vcs_type}[/green]")
        console.print(f"[dim]パス: {cwd}[/dim]")

        # 追加情報
        if backend.has_uncommitted_changes():
            console.print("[yellow]• 未コミットの変更があります[/yellow]")
        else:
            console.print("[dim]• 変更はありません[/dim]")
    else:
        console.print("[red]VCSリポジトリが見つかりません[/red]")
        console.print(f"[dim]パス: {cwd}[/dim]")


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
    """vcs-cc-hook の全機能（hooks, sub-agent, slash command）を一括インストールする。"""

    # 言語設定の取得
    language = os.environ.get("VCS_CC_HOOK_LANGUAGE", "japanese")

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
                Text("🚀 vcs-cc-hook 一括インストールを開始します", style="bold blue"),
                title="一括インストール",
                border_style="blue",
            )
        )
        console.print(f"[blue]インストール先: {install_location}[/blue]")
        console.print(f"[dim]DRY-RUNモード: {'有効' if dry_run else '無効'}[/dim]\n")
    else:
        console.print(
            Panel(
                Text("🚀 Starting vcs-cc-hook bulk installation", style="bold blue"),
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
            if not dry_run:
                # hookのインストールロジックを実行
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
                agent_file = agents_dir / "vcs-commit-organizer.md"

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
                command_file = slash_commands_dir / "vcs-commit-organizer.md"

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
                    summary_text += "\n• vcs-commit-organizer サブエージェント"
                if any(
                    name == "Slash Command" and success for name, success, _ in installation_results
                ):
                    summary_text += "\n• /vcs-commit-organizer コマンド"
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
                    summary_text += "\n• vcs-commit-organizer sub-agent"
                if any(
                    name == "Slash Command" and success for name, success, _ in installation_results
                ):
                    summary_text += "\n• /vcs-commit-organizer command"

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


def main() -> None:
    """CLIのメインエントリーポイント。"""
    cli()


if __name__ == "__main__":
    main()
