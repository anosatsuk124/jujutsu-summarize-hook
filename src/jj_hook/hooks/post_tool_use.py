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

# パッケージのインポートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from jj_hook.summarizer import JujutsuSummarizer, SummaryConfig
except ImportError:
    # フォールバック：スクリプトが単体で実行された場合
    sys.stderr.write("警告: jj_hook パッケージをインポートできませんでした。スタンドアロンモードで実行します。\n")
    
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
                return "ファイルを編集"
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
        sys.stderr.write(f"JSONデコードエラー: {e}\n")
        sys.exit(1)
    
    # フック情報の取得
    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", os.getcwd())
    
    # 対象のツールかチェック
    if tool_name not in ["Edit", "Write", "MultiEdit"]:
        sys.exit(0)
    
    # Jujutsuリポジトリかチェック
    if not is_jj_repository(cwd):
        sys.stderr.write("Jujutsuリポジトリではありません。スキップします。\n")
        sys.exit(0)
    
    # 変更があるかチェック
    if not has_uncommitted_changes(cwd):
        sys.stdout.write("変更がありません。コミットをスキップします。\n")
        sys.exit(0)
    
    # サマリーを生成
    try:
        summarizer = JujutsuSummarizer()
        success, summary = summarizer.generate_commit_summary(cwd)
        
        if not success:
            # サマリー生成に失敗した場合
            sys.stderr.write(f"サマリー生成に失敗しました: {summary}\n")
            summary = "ファイルを編集"
            
    except NameError:
        # フォールバックモード
        summary = create_fallback_summary(cwd)
        if not summary:
            sys.stdout.write("変更がありません。コミットをスキップします。\n")
            sys.exit(0)
    
    # コミット実行
    commit_success, commit_result = commit_changes(cwd, summary)
    
    if commit_success:
        sys.stdout.write(f"✅ 自動コミット完了: {summary}\n")
        if commit_result:
            sys.stdout.write(f"詳細: {commit_result}\n")
    else:
        sys.stderr.write(f"❌ コミットに失敗しました: {commit_result}\n")
        # exit code 2 で Claude にエラーを報告
        sys.exit(2)


if __name__ == "__main__":
    main()