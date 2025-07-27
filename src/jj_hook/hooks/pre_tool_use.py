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

# 言語設定の取得
LANGUAGE = os.environ.get("JJ_HOOK_LANGUAGE", "english")

try:
    from ..summarizer import JujutsuSummarizer, SummaryConfig
    from ..template_loader import load_template
except ImportError:
    # フォールバック：スクリプトが単体で実行された場合
    warning_msg = "警告: jj_hook パッケージをインポートできませんでした。スタンドアロンモードで実行します。\n" if LANGUAGE == "japanese" else "Warning: Could not import jj_hook package. Running in standalone mode.\n"
    sys.stderr.write(warning_msg)
    load_template = None


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
    if load_template is None:
        # フォールバックモード：従来のロジックを使用
        file_path = tool_input.get("file_path", "")
        
        # ファイル名から基本的な説明を作成
        base_description = ""
        if file_path:
            file_name = Path(file_path).name
            if tool_name == "Write":
                base_description = f"{file_name}を作成" if LANGUAGE == "japanese" else f"Create {file_name}"
            elif tool_name == "Edit":
                base_description = f"{file_name}を修正" if LANGUAGE == "japanese" else f"Edit {file_name}"
            elif tool_name == "MultiEdit":
                base_description = f"{file_name}を更新" if LANGUAGE == "japanese" else f"Update {file_name}"
        else:
            if tool_name == "Write":
                base_description = "新規ファイル作成" if LANGUAGE == "japanese" else "Create new file"
            elif tool_name == "Edit":
                base_description = "ファイル修正" if LANGUAGE == "japanese" else "Edit file"
            elif tool_name == "MultiEdit":
                base_description = "ファイル更新" if LANGUAGE == "japanese" else "Update file"
        
        # 内容から詳細を推測
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        if content:
            content_lower = content.lower()
            
            # 特定のキーワードから作業内容を判断
            if any(keyword in content_lower for keyword in ["function", "def ", "class"]):
                base_description += " (関数・クラス追加)" if LANGUAGE == "japanese" else " (add functions/classes)"
            elif any(keyword in content_lower for keyword in ["import", "require"]):
                base_description += " (依存関係追加)" if LANGUAGE == "japanese" else " (add dependencies)"
            elif any(keyword in content_lower for keyword in ["test", "spec"]):
                base_description += " (テスト追加)" if LANGUAGE == "japanese" else " (add tests)"
            elif any(keyword in content_lower for keyword in ["fix", "bug", "error"]):
                base_description += " (バグ修正)" if LANGUAGE == "japanese" else " (bug fix)"
            elif any(keyword in content_lower for keyword in ["feature", "新機能"]):
                base_description += " (機能追加)" if LANGUAGE == "japanese" else " (add feature)"
            elif any(keyword in content_lower for keyword in ["refactor", "リファクタ"]):
                base_description += " (リファクタリング)" if LANGUAGE == "japanese" else " (refactoring)"
        
        # 長すぎる場合は切り詰める
        if len(base_description) > 60:
            base_description = base_description[:57] + "..."
        
        return base_description
    
    try:
        # テンプレートモード
        file_path = tool_input.get("file_path", "")
        file_name = Path(file_path).name if file_path else ""
        
        # 内容解析のヒント生成
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        content_hints = ""
        if content:
            content_lower = content.lower()
            hints = []
            
            if any(keyword in content_lower for keyword in ["function", "def ", "class"]):
                hints.append("functions/classes")
            if any(keyword in content_lower for keyword in ["import", "require"]):
                hints.append("dependencies")
            if any(keyword in content_lower for keyword in ["test", "spec"]):
                hints.append("tests")
            if any(keyword in content_lower for keyword in ["fix", "bug", "error"]):
                hints.append("bug fix")
            if any(keyword in content_lower for keyword in ["feature", "新機能"]):
                hints.append("feature")
            if any(keyword in content_lower for keyword in ["refactor", "リファクタ"]):
                hints.append("refactoring")
            
            if hints:
                content_hints = f"Content includes: {', '.join(hints)}"
        
        # テンプレートを使用して説明を生成
        description = load_template(
            "revision_description",
            tool_name=tool_name,
            file_name=file_name,
            file_path=file_path,
            content_hints=content_hints
        )
        
        return description.strip()
        
    except Exception:
        # テンプレート使用に失敗した場合はフォールバックモード
        return generate_revision_description_from_tool.__wrapped__(tool_name, tool_input)

# フォールバック用の元の関数を保存
generate_revision_description_from_tool.__wrapped__ = lambda tool_name, tool_input: "Edit file"




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