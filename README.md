# jujutsu-summarize-hook

This repository provides AI-powered hooks for Claude Code that integrate with the Jujutsu version control system (jj).

## Features

- **Automatic Commits**: Automatically commit with AI-generated summaries after file edits
- **Automatic Branch Creation**: Automatically create new branches from user prompts
- **Multi-language Support**: Support for both English and Japanese commit messages and branch names
- **Multiple LLM Providers**: Support for OpenAI, Anthropic, local models, and more

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

Set up API keys using environment variables:

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# Specify model to use (optional)
export JJ_HOOK_MODEL="gpt-4"
export JJ_HOOK_LANGUAGE="english"
```

## Usage

### Automatic Hook Execution

1. **After File Edits**: Automatic commits after Edit, Write, MultiEdit tool usage
2. **On Prompt Submission**: Automatic branch creation for work-related prompts

### Example Workflow

```bash
# Submit a prompt in Claude Code
"Add user authentication feature"
# → A new branch is automatically created

# Edit files using Claude Code
# → After editing is complete, automatic commit with AI-generated message
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

- OpenAI (gpt-3.5-turbo, gpt-4, etc.)
- Anthropic (claude-3-sonnet, claude-3-haiku, etc.)
- Local models (Ollama, etc.)
- All providers supported by LiteLLM

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
├── cli.py              # CLI entry point
├── summarizer.py       # AI functionality
├── config.py          # Configuration management
└── hooks/
    ├── __init__.py
    ├── post_tool_use.py     # Post file-edit hook
    └── user_prompt_submit.py # Prompt submission hook
```

## Language Support

This project supports both English and Japanese:

- **English** (default): Set `JJ_HOOK_LANGUAGE=english` or leave unset
- **Japanese**: Set `JJ_HOOK_LANGUAGE=japanese`

For Japanese documentation, see [README.ja.md](README.ja.md).