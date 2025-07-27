"""
PreToolUse hook for creating new revisions before file edits.

This hook is triggered before Edit, Write, or MultiEdit tool calls and
automatically creates a new Jujutsu revision with a descriptive name based on the intended changes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# 言語設定の取得
LANGUAGE = os.environ.get("JJ_HOOK_LANGUAGE", "english")

from ..template_loader import load_template
from ..vcs_backend import detect_vcs_backend, is_vcs_repository


def is_jj_repository(cwd: str) -> bool:
    """現在のディレクトリがVCSリポジトリかどうかチェックする（下位互換用）。"""
    return is_vcs_repository(cwd)


def create_new_revision(cwd: str, revision_description: str) -> tuple[bool, str]:
    """新しいリビジョン/ブランチを作成する。"""
    try:
        backend = detect_vcs_backend(cwd)
        if backend:
            return backend.create_branch("temp-branch", revision_description)
        else:
            return False, "VCSリポジトリが見つかりません"
    except Exception as e:
        return False, str(e)


def should_create_revision_for_tool(tool_name: str, tool_input: dict[str, str]) -> bool:
    """ツールの種類と入力から新しいリビジョンを作成すべきかどうか判断する。"""
    # 対象ツール以外はスキップ
    if tool_name not in ["Edit", "Write", "MultiEdit"]:
        return False

    # ファイルパスから判断（一時ファイルのみスキップ）
    file_path = tool_input.get("file_path", "")
    if file_path:
        # 一時ファイルや隠しファイルはスキップ
        if any(
            pattern in file_path.lower()
            for pattern in ["/tmp/", "/temp/", "/.claude/", "/.git/", ".tmp", ".temp", ".cache"]
        ):
            return False

    # その他のファイルは基本的に作成（READMEなどを含む）
    return True


def generate_revision_description_from_tool(tool_name: str, tool_input: dict[str, str], cwd: str) -> str:
    """ツール情報から作業内容の説明を生成する。"""
    file_path = tool_input.get("file_path", "")
    file_name = Path(file_path).name if file_path else ""
    
    # jj diffを取得
    diff_content = ""
    try:
        result = subprocess.run(
            ["jj", "diff"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            diff_content = result.stdout
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        description = load_template(
            "revision_description", 
            tool_name=tool_name, 
            file_name=file_name, 
            file_path=file_path,
            content_hints=diff_content
        )
    except (FileNotFoundError, ValueError) as e:
        # テンプレート読み込みに失敗した場合のフォールバック
        description = f"{tool_name} {file_name}"

    return description.strip()


def main() -> None:
    """メイン処理。"""
    try:
        # stdinからJSONデータを読み込み
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"JSONデコードエラー: {e}\n")
        sys.exit(1)

    # フック情報の取得
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd", os.getcwd())

    # 対象のツールかチェック
    if tool_name not in ["Edit", "Write", "MultiEdit"]:
        sys.exit(0)

    # VCSリポジトリかチェック
    if not is_jj_repository(cwd):
        sys.stderr.write("VCSリポジトリではありません。スキップします。\n")
        sys.exit(0)

    # 新しいリビジョンを作成すべきかチェック
    if not should_create_revision_for_tool(tool_name, tool_input):
        sys.stdout.write("一時ファイルのため、新しいリビジョンは作成しません。\n")
        sys.exit(0)

    # リビジョンの説明を生成
    revision_description = generate_revision_description_from_tool(tool_name, tool_input, cwd)

    # リビジョン作成実行
    revision_success, revision_result = create_new_revision(cwd, revision_description)

    if revision_success:
        sys.stdout.write(f"🌟 新しいリビジョンを作成しました: {revision_description}\n")
        if revision_result:
            sys.stdout.write(f"詳細: {revision_result}\n")
    else:
        # リビジョン作成に失敗してもエラーにはしない（警告のみ）
        sys.stderr.write(f"⚠️  リビジョン作成に失敗しました: {revision_result}\n")
        # 通常は exit(0) でツール処理を続行
        sys.exit(0)


if __name__ == "__main__":
    main()
