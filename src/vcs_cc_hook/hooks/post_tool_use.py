"""
PostToolUse hook for automatic commits after file edits.

This hook is triggered after Edit, Write, or MultiEdit tool calls and
automatically commits changes to the Jujutsu repository with an AI-generated summary.
"""

import json
import os
import subprocess
import sys

# 言語設定の取得
LANGUAGE = os.environ.get("JJ_HOOK_LANGUAGE", "english")

# インポート状態の追跡
IMPORT_SUCCESS = True
IMPORT_ERROR = None

try:
    from jj_hook.summarizer import JujutsuSummarizer, SummaryConfig
    from jj_hook.vcs_backend import detect_vcs_backend, is_vcs_repository
except ImportError as e:
    IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)
    try:
        from ..summarizer import JujutsuSummarizer, SummaryConfig
        from ..vcs_backend import detect_vcs_backend, is_vcs_repository

        IMPORT_SUCCESS = True
        IMPORT_ERROR = None
    except ImportError as e2:
        IMPORT_SUCCESS = False
        IMPORT_ERROR = str(e2)

    def create_fallback_summary(cwd: str) -> str:
        """フォールバック用の簡単なサマリー生成。"""
        try:
            backend = detect_vcs_backend(cwd)
            if backend and backend.has_uncommitted_changes():
                return "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"
            else:
                return ""
        except Exception:
            return ""


def is_jj_repository(cwd: str) -> bool:
    """現在のディレクトリがVCSリポジトリかどうかチェックする（下位互換用）。"""
    return is_vcs_repository(cwd)


def has_uncommitted_changes(cwd: str) -> bool:
    """コミットされていない変更があるかチェックする。"""
    try:
        backend = detect_vcs_backend(cwd)
        return backend is not None and backend.has_uncommitted_changes()
    except Exception:
        return False


def commit_changes(cwd: str, message: str) -> tuple[bool, str]:
    """変更をコミットする。"""
    try:
        backend = detect_vcs_backend(cwd)
        if backend:
            return backend.commit_changes(message)
        else:
            return False, "VCSリポジトリが見つかりません"
    except Exception as e:
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

    # VCSリポジトリかチェック
    if not is_jj_repository(cwd):
        msg = (
            "VCSリポジトリではありません。スキップします。"
            if LANGUAGE == "japanese"
            else "Not a VCS repository. Skipping."
        )
        sys.stderr.write(f"{msg}\n")
        sys.exit(0)

    # 変更があるかチェック
    if not has_uncommitted_changes(cwd):
        msg = (
            "変更がありません。コミットをスキップします。"
            if LANGUAGE == "japanese"
            else "No changes found. Skipping commit."
        )
        sys.stdout.write(f"{msg}\n")
        sys.exit(0)

    # サマリーを生成
    if not IMPORT_SUCCESS:
        # インポートが失敗していた場合はフォールバックモード
        debug_msg = (
            f"デバッグ: インポートエラーのためフォールバック実行 ({IMPORT_ERROR})"
            if LANGUAGE == "japanese"
            else f"Debug: Fallback due to import error ({IMPORT_ERROR})"
        )
        sys.stderr.write(f"{debug_msg}\n")
        summary = create_fallback_summary(cwd)
        if not summary:
            msg = (
                "変更がありません。コミットをスキップします。"
                if LANGUAGE == "japanese"
                else "No changes found. Skipping commit."
            )
            sys.stdout.write(f"{msg}\n")
            sys.exit(0)
    else:
        try:
            # 環境変数をデバッグ出力
            model = os.environ.get("JJ_HOOK_MODEL", "gpt-3.5-turbo")
            debug_msg = (
                f"デバッグ: 使用モデル = {model}"
                if LANGUAGE == "japanese"
                else f"Debug: Using model = {model}"
            )
            sys.stderr.write(f"{debug_msg}\n")

            summarizer = JujutsuSummarizer()
            success, summary = summarizer.generate_commit_summary(cwd)

            if not success:
                # サマリー生成に失敗した場合
                error_msg = (
                    f"サマリー生成に失敗しました: {summary}"
                    if LANGUAGE == "japanese"
                    else f"Summary generation failed: {summary}"
                )
                sys.stderr.write(f"{error_msg}\n")
                summary = "ファイルを編集" if LANGUAGE == "japanese" else "Edit files"

        except Exception as e:
            # すべての例外をキャッチしてデバッグ情報を出力
            error_msg = (
                f"予期しないエラー: {type(e).__name__}: {str(e)}"
                if LANGUAGE == "japanese"
                else f"Unexpected error: {type(e).__name__}: {str(e)}"
            )
            sys.stderr.write(f"{error_msg}\n")
            # フォールバックモード
            summary = create_fallback_summary(cwd)
            if not summary:
                msg = (
                    "変更がありません。コミットをスキップします。"
                    if LANGUAGE == "japanese"
                    else "No changes found. Skipping commit."
                )
                sys.stdout.write(f"{msg}\n")
                sys.exit(0)

    # コミット実行
    commit_success, commit_result = commit_changes(cwd, summary)

    if commit_success:
        success_msg = (
            f"✅ 自動コミット完了: {summary}"
            if LANGUAGE == "japanese"
            else f"✅ Auto-commit completed: {summary}"
        )
        sys.stdout.write(f"{success_msg}\n")
        if commit_result:
            sys.stdout.write(f"詳細: {commit_result}\n")
    else:
        error_msg = (
            f"❌ コミットに失敗しました: {commit_result}"
            if LANGUAGE == "japanese"
            else f"❌ Commit failed: {commit_result}"
        )
        sys.stderr.write(f"{error_msg}\n")
        # exit code 2 で Claude にエラーを報告
        sys.exit(2)


if __name__ == "__main__":
    main()
