# jujutsu-summarize-hook

This repository provides AI-powered hooks for Claude Code that integrate with the Jujutsu version control system (jj).

## Features

- **Automatic New Commit Creation**: Automatically create new commits before file edits using `jj new`
- **Automatic Commits**: Automatically commit with AI-generated summaries after file edits
- **AI-Powered Commit History Organization**: Analyze and reorganize commit history using `jj-hook organize`
- **Sub-agent Integration**: jj-commit-organizer sub-agent for intelligent commit management
- **Slash Command Support**: `/jj-commit-organizer` command for quick access to commit organization
- **Template System**: Customizable prompt templates for different languages and scenarios
- **GitHub Copilot Integration**: Built-in support for GitHub Copilot with OAuth authentication
- **Multi-language Support**: Support for both English and Japanese commit messages and branch names
- **Multiple LLM Providers**: Support for OpenAI, Anthropic, GitHub Copilot, local models, and more
- **Bulk Installation**: Install all components (hooks, sub-agents, slash commands) at once

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)
- [Jujutsu (jj)](https://github.com/martinvonz/jj)
- [Claude Code](https://claude.ai/code)
- [mise](https://mise.jdx.dev/) (recommended)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/anosatsuk124/jujutsu-summarize-hook.git
```

### 2. Installation

```bash
cd jujutsu-summarize-hook
uv tool install .
```
```

### 3. Use anywhere you want (hooks/agents installation in a local directory)

```bash
jj-hook install-all
```

## Installation for development

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

1. **Before File Edits**: Automatic new commit creation before Edit, Write, MultiEdit tool usage using `jj new`
2. **After File Edits**: Automatic commits after file edits with AI-generated messages

### Example Workflows

#### Basic File Editing Workflow

```bash
# Edit files using Claude Code
# → Before editing: Automatic new commit creation with `jj new`
# → After editing: Automatic commit with AI-generated message
```

#### Commit History Organization Workflow

```bash
# Analyze and organize commit history
jj-hook organize

# Example output:
# 🔍 Analyzing 10 commits...
# ✅ Found 3 organization opportunities:
#   1. Squash "fix typo" into "Add new feature" (confidence: 0.9)
#   2. Squash "remove debug" into "Add logging" (confidence: 0.8)
#   3. Create feature branch for commits 5-7 (confidence: 0.7)
```

#### Sub-agent Integration Workflow

```bash
# Install sub-agent
jj-hook install-agent --global

# Use in Claude Code:
# "jj-commit-organizer サブエージェントを使ってコミット履歴を整理して"
# → Sub-agent analyzes commit history
# → Provides organization suggestions
# → Executes approved changes
```

#### Slash Command Workflow

```bash
# Install slash command
jj-hook install-slash-command --global

# Use in Claude Code:
# Type: /jj-commit-organizer
# → Automatically invokes sub-agent
# → Analyzes and organizes commit history
# → Creates backup before changes
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JJ_HOOK_MODEL` | `gpt-3.5-turbo` | LLM model to use |
| `JJ_HOOK_LANGUAGE` | `english` | Prompt language (`english` or `japanese`) |
| `JJ_HOOK_MAX_TOKENS` | `100` | Maximum tokens for AI responses |
| `JJ_HOOK_TEMPERATURE` | `0.1` | Generation temperature (0.0-1.0) |

### Template System

The template system allows customization of AI prompts for different scenarios:

- **Templates Directory**: `src/jj_hook/templates/`
- **Language Support**: Templates automatically use the language specified in `JJ_HOOK_LANGUAGE`
- **Template Variables**: Templates support variable substitution using Python's `str.format()` syntax

#### Available Templates

| Template | Purpose | Variables |
|----------|---------|-----------|
| `commit_message.md` | Generate commit messages | `changes`, `language` |
| `branch_name.md` | Generate branch names | `prompt`, `language` |
| `commit_analysis.md` | Analyze commit history | `commits`, `language` |
| `revision_description.md` | Generate revision descriptions | `file_path`, `content`, `language` |
| `agent_content.md` | Sub-agent definitions | `language` |

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

# Install sub-agent globally
jj-hook install-agent --global

# Install sub-agent in specific directory
jj-hook install-agent --path /path/to/project

# Install slash command globally
jj-hook install-slash-command --global

# Install slash command in specific directory
jj-hook install-slash-command --path /path/to/project

# Install all components at once
jj-hook install-all --global

# Preview installation without making changes
jj-hook install-all --dry-run
```

### Commit History Organization

The `organize` command uses the jj-commit-organizer sub-agent to analyze and organize your commit history:

```bash
# Analyze and organize commit history
jj-hook organize

# Preview organization without making changes
jj-hook organize --dry-run

# Automatically organize without confirmation
jj-hook organize --auto

# Limit analysis to last N commits
jj-hook organize --limit 20

# Set thresholds for commit size classification
jj-hook organize --tiny-threshold 5 --small-threshold 20

# Aggressive mode (includes lower confidence suggestions)
jj-hook organize --aggressive

# Exclude commits matching patterns
jj-hook organize --exclude-pattern "WIP" --exclude-pattern "temp"
```

This command:
1. Analyzes your commit history using `jj log`
2. Checks for safety concerns
3. Creates a backup bookmark
4. Generates a prompt for the jj-commit-organizer sub-agent
5. Provides instructions for using the sub-agent to organize commits

The jj-commit-organizer sub-agent can:
- Identify logically related commits to squash using `jj squash --from <source> --into <target> -u`
- Suggest appropriate commit messages with the `-m` option
- Create bookmarks for feature branches
- Perform sequential commit integration while preserving target messages

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
├── cli.py                      # CLI entry point (includes organize command)
├── summarizer.py               # AI functionality
├── config.py                   # Configuration management
├── template_loader.py          # Template system for prompts
├── hooks/
│   ├── __init__.py
│   ├── pre_tool_use.py         # Pre file-edit hook (new commit creation)
│   └── post_tool_use.py        # Post file-edit hook (auto commit)
└── templates/
    ├── commit_message.md       # Commit message generation template
    ├── branch_name.md          # Branch name generation template
    ├── commit_analysis.md      # Commit analysis template
    ├── revision_description.md # Revision description template
    └── agent_content.md        # Sub-agent definition template
```

## Hook Details

### PreToolUse Hook (pre_tool_use.py)
- **Trigger**: Before Edit, Write, MultiEdit tool calls
- **Function**: Creates new Jujutsu commits with descriptive names using `jj new`
- **Behavior**: 
  - Skips temporary files and configuration files
  - Only creates new commits when no uncommitted changes exist
  - Generates commit descriptions based on file path and content

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

## License

```
```
   Copyright 2025 Satsuki Akiba <anosatsuk124@gmail.com>

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
```
