"""
PreToolUse hook for creating new revisions before file edits.

This hook is triggered before Edit, Write, or MultiEdit tool calls and
automatically creates a new Jujutsu revision with a descriptive name based on the intended changes.
"""

import json
import sys
import subprocess
import os
import re
from pathlib import Path

try:
    from ..summarizer import JujutsuSummarizer, SummaryConfig
except ImportError:
    # フォールバック：スクリプトが単体で実行された場合
    sys.stderr.write("警告: jj_hook パッケージをインポートできませんでした。スタンドアロンモードで実行します。\n")


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


def create_new_revision(cwd: str, revision_description: str) -> tuple[bool, str]:
    """新しいリビジョンを作成する。"""
    try:
        # jj new -m でリビジョン作成とコミットメッセージ設定を同時に行う
        result = subprocess.run(
            ["jj", "new", "-m", revision_description],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, str(e)


def should_create_revision_for_tool(tool_name: str, tool_input: dict) -> bool:
    """ツールの種類と入力から新しいリビジョンを作成すべきかどうか判断する。"""
    # 対象ツール以外はスキップ
    if tool_name not in ["Edit", "Write", "MultiEdit"]:
        return False
    
    # ファイルパスから判断（一時ファイルのみスキップ）
    file_path = tool_input.get("file_path", "")
    if file_path:
        # 一時ファイルや隠しファイルはスキップ
        if any(pattern in file_path.lower() for pattern in [
            "/tmp/", "/temp/", "/.claude/", "/.git/", 
            ".tmp", ".temp", ".cache"
        ]):
            return False
    
    # その他のファイルは基本的に作成（READMEなどを含む）
    return True


def generate_revision_description_from_tool(tool_name: str, tool_input: dict) -> str:
    """ツール情報から作業内容の説明を生成する。"""
    file_path = tool_input.get("file_path", "")
    
    # ファイル名から基本的な説明を作成
    base_description = ""
    if file_path:
        file_name = Path(file_path).name
        if tool_name == "Write":
            base_description = f"{file_name}を作成"
        elif tool_name == "Edit":
            base_description = f"{file_name}を修正"
        elif tool_name == "MultiEdit":
            base_description = f"{file_name}を更新"
    else:
        if tool_name == "Write":
            base_description = "新規ファイル作成"
        elif tool_name == "Edit":
            base_description = "ファイル修正"
        elif tool_name == "MultiEdit":
            base_description = "ファイル更新"
    
    # 内容から詳細を推測
    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    if content:
        content_lower = content.lower()
        
        # 特定のキーワードから作業内容を判断
        if any(keyword in content_lower for keyword in ["function", "def ", "class"]):
            base_description += " (関数・クラス追加)"
        elif any(keyword in content_lower for keyword in ["import", "require"]):
            base_description += " (依存関係追加)"
        elif any(keyword in content_lower for keyword in ["test", "spec"]):
            base_description += " (テスト追加)"
        elif any(keyword in content_lower for keyword in ["fix", "bug", "error"]):
            base_description += " (バグ修正)"
        elif any(keyword in content_lower for keyword in ["feature", "新機能"]):
            base_description += " (機能追加)"
        elif any(keyword in content_lower for keyword in ["refactor", "リファクタ"]):
            base_description += " (リファクタリング)"
    
    # 長すぎる場合は切り詰める
    if len(base_description) > 60:
        base_description = base_description[:57] + "..."
    
    return base_description




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
    
    # Jujutsuリポジトリかチェック
    if not is_jj_repository(cwd):
        sys.stderr.write("Jujutsuリポジトリではありません。スキップします。\n")
        sys.exit(0)
    
    # 新しいリビジョンを作成すべきかチェック
    if not should_create_revision_for_tool(tool_name, tool_input):
        sys.stdout.write("一時ファイルのため、新しいリビジョンは作成しません。\n")
        sys.exit(0)
    
    
    # リビジョンの説明を生成
    revision_description = generate_revision_description_from_tool(tool_name, tool_input)
    
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