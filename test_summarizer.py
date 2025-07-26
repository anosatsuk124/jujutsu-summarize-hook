#!/usr/bin/env python3
"""
AI要約機能のテストスクリプト

このスクリプトは以下をテストします：
1. JujutsuSummarizerのインポート
2. LiteLLMの動作確認
3. 環境変数の設定確認
4. 実際のサマリー生成
"""

import os
import sys
from pathlib import Path

# パッケージのインポートパスを追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """インポートのテスト"""
    print("=== インポートテスト ===")
    
    try:
        import litellm
        print("✅ LiteLLM インポート成功")
    except ImportError as e:
        print(f"❌ LiteLLM インポート失敗: {e}")
        return False
    
    try:
        from jj_hook.summarizer import JujutsuSummarizer, SummaryConfig
        print("✅ JujutsuSummarizer インポート成功")
        return True
    except ImportError as e:
        print(f"❌ JujutsuSummarizer インポート失敗: {e}")
        return False

def test_environment():
    """環境変数のテスト"""
    print("\n=== 環境変数テスト ===")
    
    model = os.environ.get("JJ_HOOK_MODEL", "gpt-3.5-turbo")
    language = os.environ.get("JJ_HOOK_LANGUAGE", "english")
    
    print(f"モデル: {model}")
    print(f"言語: {language}")
    
    # API キーの確認
    api_keys = []
    if os.environ.get("OPENAI_API_KEY"):
        api_keys.append("OPENAI_API_KEY")
    if os.environ.get("ANTHROPIC_API_KEY"):
        api_keys.append("ANTHROPIC_API_KEY")
    if os.environ.get("GITHUB_TOKEN"):
        api_keys.append("GITHUB_TOKEN")
    
    if api_keys:
        print(f"✅ 設定されているAPI キー: {', '.join(api_keys)}")
    else:
        print("⚠️  API キーが設定されていません")
    
    return True

def test_summarizer_creation():
    """JujutsuSummarizerの作成テスト"""
    print("\n=== JujutsuSummarizer作成テスト ===")
    
    try:
        from jj_hook.summarizer import JujutsuSummarizer
        summarizer = JujutsuSummarizer()
        print("✅ JujutsuSummarizer作成成功")
        print(f"使用モデル: {summarizer.config.model}")
        print(f"言語設定: {summarizer.config.prompt_language}")
        return summarizer
    except Exception as e:
        print(f"❌ JujutsuSummarizer作成失敗: {type(e).__name__}: {e}")
        return None

def test_jj_commands():
    """jjコマンドのテスト"""
    print("\n=== jjコマンドテスト ===")
    
    import subprocess
    
    try:
        # jj root
        result = subprocess.run(
            ["jj", "root"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ jj root 成功")
            print(f"リポジトリルート: {result.stdout.strip()}")
        else:
            print("❌ jj root 失敗 (Jujutsuリポジトリではない可能性)")
            return False
    except Exception as e:
        print(f"❌ jj root 実行エラー: {e}")
        return False
    
    try:
        # jj status
        result = subprocess.run(
            ["jj", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ jj status 成功")
            status = result.stdout.strip()
            if status:
                print(f"ステータス: {status[:100]}...")
            else:
                print("ステータス: 変更なし")
        else:
            print(f"❌ jj status 失敗: {result.stderr}")
    except Exception as e:
        print(f"❌ jj status 実行エラー: {e}")
    
    return True

def test_summary_generation(summarizer):
    """サマリー生成のテスト"""
    print("\n=== サマリー生成テスト ===")
    
    if not summarizer:
        print("❌ Summarizerが利用できません")
        return False
    
    try:
        cwd = os.getcwd()
        success, summary = summarizer.generate_commit_summary(cwd)
        
        if success:
            print(f"✅ サマリー生成成功: {summary}")
        else:
            print(f"⚠️  サマリー生成失敗: {summary}")
        
        return success
    except Exception as e:
        print(f"❌ サマリー生成でエラー: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メイン処理"""
    print("AI要約機能テストスクリプト - 更新版")
    print("=" * 40)
    
    # テストの実行
    if not test_imports():
        sys.exit(1)
    
    test_environment()
    
    summarizer = test_summarizer_creation()
    
    if not test_jj_commands():
        print("\n⚠️  Jujutsuリポジトリではないため、一部のテストをスキップします")
    
    test_summary_generation(summarizer)
    
    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    main()