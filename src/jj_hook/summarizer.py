"""LiteLLMを使用したコミットメッセージの自動生成機能。"""

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import litellm
from pydantic import BaseModel


class SummaryConfig(BaseModel):
    """サマリー生成の設定。"""
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 100
    temperature: float = 0.1
    prompt_language: str = "english"


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
            completion_kwargs = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            # GitHub Copilot使用時のヘッダーを追加
            if self.config.model.startswith("github_copilot/"):
                completion_kwargs["extra_headers"] = {
                    "editor-version": "vscode/1.85.1",
                    "Copilot-Integration-Id": "vscode-chat"
                }
            
            response = litellm.completion(**completion_kwargs)
            
            summary = response.choices[0].message.content.strip()
            
            # 不要な引用符やマークダウンを除去
            summary = summary.strip('"\'`')
            if summary.startswith("```") and summary.endswith("```"):
                lines = summary.split("\n")
                summary = "\n".join(lines[1:-1]).strip()
            
            return True, summary
            
        except Exception as e:
            error_msg = f"サマリー生成エラー: {str(e)}" if self.config.prompt_language == "japanese" else f"Summary generation error: {str(e)}"
            return False, error_msg
    
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
            
            completion_kwargs = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 30,
                "temperature": 0.1
            }
            
            # GitHub Copilot使用時のヘッダーを追加
            if self.config.model.startswith("github_copilot/"):
                completion_kwargs["extra_headers"] = {
                    "editor-version": "vscode/1.85.1",
                    "Copilot-Integration-Id": "vscode-chat"
                }
            
            response = litellm.completion(**completion_kwargs)
            
            branch_name = response.choices[0].message.content.strip()
            
            # サニタイズ
            branch_name = "".join(c for c in branch_name if c.isalnum() or c == "-")
            branch_name = branch_name.strip("-")[:20]
            
            if not branch_name:
                branch_name = "feature-work"
            
            return True, branch_name
            
        except Exception as e:
            error_msg = f"ブランチ名生成エラー: {str(e)}" if self.config.prompt_language == "japanese" else f"Branch name generation error: {str(e)}"
            return False, error_msg


@dataclass
class CommitMetrics:
    """コミットのメトリクス情報"""
    commit_id: str
    message: str
    files_changed: int
    lines_added: int
    lines_deleted: int
    total_lines: int
    size_category: str  # "tiny", "small", "medium", "large"
    
    
@dataclass
class SquashProposal:
    """統合提案の情報"""
    source_commits: List[str]  # 統合元コミットID
    target_commit: str         # 統合先コミットID
    reason: str               # 統合理由
    suggested_message: str    # 推奨メッセージ
    confidence_score: float = 0.8  # 提案の信頼度


class CommitOrganizer:
    """コミット履歴を整理するクラス。"""
    
    def __init__(self, config: Optional[SummaryConfig] = None) -> None:
        """初期化。"""
        self.config = config or SummaryConfig()
        
        # 環境変数からモデルを上書き
        if model_env := os.environ.get("JJ_HOOK_MODEL"):
            self.config.model = model_env
            
    def get_commit_log(self, cwd: str, limit: int = 20) -> Tuple[bool, str]:
        """コミット履歴を取得する。"""
        try:
            result = subprocess.run(
                ["jj", "log", "-r", "present(@)::heads(main)", "--limit", str(limit), "--no-graph"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, f"jj log failed: {result.stderr}"
        except Exception as e:
            return False, f"jj log error: {str(e)}"
    
    def get_commit_details(self, cwd: str, commit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """複数のコミットの詳細情報を取得する。"""
        details = {}
        
        for commit_id in commit_ids:
            try:
                # コミットメッセージ取得
                msg_result = subprocess.run(
                    ["jj", "log", "-r", commit_id, "-T", "description"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # コミット差分取得  
                diff_result = subprocess.run(
                    ["jj", "diff", "-r", commit_id, "--stat"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if msg_result.returncode == 0 and diff_result.returncode == 0:
                    details[commit_id] = {
                        "message": msg_result.stdout.strip(),
                        "diff_stat": diff_result.stdout.strip(),
                    }
                    
            except Exception as e:
                details[commit_id] = {
                    "message": f"取得失敗: {str(e)}",
                    "diff_stat": "",
                }
                
        return details
    
    def analyze_commits(self, cwd: str, limit: int = 20) -> Tuple[bool, List[SquashProposal]]:
        """
        コミット履歴を分析して統合提案を生成する。
        
        Returns:
            (success, proposals): 成功フラグと統合提案のリスト
        """
        # コミット履歴取得
        success, log_output = self.get_commit_log(cwd, limit)
        if not success:
            return False, []
        
        # コミットIDを抽出（簡単な解析）
        commit_ids = []
        for line in log_output.split('\n'):
            if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                # コミットIDらしき文字列を抽出
                parts = line.split()
                if parts and len(parts[0]) >= 8:  # 短縮されたコミットIDを想定
                    commit_ids.append(parts[0])
        
        if len(commit_ids) < 2:
            return True, []  # 統合対象がない
        
        # 上位5件のコミット詳細を取得
        recent_commits = commit_ids[:min(5, len(commit_ids))]
        commit_details = self.get_commit_details(cwd, recent_commits)
        
        # AI分析でスカッシュ提案を生成
        return self._generate_squash_proposals(log_output, commit_details)
    
    def _generate_squash_proposals(self, log_output: str, commit_details: Dict[str, Dict[str, Any]]) -> Tuple[bool, List[SquashProposal]]:
        """AI分析でスカッシュ提案を生成する。"""
        try:
            if self.config.prompt_language == "japanese":
                prompt = self._build_japanese_analysis_prompt(log_output, commit_details)
            else:
                prompt = self._build_english_analysis_prompt(log_output, commit_details)
            
            completion_kwargs = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            # GitHub Copilot使用時のヘッダーを追加
            if self.config.model.startswith("github_copilot/"):
                completion_kwargs["extra_headers"] = {
                    "editor-version": "vscode/1.85.1",
                    "Copilot-Integration-Id": "vscode-chat"
                }
            
            response = litellm.completion(**completion_kwargs)
            analysis_result = response.choices[0].message.content.strip()
            
            # JSON形式の結果をパース
            try:
                data = json.loads(analysis_result)
                proposals = []
                
                for item in data.get("proposals", []):
                    proposal = SquashProposal(
                        source_commits=item.get("source_commits", []),
                        target_commit=item.get("target_commit", ""),
                        reason=item.get("reason", ""),
                        suggested_message=item.get("suggested_message", "")
                    )
                    proposals.append(proposal)
                
                return True, proposals
                
            except json.JSONDecodeError:
                # JSONパースが失敗した場合は空のリストを返す
                return True, []
                
        except Exception as e:
            return False, []
    
    def _build_japanese_analysis_prompt(self, log_output: str, commit_details: Dict[str, Dict[str, Any]]) -> str:
        """日本語の分析プロンプトを構築する。"""
        details_text = ""
        for commit_id, details in commit_details.items():
            details_text += f"\n{commit_id}: {details['message']}\n{details['diff_stat']}\n"
        
        return f"""
コミット履歴を分析して、論理的に関連するコミットをスカッシュする提案を生成してください。

## コミット履歴:
{log_output}

## 詳細情報:
{details_text}

## 分析基準:
- 同一ファイルの連続した小さな修正
- タイポ修正とそのフィックス
- 機能追加とそのテスト
- "fix", "wip", "tmp"等の意味のないメッセージ
- 論理的に一つの変更であるべき分散したコミット

以下のJSON形式で提案を出力してください:

{{
  "proposals": [
    {{
      "source_commits": ["commit-id1", "commit-id2"],
      "target_commit": "commit-id1",
      "reason": "統合理由",
      "suggested_message": "提案するコミットメッセージ"
    }}
  ]
}}

提案がない場合は空の配列を返してください。JSON形式のみ出力してください:"""
    
    def _build_english_analysis_prompt(self, log_output: str, commit_details: Dict[str, Dict[str, Any]]) -> str:
        """英語の分析プロンプトを構築する。"""
        details_text = ""
        for commit_id, details in commit_details.items():
            details_text += f"\n{commit_id}: {details['message']}\n{details['diff_stat']}\n"
        
        return f"""
Analyze the commit history and generate proposals to squash logically related commits.

## Commit History:
{log_output}

## Details:
{details_text}

## Analysis Criteria:
- Consecutive small modifications to the same file
- Typo fixes and their corrections
- Feature additions and their tests
- Meaningless messages like "fix", "wip", "tmp"
- Logically unified changes dispersed across commits

Output proposals in the following JSON format:

{{
  "proposals": [
    {{
      "source_commits": ["commit-id1", "commit-id2"],
      "target_commit": "commit-id1",
      "reason": "Reason for squashing",
      "suggested_message": "Proposed commit message"
    }}
  ]
}}

Return empty array if no proposals. Output only JSON format:"""
    
    def execute_squash(self, cwd: str, proposal: SquashProposal) -> Tuple[bool, str]:
        """スカッシュを実行する。"""
        try:
            if len(proposal.source_commits) < 2:
                return False, "統合対象のコミットが不十分です"
            
            target = proposal.target_commit
            sources = [c for c in proposal.source_commits if c != target]
            
            # 各ソースコミットを順次ターゲットに統合
            for source in sources:
                result = subprocess.run(
                    ["jj", "squash", "--from", source, "--into", target],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    return False, f"スカッシュ失敗: {result.stderr}"
            
            # コミットメッセージの更新
            if proposal.suggested_message:
                result = subprocess.run(
                    ["jj", "describe", "-r", target, "-m", proposal.suggested_message],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                
                if result.returncode != 0:
                    return False, f"メッセージ更新失敗: {result.stderr}"
            
            return True, "スカッシュが完了しました"
            
        except Exception as e:
            return False, f"実行エラー: {str(e)}"
    
    def create_backup_bookmark(self, cwd: str) -> Tuple[bool, str]:
        """バックアップブックマークを作成する。"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_before_organize_{timestamp}"
            
            result = subprocess.run(
                ["jj", "bookmark", "create", backup_name, "-r", "@"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, backup_name
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)