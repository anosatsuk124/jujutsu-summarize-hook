# jujutsu-summarize-hook

This repository provides AI-powered hooks for Claude Code that integrate with the Jujutsu version control system (jj).

## Features

- **Automatic Branch Creation**: Automatically create new branches before file edits
- **Automatic Commits**: Automatically commit with AI-generated summaries after file edits
- **GitHub Copilot Integration**: Built-in support for GitHub Copilot with OAuth authentication
- **Multi-language Support**: Support for both English and Japanese commit messages and branch names
- **Multiple LLM Providers**: Support for OpenAI, Anthropic, GitHub Copilot, local models, and more

## Requirements

- Python 3.9+
- [Jujutsu (jj)](https://github.com/martinvonz/jj)
- [Claude Code](https://claude.ai/code)
- [mise](https://mise.jdx.dev/) (recommended)
- [uv](https://docs.astral.sh/uv/) (recommended)

## Installation

### 1. Project Setup

```bash
# Set up development environment
mise install
uv sync

# Install package
uv pip install -e .
```

### 2. Configure Claude Code Hooks

Install hooks in a specific project directory:

```bash
jj-hook install --path .
```

Install hooks in the current directory:

```bash
jj-hook install
```

### 3. Configure LLM Provider

#### GitHub Copilot (Recommended)

GitHub Copilot is the recommended LLM provider as it offers seamless authentication through your existing GitHub account and doesn't require managing API keys.

```bash
# Set GitHub Copilot as the model
export JJ_HOOK_MODEL="github_copilot/gpt-4"

# Authenticate with GitHub Copilot (opens browser for OAuth)
jj-hook auth github-copilot

# Check authentication status
jj-hook auth --check
```

The authentication process will:
1. Open your default browser to GitHub OAuth page
2. Prompt you to authorize the application 
3. Store the authentication token securely for future use

#### Other Providers

Set up API keys using environment variables:

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"
export JJ_HOOK_MODEL="gpt-4"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"
export JJ_HOOK_MODEL="claude-3-sonnet-20240229"

# Language setting (optional)
export JJ_HOOK_LANGUAGE="english"
```

## Usage

### Automatic Hook Execution

1. **On User Prompt Submit**: Automatic branch creation when submitting work-related prompts
2. **Before File Edits**: Automatic branch creation before Edit, Write, MultiEdit tool usage  
3. **After File Edits**: Automatic commits after file edits with AI-generated messages

### Example Workflow

```bash
# Submit a work-related prompt to Claude Code
"Add user authentication feature"
# → Automatic branch creation: "feat/add-user-authentication-feature"

# Edit files using Claude Code
# → Before editing: Additional branch creation if needed
# → After editing: Automatic commit with AI-generated message
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JJ_HOOK_MODEL` | `gpt-3.5-turbo` | LLM model to use |
| `JJ_HOOK_LANGUAGE` | `english` | Prompt language |
| `JJ_HOOK_MAX_TOKENS` | `100` | Maximum tokens |
| `JJ_HOOK_TEMPERATURE` | `0.1` | Generation temperature |

### Supported LLM Providers

- **GitHub Copilot** (github_copilot/gpt-4) - Recommended
- OpenAI (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic (claude-3-sonnet, claude-3-haiku, etc.)
- Local models (Ollama, etc.)
- All providers supported by LiteLLM

## CLI Commands

### Authentication

```bash
# Authenticate with GitHub Copilot
jj-hook auth github-copilot

# Check authentication status
jj-hook auth --check
```

### Installation

```bash
# Install hooks in current directory
jj-hook install

# Install hooks in specific directory
jj-hook install --path /path/to/project
```

## Development

### Development Environment Setup

```bash
# Install dependencies
mise install
uv sync --dev

# Code formatting
uv run ruff format .

# Type checking
uv run mypy src/

# Run tests
uv run pytest
```

### Project Structure

```
src/jj_hook/
├── __init__.py
├── cli.py                      # CLI entry point
├── summarizer.py               # AI functionality
├── config.py                   # Configuration management
└── hooks/
    ├── __init__.py
    ├── user_prompt_submit.py   # User prompt hook (branch creation)
    ├── pre_tool_use.py         # Pre file-edit hook (branch creation)
    └── post_tool_use.py        # Post file-edit hook (auto commit)
```

## Hook Details

### UserPromptSubmit Hook (user_prompt_submit.py)
- **Trigger**: When user submits prompts to Claude Code
- **Function**: Creates new Jujutsu branches for work-related prompts
- **Behavior**:
  - Analyzes prompt content to determine if it's work-related
  - Skips question-type prompts to avoid unnecessary branches
  - Generates descriptive branch names from prompt content

### PreToolUse Hook (pre_tool_use.py)
- **Trigger**: Before Edit, Write, MultiEdit tool calls
- **Function**: Creates new Jujutsu branches with descriptive names
- **Behavior**: 
  - Skips temporary files and configuration files
  - Only creates branches when no uncommitted changes exist
  - Generates branch descriptions based on file path and content

### PostToolUse Hook (post_tool_use.py)
- **Trigger**: After Edit, Write, MultiEdit tool calls
- **Function**: Automatically commits changes with AI-generated summaries
- **Behavior**:
  - Uses LiteLLM to generate commit messages
  - Falls back to simple messages if AI generation fails
  - Only commits when changes are detected

## Language Support

This project supports both English and Japanese:

- **English** (default): Set `JJ_HOOK_LANGUAGE=english` or leave unset
- **Japanese**: Set `JJ_HOOK_LANGUAGE=japanese`

For Japanese documentation, see [README.ja.md](README.ja.md).