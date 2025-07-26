#!/usr/bin/env python3
"""
PostToolUse hook for automatic commits after file edits.

This hook is triggered after Edit, Write, or MultiEdit tool calls and
automatically commits changes to the Jujutsu repository with an AI-generated summary.
"""

import json
import sys
import subprocess
import os
from pathlib import Path

# 言語設定の取得
LANGUAGE = os.environ.get("JJ_HOOK_LANGUAGE", "english")

# パッケージのインポートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from jj_hook.summarizer import JujutsuSummarizer, SummaryConfig
except ImportError:
    # フォールバック：スクリプトが単体で実行された場合
    msg = "警告: jj_hook パッケージをインポートできませんでした。スタンドアロンモードで実行します。" if LANGUAGE == "japanese" else "Warning: Could not import jj_hook package. Running in standalone mode."
    sys.stderr.write(f"{msg}\n")
    
    def create_fallback_summary(cwd: str) -> str:
        """フォールバック用の簡単なサマリー生成。"""
        try:
            result = subprocess.run(
                ["jj", "status"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and "No changes" not in result.stdout:
                return "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"
            else:
                return ""
        except Exception:
            return ""


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


def has_uncommitted_changes(cwd: str) -> bool:
    """コミットされていない変更があるかチェックする。"""
    try:
        result = subprocess.run(
            ["jj", "status"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            status_output = result.stdout.strip()
            return "No changes" not in status_output and len(status_output) > 0
        return False
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def commit_changes(cwd: str, message: str) -> tuple[bool, str]:
    """変更をコミットする。"""
    try:
        result = subprocess.run(
            ["jj", "commit", "-m", message],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, str(e)


def main() -> None:
    """メイン処理。"""
    try:
        # stdinからJSONデータを読み込み
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        msg = f"JSONデコードエラー: {e}" if LANGUAGE == "japanese" else f"JSON decode error: {e}"
        sys.stderr.write(f"{msg}\n")
        sys.exit(1)
    
    # フック情報の取得
    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", os.getcwd())
    
    # 対象のツールかチェック
    if tool_name not in ["Edit", "Write", "MultiEdit"]:
        sys.exit(0)
    
    # Jujutsuリポジトリかチェック
    if not is_jj_repository(cwd):
        msg = "Jujutsuリポジトリではありません。スキップします。" if LANGUAGE == "japanese" else "Not a Jujutsu repository. Skipping."
        sys.stderr.write(f"{msg}\n")
        sys.exit(0)
    
    # 変更があるかチェック
    if not has_uncommitted_changes(cwd):
        msg = "変更がありません。コミットをスキップします。" if LANGUAGE == "japanese" else "No changes found. Skipping commit."
        sys.stdout.write(f"{msg}\n")
        sys.exit(0)
    
    # サマリーを生成
    try:
        summarizer = JujutsuSummarizer()
        success, summary = summarizer.generate_commit_summary(cwd)
        
        if not success:
            # サマリー生成に失敗した場合
            error_msg = f"サマリー生成に失敗しました: {summary}" if LANGUAGE == "japanese" else f"Summary generation failed: {summary}"
            sys.stderr.write(f"{error_msg}\n")
            summary = "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"
            
    except NameError:
        # フォールバックモード
        summary = create_fallback_summary(cwd)
        if not summary:
            msg = "変更がありません。コミットをスキップします。" if LANGUAGE == "japanese" else "No changes found. Skipping commit."
            sys.stdout.write(f"{msg}\n")
            sys.exit(0)
    
    # コミット実行
    commit_success, commit_result = commit_changes(cwd, summary)
    
    if commit_success:
        success_msg = f"✅ 自動コミット完了: {summary}" if LANGUAGE == "japanese" else f"✅ Auto-commit completed: {summary}"
        sys.stdout.write(f"{success_msg}\n")
        if commit_result:
            sys.stdout.write(f"詳細: {commit_result}\n")
    else:
        error_msg = f"❌ コミットに失敗しました: {commit_result}" if LANGUAGE == "japanese" else f"❌ Commit failed: {commit_result}"
        sys.stderr.write(f"{error_msg}\n")
        # exit code 2 で Claude にエラーを報告
        sys.exit(2)


if __name__ == "__main__":
    main()