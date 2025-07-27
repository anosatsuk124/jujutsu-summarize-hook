"""Git VCSバックエンドの実装。"""

import os
from pathlib import Path
from typing import Optional, Tuple

from .vcs_backend import VCSBackend


class GitBackend(VCSBackend):
    """Git VCS操作の実装。"""

    def is_repository(self) -> bool:
        """現在のディレクトリがGitリポジトリかどうかチェックする。"""
        success, _, _ = self.run_command(["git", "rev-parse", "--show-toplevel"], timeout=5)
        return success

    def get_status(self) -> str:
        """git statusコマンドの出力を取得する。"""
        success, stdout, stderr = self.run_command(["git", "status", "--porcelain"], timeout=10)
        if success:
            return stdout.strip()
        else:
            return f"git status failed: {stderr}"

    def get_diff(self) -> str:
        """git diffコマンドの出力を取得する。"""
        # ステージングエリアと作業ディレクトリの両方の変更を取得
        success1, stdout1, stderr1 = self.run_command(["git", "diff", "HEAD"], timeout=30)
        
        if success1:
            diff_output = stdout1.strip()
            # diffが大きすぎる場合は切り詰める
            if len(diff_output) > 5000:
                diff_output = diff_output[:5000] + "\n... (切り詰められました)"
            return diff_output
        else:
            return f"git diff failed: {stderr1}"

    def has_uncommitted_changes(self) -> bool:
        """コミットされていない変更があるかチェックする。"""
        success, stdout, _ = self.run_command(["git", "status", "--porcelain"], timeout=10)
        if success:
            status_output = stdout.strip()
            return len(status_output) > 0
        return False

    def commit_changes(self, message: str) -> Tuple[bool, str]:
        """変更をコミットする。"""
        # まずステージングエリアに追加
        success_add, _, stderr_add = self.run_command(["git", "add", "-A"], timeout=15)
        if not success_add:
            return False, f"git add failed: {stderr_add}"
        
        # コミット実行
        success, stdout, stderr = self.run_command(["git", "commit", "-m", message], timeout=30)
        if success:
            return True, stdout.strip()
        else:
            return False, stderr.strip()

    def create_branch(self, name: str, message: Optional[str] = None) -> Tuple[bool, str]:
        """新しいブランチを作成する。"""
        # ブランチを作成してチェックアウト
        success, stdout, stderr = self.run_command(["git", "checkout", "-b", name], timeout=15)
        if success:
            result_msg = f"新しいブランチ '{name}' を作成しました"
            
            # メッセージが指定されている場合は空のコミットを作成
            if message:
                commit_success, commit_stdout, commit_stderr = self.run_command([
                    "git", "commit", "--allow-empty", "-m", message
                ], timeout=15)
                if commit_success:
                    result_msg += f": {message}"
                else:
                    # 空のコミット作成に失敗してもブランチ作成は成功として扱う
                    result_msg += f" (空のコミット作成に失敗: {commit_stderr})"
            
            return True, result_msg
        else:
            return False, stderr.strip()

    def get_repository_root(self) -> Optional[str]:
        """リポジトリのルートディレクトリを取得する。"""
        success, stdout, _ = self.run_command(["git", "rev-parse", "--show-toplevel"], timeout=5)
        if success:
            return stdout.strip()
        return None

    def get_commit_log(self, limit: int = 20) -> Tuple[bool, str]:
        """コミット履歴を取得する。"""
        success, stdout, stderr = self.run_command([
            "git", "log", "--oneline", f"-{limit}"
        ], timeout=15)
        if success:
            return True, stdout.strip()
        else:
            return False, f"git log failed: {stderr}"

    def get_commit_diff_stat(self, commit_hash: str) -> Tuple[bool, str]:
        """指定されたコミットの差分統計を取得する。"""
        success, stdout, stderr = self.run_command([
            "git", "show", "--stat", "--format=", commit_hash
        ], timeout=10)
        if success:
            return True, stdout.strip()
        else:
            return False, f"git show failed: {stderr}"

    def get_commit_message(self, commit_hash: str) -> Tuple[bool, str]:
        """指定されたコミットのメッセージを取得する。"""
        success, stdout, stderr = self.run_command([
            "git", "log", "-1", "--pretty=format:%s", commit_hash
        ], timeout=10)
        if success:
            return True, stdout.strip()
        else:
            return False, f"git log failed: {stderr}"

    def get_changed_files(self, commit_hash: str) -> Tuple[bool, list[str]]:
        """指定されたコミットで変更されたファイル一覧を取得する。"""
        success, stdout, stderr = self.run_command([
            "git", "show", "--name-only", "--format=", commit_hash
        ], timeout=10)
        if success:
            files = [f.strip() for f in stdout.split("\n") if f.strip()]
            return True, files
        else:
            return False, []

    def create_backup_branch(self, name: str) -> Tuple[bool, str]:
        """バックアップブランチを作成する（現在のブランチから）。"""
        success, stdout, stderr = self.run_command([
            "git", "branch", name
        ], timeout=10)
        if success:
            return True, name
        else:
            return False, stderr.strip()

    def interactive_rebase(self, base_commit: str) -> Tuple[bool, str]:
        """インタラクティブリベースを開始する（Git固有機能）。"""
        # 注意: このメソッドは実際のインタラクティブセッションを開始するため、
        # 自動化環境では使用注意
        success, stdout, stderr = self.run_command([
            "git", "rebase", "-i", base_commit
        ], timeout=60)
        if success:
            return True, "Interactive rebase started"
        else:
            return False, stderr.strip()

    def squash_commits(self, commit_hashes: list[str], new_message: str) -> Tuple[bool, str]:
        """
        複数のコミットをスカッシュする（Git向けの簡易実装）。
        
        注意: これは簡略化された実装です。実際のプロダクション環境では
        より慎重な実装が必要です。
        """
        if len(commit_hashes) < 2:
            return False, "スカッシュには2つ以上のコミットが必要です"
        
        # 最も古いコミットの親を取得
        oldest_commit = commit_hashes[-1]  # リストの最後が最も古いと仮定
        success, parent_stdout, stderr = self.run_command([
            "git", "rev-parse", f"{oldest_commit}^"
        ], timeout=10)
        
        if not success:
            return False, f"親コミットの取得に失敗: {stderr}"
        
        parent_hash = parent_stdout.strip()
        
        # ソフトリセットで変更をステージングエリアに戻す
        success, _, stderr = self.run_command([
            "git", "reset", "--soft", parent_hash
        ], timeout=15)
        
        if not success:
            return False, f"リセットに失敗: {stderr}"
        
        # 新しいメッセージでコミット
        success, stdout, stderr = self.run_command([
            "git", "commit", "-m", new_message
        ], timeout=30)
        
        if success:
            return True, f"コミットをスカッシュしました: {new_message}"
        else:
            return False, f"コミットに失敗: {stderr}"