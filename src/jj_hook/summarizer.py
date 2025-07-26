"""LiteLLMを使用したコミットメッセージの自動生成機能。"""

import os
import subprocess
from typing import Optional, Tuple

import litellm
from pydantic import BaseModel


class SummaryConfig(BaseModel):
    """サマリー生成の設定。"""
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 100
    temperature: float = 0.1
    prompt_language: str = "japanese"


class JujutsuSummarizer:
    """Jujutsuリポジトリの変更をサマリーするクラス。"""
    
    def __init__(self, config: Optional[SummaryConfig] = None) -> None:
        """初期化。"""
        self.config = config or SummaryConfig()
        
        # 環境変数からモデルを上書き
        if model_env := os.environ.get("JJ_HOOK_MODEL"):
            self.config.model = model_env
    
    def get_jj_status(self, cwd: str) -> str:
        """jj statusコマンドの出力を取得する。"""
        try:
            result = subprocess.run(
                ["jj", "status"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"jj status failed: {result.stderr}"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            return f"jj status error: {str(e)}"
    
    def get_jj_diff(self, cwd: str) -> str:
        """jj diffコマンドの出力を取得する。"""
        try:
            result = subprocess.run(
                ["jj", "diff"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                # diffが大きすぎる場合は切り詰める
                diff_output = result.stdout.strip()
                if len(diff_output) > 5000:
                    diff_output = diff_output[:5000] + "\n... (切り詰められました)"
                return diff_output
            else:
                return f"jj diff failed: {result.stderr}"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            return f"jj diff error: {str(e)}"
    
    def generate_commit_summary(self, cwd: str) -> Tuple[bool, str]:
        """
        Jujutsuリポジトリの変更に基づいてコミットメッセージを生成する。
        
        Returns:
            (success, message): 成功フラグとメッセージ
        """
        status_output = self.get_jj_status(cwd)
        diff_output = self.get_jj_diff(cwd)
        
        # 変更がない場合はスキップ
        if "No changes" in status_output or not diff_output.strip():
            return False, "変更がありません"
        
        # プロンプトを構築
        if self.config.prompt_language == "japanese":
            prompt = self._build_japanese_prompt(status_output, diff_output)
        else:
            prompt = self._build_english_prompt(status_output, diff_output)
        
        try:
            # LiteLLMでサマリーを生成
            response = litellm.completion(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            summary = response.choices[0].message.content.strip()
            
            # 不要な引用符やマークダウンを除去
            summary = summary.strip('"\'`')
            if summary.startswith("```") and summary.endswith("```"):
                lines = summary.split("\n")
                summary = "\n".join(lines[1:-1]).strip()
            
            return True, summary
            
        except Exception as e:
            return False, f"サマリー生成エラー: {str(e)}"
    
    def _build_japanese_prompt(self, status: str, diff: str) -> str:
        """日本語のプロンプトを構築する。"""
        return f"""
以下のJujutsu (jj)リポジトリの変更内容から、簡潔で分かりやすいコミットメッセージを日本語で生成してください。

## jj status:
{status}

## jj diff:
{diff}

## 要求事項:
- 1行で簡潔に（50文字以内が理想）
- 変更の内容を端的に表現
- 技術的すぎない日常的な表現
- プレフィックス（feat:, fix:など）は不要

例: "ユーザー認証機能を追加", "バグ修正：ログイン時のエラー処理", "設定ファイルを更新"

コミットメッセージのみを出力してください:"""
    
    def _build_english_prompt(self, status: str, diff: str) -> str:
        """英語のプロンプトを構築する。"""
        return f"""
Generate a concise and clear commit message based on the following Jujutsu (jj) repository changes.

## jj status:
{status}

## jj diff:
{diff}

## Requirements:
- Keep it concise and under 50 characters if possible
- Capture the essence of the changes
- Use conventional style but don't include prefixes like feat:, fix:
- Be specific but not overly technical

Examples: "Add user authentication", "Fix login error handling", "Update configuration"

Output only the commit message:"""
    
    def generate_branch_name(self, prompt: str) -> Tuple[bool, str]:
        """
        ユーザープロンプトから新しいブランチ名を生成する。
        
        Returns:
            (success, branch_name): 成功フラグとブランチ名
        """
        try:
            if self.config.prompt_language == "japanese":
                system_prompt = """
ユーザーのプロンプトから適切なブランチ名を生成してください。

要求事項:
- ケバブケース（ハイフン区切り）
- 英数字とハイフンのみ使用
- 20文字以内
- 作業内容を簡潔に表現

例:
- "ユーザー認証機能を追加して" → "add-user-auth"
- "バグを修正する" → "fix-bug"
- "設定を更新" → "update-config"

ブランチ名のみを出力してください:"""
            else:
                system_prompt = """
Generate an appropriate branch name from the user's prompt.

Requirements:
- Use kebab-case (hyphen-separated)
- Only alphanumeric characters and hyphens
- Under 20 characters
- Briefly describe the work

Examples:
- "Add user authentication feature" → "add-user-auth"
- "Fix login bug" → "fix-login-bug"
- "Update configuration" → "update-config"

Output only the branch name:"""
            
            response = litellm.completion(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=30,
                temperature=0.1
            )
            
            branch_name = response.choices[0].message.content.strip()
            
            # サニタイズ
            branch_name = "".join(c for c in branch_name if c.isalnum() or c == "-")
            branch_name = branch_name.strip("-")[:20]
            
            if not branch_name:
                branch_name = "feature-work"
            
            return True, branch_name
            
        except Exception as e:
            return False, f"ブランチ名生成エラー: {str(e)}"