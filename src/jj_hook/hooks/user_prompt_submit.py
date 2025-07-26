#!/usr/bin/env python3
"""
UserPromptSubmit hook for creating new branches with AI-generated names.

This hook is triggered when a user submits a prompt and automatically
creates a new Jujutsu branch with a descriptive name based on the user's intent.
"""

import json
import sys
import subprocess
import os
import re
from pathlib import Path

# パッケージのインポートパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from jj_hook.summarizer import JujutsuSummarizer, SummaryConfig
except ImportError:
    # フォールバック：スクリプトが単体で実行された場合
    sys.stderr.write("警告: jj_hook パッケージをインポートできませんでした。スタンドアロンモードで実行します。\n")
    
    def create_fallback_branch_name(prompt: str) -> str:
        """フォールバック用の簡単なブランチ名生成。"""
        # プロンプトから英数字とスペースのみ抽出
        clean_prompt = re.sub(r'[^\w\s]', '', prompt.lower())
        words = clean_prompt.split()[:3]  # 最初の3単語
        if words:
            return "-".join(words)[:20]
        else:
            return "feature-work"


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


def create_new_branch(cwd: str, branch_description: str) -> tuple[bool, str]:
    """新しいブランチを作成する。"""
    try:
        # jj new -m でブランチ作成とコミットメッセージ設定を同時に行う
        result = subprocess.run(
            ["jj", "new", "-m", branch_description],
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


def should_create_branch(prompt: str) -> bool:
    """プロンプトの内容から新しいブランチを作成すべきかどうか判断する。"""
    # 短すぎるプロンプトはスキップ
    if len(prompt.strip()) < 10:
        return False
    
    # 質問系のプロンプトはスキップ
    question_patterns = [
        r'^(what|how|why|when|where|which)',
        r'[?？]',
        r'^(教えて|説明|どう)',
        r'(とは|って何|について)',
    ]
    
    for pattern in question_patterns:
        if re.search(pattern, prompt.lower()):
            return False
    
    # 作業系のプロンプトは対象
    work_patterns = [
        r'(作成|追加|実装|修正|更新|削除)',
        r'(create|add|implement|fix|update|delete)',
        r'(build|make|write|develop)',
        r'(リファクタ|テスト|デプロイ)',
    ]
    
    for pattern in work_patterns:
        if re.search(pattern, prompt.lower()):
            return True
    
    # デフォルトは作成する（保守的）
    return True


def generate_branch_description(prompt: str) -> str:
    """プロンプトから作業内容の説明を生成する。"""
    # プロンプトを簡潔にまとめる
    description = prompt.strip()
    
    # 長すぎる場合は切り詰める
    if len(description) > 60:
        description = description[:57] + "..."
    
    return description


def main() -> None:
    """メイン処理。"""
    try:
        # stdinからJSONデータを読み込み
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"JSONデコードエラー: {e}\n")
        sys.exit(1)
    
    # フック情報の取得
    prompt = input_data.get("prompt", "")
    cwd = input_data.get("cwd", os.getcwd())
    
    # プロンプトが空の場合はスキップ
    if not prompt.strip():
        sys.exit(0)
    
    # Jujutsuリポジトリかチェック
    if not is_jj_repository(cwd):
        sys.stderr.write("Jujutsuリポジトリではありません。スキップします。\n")
        sys.exit(0)
    
    # 新しいブランチを作成すべきかチェック
    if not should_create_branch(prompt):
        sys.stdout.write("質問系のプロンプトのため、新しいブランチは作成しません。\n")
        sys.exit(0)
    
    # ブランチの説明を生成
    branch_description = generate_branch_description(prompt)
    
    # ブランチ作成実行
    branch_success, branch_result = create_new_branch(cwd, branch_description)
    
    if branch_success:
        sys.stdout.write(f"🌟 新しいブランチを作成しました: {branch_description}\n")
        if branch_result:
            sys.stdout.write(f"詳細: {branch_result}\n")
    else:
        # ブランチ作成に失敗してもエラーにはしない（警告のみ）
        sys.stderr.write(f"⚠️  ブランチ作成に失敗しました: {branch_result}\n")
        # 通常は exit(0) でプロンプト処理を続行
        sys.exit(0)


if __name__ == "__main__":
    main()