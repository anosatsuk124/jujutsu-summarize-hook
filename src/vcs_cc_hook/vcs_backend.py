"""VCS抽象化レイヤー。"""

import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class VCSBackend(ABC):
    """VCS操作の抽象基底クラス。"""

    def __init__(self, cwd: str):
        """初期化。"""
        self.cwd = cwd

    @abstractmethod
    def is_repository(self) -> bool:
        """現在のディレクトリがこのVCSのリポジトリかどうかチェックする。"""
        pass

    @abstractmethod
    def get_status(self) -> str:
        """リポジトリの状態を取得する。"""
        pass

    @abstractmethod
    def get_diff(self) -> str:
        """変更差分を取得する。"""
        pass

    @abstractmethod
    def has_uncommitted_changes(self) -> bool:
        """コミットされていない変更があるかチェックする。"""
        pass

    @abstractmethod
    def commit_changes(self, message: str) -> Tuple[bool, str]:
        """変更をコミットする。"""
        pass

    @abstractmethod
    def create_branch(self, name: str, message: Optional[str] = None) -> Tuple[bool, str]:
        """新しいブランチを作成する。"""
        pass

    @abstractmethod
    def get_repository_root(self) -> Optional[str]:
        """リポジトリのルートディレクトリを取得する。"""
        pass

    @abstractmethod
    def get_commit_log(self, limit: int = 20) -> Tuple[bool, str]:
        """コミット履歴を取得する。"""
        pass

    @abstractmethod
    def get_commit_message(self, commit_id: str) -> Tuple[bool, str]:
        """指定されたコミットのメッセージを取得する。"""
        pass

    @abstractmethod
    def get_commit_diff_stat(self, commit_id: str) -> Tuple[bool, str]:
        """指定されたコミットの差分統計を取得する。"""
        pass

    @abstractmethod
    def get_changed_files(self, commit_id: str) -> Tuple[bool, list[str]]:
        """指定されたコミットで変更されたファイル一覧を取得する。"""
        pass

    def run_command(self, command: list[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """コマンドを実行して結果を返すヘルパーメソッド。"""
        try:
            result = subprocess.run(
                command, cwd=self.cwd, capture_output=True, text=True, timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            return False, "", str(e)


def detect_vcs_backend(cwd: str) -> Optional[VCSBackend]:
    """
    指定されたディレクトリでVCSバックエンドを自動検出する。

    Returns:
        検出されたVCSバックエンド、または None
    """
    # Jujutsuを優先的に検出
    from .jujutsu_backend import JujutsuBackend

    jj_backend = JujutsuBackend(cwd)
    if jj_backend.is_repository():
        return jj_backend

    # Gitを検出
    from .git_backend import GitBackend

    git_backend = GitBackend(cwd)
    if git_backend.is_repository():
        return git_backend

    return None


def is_vcs_repository(cwd: str) -> bool:
    """指定されたディレクトリがいずれかのVCSリポジトリかどうかチェックする。"""
    backend = detect_vcs_backend(cwd)
    return backend is not None


def get_vcs_backend(cwd: str) -> Optional[VCSBackend]:
    """VCSバックエンドを取得する。detect_vcs_backendのエイリアス。"""
    return detect_vcs_backend(cwd)
