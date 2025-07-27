"""LiteLLMを使用したコミットメッセージの自動生成機能。"""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
from difflib import SequenceMatcher

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
class ExtendedCommitMetrics(CommitMetrics):
    """拡張されたコミットメトリクス情報"""
    modified_files: List[str] = None  # 変更されたファイルのリスト
    commit_time: Optional[str] = None  # コミット時刻
    
    
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
    
    def get_commit_metrics(self, cwd: str, commit_ids: List[str]) -> List[CommitMetrics]:
        """複数のコミットのメトリクス情報を取得する。"""
        metrics_list = []
        
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
                
                # コミット差分の詳細取得（数値データあり）
                diff_result = subprocess.run(
                    ["jj", "diff", "-r", commit_id, "--stat"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # ファイル一覧取得
                files_result = subprocess.run(
                    ["jj", "diff", "-r", commit_id, "--name-only"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if msg_result.returncode == 0 and diff_result.returncode == 0:
                    message = msg_result.stdout.strip()
                    diff_stat = diff_result.stdout.strip()
                    
                    # ファイルリストを取得（失敗しても続行）
                    modified_files = []
                    if files_result.returncode == 0:
                        modified_files = [f.strip() for f in files_result.stdout.split('\n') if f.strip()]
                    
                    # 差分統計を解析
                    files_changed, lines_added, lines_deleted = self._parse_diff_stat(diff_stat)
                    total_lines = lines_added + lines_deleted
                    size_category = self._categorize_size(files_changed, total_lines)
                    
                    # ExtendedCommitMetricsを作成
                    metrics = ExtendedCommitMetrics(
                        commit_id=commit_id,
                        message=message,
                        files_changed=files_changed,
                        lines_added=lines_added,
                        lines_deleted=lines_deleted,
                        total_lines=total_lines,
                        size_category=size_category,
                        modified_files=modified_files,
                        commit_time=None  # 時間情報は別途取得
                    )
                    metrics_list.append(metrics)
                    
            except Exception as e:
                # エラーの場合はダミーデータで追加
                metrics = ExtendedCommitMetrics(
                    commit_id=commit_id,
                    message=f"取得失敗: {str(e)}",
                    files_changed=0,
                    lines_added=0,
                    lines_deleted=0,
                    total_lines=0,
                    size_category="unknown",
                    modified_files=[],
                    commit_time=None
                )
                metrics_list.append(metrics)
                
        return metrics_list
    
    def detect_tiny_commits(self, metrics_list: List[CommitMetrics]) -> List[str]:
        """極小サイズのコミットを検出する。"""
        tiny_commits = []
        
        for metrics in metrics_list:
            # サイズベース判定
            if metrics.size_category == "tiny":
                tiny_commits.append(metrics.commit_id)
                continue
                
            # メッセージパターンベース判定
            if self._is_trivial_commit_message(metrics.message):
                tiny_commits.append(metrics.commit_id)
                continue
                
            # 特定パターン（タイポ修正など）
            if self._is_fix_commit(metrics.message) and metrics.total_lines <= 10:
                tiny_commits.append(metrics.commit_id)
                
        return tiny_commits
    
    def _is_trivial_commit_message(self, message: str) -> bool:
        """些細なコミットメッセージかどうか判定する。"""
        trivial_patterns = [
            r'^(fix|Fix|FIX)$',
            r'^(wip|WIP|tmp|TMP)(\s|$)',
            r'^(typo|Typo|TYPO)',
            r'^(format|Format|FORMAT)',
            r'^(style|Style|STYLE)',
            r'^(update|Update|UPDATE)$',
            r'^(cleanup|Cleanup|CLEANUP)',
            r'^(\.|,|;|:|!|\?)?\s*$',  # 記号のみ
            r'^\s*\d+\s*$',  # 数字のみ
            r'^\s*[a-zA-Z]\s*$',  # 単一文字
        ]
        
        for pattern in trivial_patterns:
            if re.match(pattern, message.strip()):
                return True
        
        # 非常に短いメッセージ
        if len(message.strip()) <= 3:
            return True
            
        return False
    
    def _is_fix_commit(self, message: str) -> bool:
        """修正系のコミットかどうか判定する。"""
        fix_patterns = [
            r'fix',
            r'bugfix',
            r'hotfix', 
            r'patch',
            r'correct',
            r'repair',
            r'typo',
            r'error',
            r'bug'
        ]
        
        message_lower = message.lower()
        return any(pattern in message_lower for pattern in fix_patterns)
    
    def detect_related_commits(self, metrics_list: List[CommitMetrics]) -> List[List[str]]:
        """関連するコミット群を検出する。"""
        related_groups = []
        processed_commits = set()
        
        for i, metrics in enumerate(metrics_list):
            if metrics.commit_id in processed_commits:
                continue
                
            # 現在のコミットを開始点として関連コミットを探す
            group = [metrics.commit_id]
            processed_commits.add(metrics.commit_id)
            
            # 後続のコミットとの関連性をチェック
            for j, other_metrics in enumerate(metrics_list[i+1:], i+1):
                if other_metrics.commit_id in processed_commits:
                    continue
                    
                if self._are_commits_related(metrics, other_metrics):
                    group.append(other_metrics.commit_id)
                    processed_commits.add(other_metrics.commit_id)
            
            # 2つ以上のコミットのグループのみを関連グループとする
            if len(group) >= 2:
                related_groups.append(group)
                
        return related_groups
    
    def _are_commits_related(self, commit1: CommitMetrics, commit2: CommitMetrics) -> bool:
        """2つのコミットが関連しているかどうか判定する。"""
        # 両方とも小さいコミットの場合
        if (commit1.size_category in ["tiny", "small"] and 
            commit2.size_category in ["tiny", "small"]):
            
            # メッセージの類似度をチェック
            similarity = self._calculate_message_similarity(commit1.message, commit2.message)
            if similarity > 0.6:  # 60%以上類似
                return True
                
            # 両方が修正系コミットの場合
            if (self._is_fix_commit(commit1.message) and 
                self._is_fix_commit(commit2.message)):
                return True
                
            # 両方が些細なコミットメッセージの場合
            if (self._is_trivial_commit_message(commit1.message) and 
                self._is_trivial_commit_message(commit2.message)):
                return True
                
        return False
    
    def _calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """2つのコミットメッセージの類似度を計算する。"""
        # 基本的な前処理
        msg1_clean = msg1.lower().strip()
        msg2_clean = msg2.lower().strip() 
        
        # SequenceMatcherで類似度計算
        similarity = SequenceMatcher(None, msg1_clean, msg2_clean).ratio()
        return similarity
    
    def generate_rule_based_proposals(self, metrics_list: List[CommitMetrics]) -> List[SquashProposal]:
        """ルールベースでスカッシュ提案を生成する。"""
        proposals = []
        
        # 極小コミットを検出
        tiny_commits = self.detect_tiny_commits(metrics_list)
        
        # 関連コミット群を検出
        related_groups = self.detect_related_commits(metrics_list)
        
        # 極小コミットを前のコミットと統合
        for tiny_commit in tiny_commits:
            # 対応するメトリクスを探す
            tiny_metrics = None
            tiny_index = -1
            for i, metrics in enumerate(metrics_list):
                if metrics.commit_id == tiny_commit:
                    tiny_metrics = metrics
                    tiny_index = i
                    break
            
            if tiny_metrics and tiny_index > 0:
                # 前のコミットと統合
                target_commit = metrics_list[tiny_index - 1].commit_id
                reason = f"極小コミット（{tiny_metrics.total_lines}行変更）を前のコミットと統合"
                
                # より適切なメッセージを提案
                target_metrics = metrics_list[tiny_index - 1]
                if self._is_trivial_commit_message(tiny_metrics.message):
                    suggested_message = target_metrics.message
                else:
                    suggested_message = f"{target_metrics.message}と{tiny_metrics.message}の統合"
                
                proposal = SquashProposal(
                    source_commits=[tiny_commit, target_commit],
                    target_commit=target_commit,
                    reason=reason,
                    suggested_message=suggested_message,
                    confidence_score=0.9
                )
                proposals.append(proposal)
        
        # 関連コミット群を統合
        for group in related_groups:
            if len(group) >= 2:
                # 最初のコミットを統合先とする
                target_commit = group[0]
                source_commits = group
                
                # グループの特徴を分析
                group_metrics = [m for m in metrics_list if m.commit_id in group]
                total_lines = sum(m.total_lines for m in group_metrics)
                
                reason = f"関連する{len(group)}個のコミットを統合（合計{total_lines}行変更）"
                
                # 統合メッセージを生成
                target_metrics = group_metrics[0]
                suggested_message = target_metrics.message
                
                proposal = SquashProposal(
                    source_commits=source_commits,
                    target_commit=target_commit,
                    reason=reason,
                    suggested_message=suggested_message,
                    confidence_score=0.8
                )
                proposals.append(proposal)
        
        return proposals
    
    def _parse_diff_stat(self, diff_stat: str) -> Tuple[int, int, int]:
        """jj diff --statの出力を解析して数値を抽出する。"""
        files_changed = 0
        lines_added = 0
        lines_deleted = 0
        
        try:
            lines = diff_stat.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # ファイル行の例: " path/to/file.py | 10 +++++-----"
                if '|' in line:
                    files_changed += 1
                    parts = line.split('|')
                    if len(parts) > 1:
                        # 数値部分を抽出
                        stats_part = parts[1].strip()
                        if stats_part:
                            # 最初の数値が変更行数
                            import re
                            numbers = re.findall(r'\d+', stats_part)
                            if numbers:
                                total_changes = int(numbers[0])
                                # +と-の数をカウント
                                plus_count = stats_part.count('+')
                                minus_count = stats_part.count('-')
                                
                                if plus_count > 0 and minus_count > 0:
                                    # 比例配分
                                    total_symbols = plus_count + minus_count
                                    lines_added += int(total_changes * plus_count / total_symbols)
                                    lines_deleted += int(total_changes * minus_count / total_symbols)
                                elif plus_count > 0:
                                    lines_added += total_changes
                                elif minus_count > 0:
                                    lines_deleted += total_changes
                
                # サマリー行の例: " 2 files changed, 15 insertions(+), 8 deletions(-)"
                elif "files changed" in line or "file changed" in line:
                    import re
                    # insertions の数値を抽出
                    insertions_match = re.search(r'(\d+) insertions?\(\+\)', line)
                    if insertions_match:
                        lines_added = int(insertions_match.group(1))
                    
                    # deletions の数値を抽出
                    deletions_match = re.search(r'(\d+) deletions?\(-\)', line)
                    if deletions_match:
                        lines_deleted = int(deletions_match.group(1))
                    
                    # files changed の数値を抽出
                    files_match = re.search(r'(\d+) files? changed', line)
                    if files_match:
                        files_changed = int(files_match.group(1))
                        
        except Exception:
            # パースに失敗した場合はデフォルト値
            pass
                
        return files_changed, lines_added, lines_deleted
    
    def _categorize_size(self, files_changed: int, total_lines: int) -> str:
        """コミットサイズを分類する。"""
        if total_lines <= 5 and files_changed <= 1:
            return "tiny"
        elif total_lines <= 20 and files_changed <= 3:
            return "small" 
        elif total_lines <= 100 and files_changed <= 10:
            return "medium"
        else:
            return "large"
    
    def get_commit_details(self, cwd: str, commit_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """複数のコミットの詳細情報を取得する（下位互換用）。"""
        details = {}
        metrics_list = self.get_commit_metrics(cwd, commit_ids)
        
        for metrics in metrics_list:
            details[metrics.commit_id] = {
                "message": metrics.message,
                "diff_stat": f"{metrics.files_changed} files, +{metrics.lines_added}/-{metrics.lines_deleted}",
                "metrics": metrics
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
        
        # 分析対象のコミット数を制限
        target_commits = commit_ids[:min(limit, len(commit_ids))]
        
        # メトリクス情報を取得
        metrics_list = self.get_commit_metrics(cwd, target_commits)
        
        # ルールベース分析
        rule_based_proposals = self.generate_rule_based_proposals(metrics_list)
        
        # AI分析も実行（下位互換性とより高度な検出のため）
        commit_details = self.get_commit_details(cwd, target_commits[:5])  # AI分析は5件まで
        ai_success, ai_proposals = self._generate_squash_proposals(log_output, commit_details)
        
        # 両方の提案をマージ（ルールベースを優先）
        all_proposals = rule_based_proposals[:]
        
        if ai_success:
            # 重複を避けながらAI提案を追加
            for ai_proposal in ai_proposals:
                # 既存のルールベース提案と重複しないかチェック
                is_duplicate = False
                for rule_proposal in rule_based_proposals:
                    if (set(ai_proposal.source_commits) & set(rule_proposal.source_commits) or
                        ai_proposal.target_commit == rule_proposal.target_commit):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    ai_proposal.confidence_score = 0.7  # AI提案は信頼度を下げる
                    all_proposals.append(ai_proposal)
        
        return True, all_proposals
    
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