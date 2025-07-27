"""VCS バックエンドのテスト。"""

import tempfile
import os
from pathlib import Path
import subprocess
import pytest

from src.jj_hook.vcs_backend import detect_vcs_backend, is_vcs_repository
from src.jj_hook.git_backend import GitBackend
from src.jj_hook.jujutsu_backend import JujutsuBackend


def test_git_backend_detection():
    """Gitリポジトリの検出テスト。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Gitリポジトリを初期化
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)
        
        # VCS検出をテスト
        backend = detect_vcs_backend(temp_dir)
        assert backend is not None
        assert isinstance(backend, GitBackend)
        assert backend.is_repository()
        assert is_vcs_repository(temp_dir)


def test_git_backend_basic_operations():
    """Gitバックエンドの基本操作テスト。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Gitリポジトリを初期化
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True)
        
        backend = GitBackend(temp_dir)
        
        # ファイルを作成
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello World")
        
        # 変更をチェック
        assert backend.has_uncommitted_changes()
        
        # ステータスを取得
        status = backend.get_status()
        assert "test.txt" in status
        
        # コミット
        success, message = backend.commit_changes("Initial commit")
        assert success
        
        # 変更がないことを確認
        assert not backend.has_uncommitted_changes()


def test_vcs_detection_priority():
    """VCS検出の優先順位テスト（Jujutsu > Git）。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Gitリポジトリを初期化
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        
        # Jujutsuがインストールされている場合のみテスト
        try:
            subprocess.run(["jj", "--version"], check=True, capture_output=True)
            
            # Jujutsuリポジトリを初期化
            subprocess.run(["jj", "init"], cwd=temp_dir, check=True, capture_output=True)
            
            # Jujutsuが優先的に検出されることを確認
            backend = detect_vcs_backend(temp_dir)
            assert isinstance(backend, JujutsuBackend)
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Jujutsuがインストールされていない場合はGitが検出される
            backend = detect_vcs_backend(temp_dir)
            assert isinstance(backend, GitBackend)


def test_non_vcs_directory():
    """非VCSディレクトリでの検出テスト。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        backend = detect_vcs_backend(temp_dir)
        assert backend is None
        assert not is_vcs_repository(temp_dir)


@pytest.mark.skipif(
    subprocess.run(["jj", "--version"], capture_output=True).returncode != 0,
    reason="Jujutsu not installed"
)
def test_jujutsu_backend_basic_operations():
    """Jujutsuバックエンドの基本操作テスト。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Jujutsuリポジトリを初期化
        subprocess.run(["jj", "init"], cwd=temp_dir, check=True, capture_output=True)
        
        backend = JujutsuBackend(temp_dir)
        
        # ファイルを作成
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello World")
        
        # 変更をチェック
        assert backend.has_uncommitted_changes()
        
        # ステータスを取得
        status = backend.get_status()
        assert "test.txt" in status
        
        # コミット
        success, message = backend.commit_changes("Initial commit")
        assert success