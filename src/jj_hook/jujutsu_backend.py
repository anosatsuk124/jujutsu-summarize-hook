"""Jujutsu VCSバックエンドの実装。"""

from typing import Optional, Tuple

from .vcs_backend import VCSBackend


class JujutsuBackend(VCSBackend):
    """Jujutsu VCS操作の実装。"""

    def is_repository(self) -> bool:
        """現在のディレクトリがJujutsuリポジトリかどうかチェックする。"""
        success, _, _ = self.run_command(["jj", "root"], timeout=5)
        return success

    def get_status(self) -> str:
        """jj statusコマンドの出力を取得する。"""
        success, stdout, stderr = self.run_command(["jj", "status"], timeout=10)
        if success:
            return stdout.strip()
        else:
            return f"jj status failed: {stderr}"

    def get_diff(self) -> str:
        """jj diffコマンドの出力を取得する。"""
        success, stdout, stderr = self.run_command(["jj", "diff"], timeout=30)
        if success:
            diff_output = stdout.strip()
            # diffが大きすぎる場合は切り詰める
            if len(diff_output) > 5000:
                diff_output = diff_output[:5000] + "\n... (切り詰められました)"
            return diff_output
        else:
            return f"jj diff failed: {stderr}"

    def has_uncommitted_changes(self) -> bool:
        """コミットされていない変更があるかチェックする。"""
        success, stdout, _ = self.run_command(["jj", "status"], timeout=10)
        if success:
            status_output = stdout.strip()
            return "No changes" not in status_output and len(status_output) > 0
        return False

    def commit_changes(self, message: str) -> Tuple[bool, str]:
        """変更をコミットする（jj describe）。"""
        success, stdout, stderr = self.run_command(["jj", "describe", "-m", message], timeout=30)
        if success:
            return True, stdout.strip()
        else:
            return False, stderr.strip()

    def create_branch(self, name: str, message: Optional[str] = None) -> Tuple[bool, str]:
        """新しいリビジョンを作成する（jj new）。"""
        if message:
            # メッセージ付きで新しいリビジョンを作成
            success, stdout, stderr = self.run_command(["jj", "new", "-m", message], timeout=15)
        else:
            # デフォルトメッセージで新しいリビジョンを作成
            success, stdout, stderr = self.run_command(["jj", "new"], timeout=15)
        
        if success:
            return True, stdout.strip()
        else:
            return False, stderr.strip()

    def get_repository_root(self) -> Optional[str]:
        """リポジトリのルートディレクトリを取得する。"""
        success, stdout, _ = self.run_command(["jj", "root"], timeout=5)
        if success:
            return stdout.strip()
        return None

    def get_commit_log(self, limit: int = 20) -> Tuple[bool, str]:
        """コミット履歴を取得する。"""
        success, stdout, stderr = self.run_command([
            "jj", "log", "-r", "present(@)::heads(main)", "--limit", str(limit), "--no-graph"
        ], timeout=15)
        if success:
            return True, stdout.strip()
        else:
            return False, f"jj log failed: {stderr}"

    def get_commit_diff_stat(self, commit_id: str) -> Tuple[bool, str]:
        """指定されたコミットの差分統計を取得する。"""
        success, stdout, stderr = self.run_command([
            "jj", "diff", "-r", commit_id, "--stat"
        ], timeout=10)
        if success:
            return True, stdout.strip()
        else:
            return False, f"jj diff failed: {stderr}"

    def get_commit_message(self, commit_id: str) -> Tuple[bool, str]:
        """指定されたコミットのメッセージを取得する。"""
        success, stdout, stderr = self.run_command([
            "jj", "log", "-r", commit_id, "-T", "description"
        ], timeout=10)
        if success:
            return True, stdout.strip()
        else:
            return False, f"jj log failed: {stderr}"

    def get_changed_files(self, commit_id: str) -> Tuple[bool, list[str]]:
        """指定されたコミットで変更されたファイル一覧を取得する。"""
        success, stdout, stderr = self.run_command([
            "jj", "diff", "-r", commit_id, "--name-only"
        ], timeout=10)
        if success:
            files = [f.strip() for f in stdout.split("\n") if f.strip()]
            return True, files
        else:
            return False, []

    def create_backup_bookmark(self, name: str) -> Tuple[bool, str]:
        """バックアップブックマークを作成する。"""
        success, stdout, stderr = self.run_command([
            "jj", "bookmark", "create", name, "-r", "@"
        ], timeout=10)
        if success:
            return True, name
        else:
            return False, stderr.strip()

    def squash_commits(self, source_commit: str, target_commit: str, new_message: Optional[str] = None) -> Tuple[bool, str]:
        """コミットをスカッシュする（jj squash）。"""
        success, stdout, stderr = self.run_command([
            "jj", "squash", "--from", source_commit, "--into", target_commit
        ], timeout=30)
        
        if not success:
            return False, f"スカッシュ失敗: {stderr}"
        
        # メッセージの更新
        if new_message:
            msg_success, msg_stdout, msg_stderr = self.run_command([
                "jj", "describe", "-r", target_commit, "-m", new_message
            ], timeout=15)
            
            if not msg_success:
                return False, f"メッセージ更新失敗: {msg_stderr}"
        
        return True, "スカッシュが完了しました"

    def update_commit_message(self, commit_id: str, message: str) -> Tuple[bool, str]:
        """コミットメッセージを更新する。"""
        success, stdout, stderr = self.run_command([
            "jj", "describe", "-r", commit_id, "-m", message
        ], timeout=15)
        if success:
            return True, stdout.strip()
        else:
            return False, stderr.strip()

    def create_bookmark(self, name: str, revision: str = "@") -> Tuple[bool, str]:
        """ブックマークを作成する。"""
        success, stdout, stderr = self.run_command([
            "jj", "bookmark", "create", name, "-r", revision
        ], timeout=10)
        if success:
            return True, f"ブックマーク '{name}' を作成しました"
        else:
            return False, stderr.strip()

    def get_current_revision(self) -> Tuple[bool, str]:
        """現在のリビジョンIDを取得する。"""
        success, stdout, stderr = self.run_command([
            "jj", "log", "-r", "@", "-T", "commit_id"
        ], timeout=5)
        if success:
            return True, stdout.strip()
        else:
            return False, stderr.strip()

    def create_backup_branch(self, name: str) -> Tuple[bool, str]:
        """バックアップブランチを作成する（Gitバックエンドとの互換性のため）。"""
        return self.create_backup_bookmark(name)