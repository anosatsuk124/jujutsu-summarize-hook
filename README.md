# vcs-cc-hook

This repository provides AI-powered hooks for Claude Code that integrate with both Jujutsu (jj) and Git version control systems with automatic detection and VCS-specific optimization.

## Features

- **Multi-VCS Support**: Automatic detection and support for both Jujutsu (jj) and Git repositories
- **Automatic New Branch/Revision Creation**: Create new branches (Git) or revisions (Jujutsu) before file edits
- **Automatic Commits**: Automatically commit with AI-generated summaries after file edits
- **Sub-agent Integration**: VCS-specific sub-agents (jj-commit-organizer, git-commit-organizer, vcs-commit-organizer) for intelligent commit management
- **Slash Command Support**: Multiple slash commands for VCS-specific and generic commit organization
- **Template System**: Customizable prompt templates for different languages and scenarios
- **GitHub Copilot Integration**: Built-in support for GitHub Copilot with OAuth authentication
- **Multi-language Support**: Support for both English and Japanese commit messages and branch names
- **Multiple LLM Providers**: Support for OpenAI, Anthropic, GitHub Copilot, local models, and more
- **Bulk Installation**: Install all components (hooks, sub-agents, slash commands) at once
- **Three Command Options**: VCS-specific (`jj-cc-hook`, `git-cc-hook`) and universal (`vcs-cc-hook`) commands

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)
- [Jujutsu (jj)](https://github.com/martinvonz/jj) or [Git](https://git-scm.com/)
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

### 3. Use anywhere you want (hooks/agents installation in a local directory)

```bash
vcs-cc-hook install-all
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
vcs-cc-hook install --path .
```

Install hooks in the current directory:

```bash
vcs-cc-hook install
```

### 3. Configure LLM Provider

#### GitHub Copilot (Recommended)

GitHub Copilot is the recommended LLM provider as it offers seamless authentication through your existing GitHub account and doesn't require managing API keys.

```bash
# Set GitHub Copilot as the model
export VCS_CC_HOOK_MODEL="github_copilot/gpt-4"

# Authenticate with GitHub Copilot (opens browser for OAuth)
vcs-cc-hook auth github-copilot

# Check authentication status
vcs-cc-hook auth --check
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
export VCS_CC_HOOK_MODEL="gpt-4"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"
export VCS_CC_HOOK_MODEL="claude-3-sonnet-20240229"

# Language setting (optional)
export VCS_CC_HOOK_LANGUAGE="english"
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


#### Sub-agent Integration Workflow

```bash
# Install sub-agent
vcs-cc-hook install-agent --global

# Use in Claude Code:
# "jj-commit-organizer サブエージェントを使ってコミット履歴を整理して"
# → Sub-agent analyzes commit history
# → Provides organization suggestions
# → Executes approved changes
```

#### Slash Command Workflow

```bash
# Install slash command
vcs-cc-hook install-slash-command --global

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
| `VCS_CC_HOOK_MODEL` | `gpt-3.5-turbo` | LLM model to use (universal) |
| `JJ_CC_HOOK_MODEL` | `gpt-3.5-turbo` | LLM model to use (jj-cc-hook) |
| `GIT_CC_HOOK_MODEL` | `gpt-3.5-turbo` | LLM model to use (git-cc-hook) |
| `VCS_CC_HOOK_LANGUAGE` | `english` | Prompt language (`english` or `japanese`) |
| `VCS_CC_HOOK_MAX_TOKENS` | `100` | Maximum tokens for AI responses |
| `VCS_CC_HOOK_TEMPERATURE` | `0.1` | Generation temperature (0.0-1.0) |

### Template System

The template system allows customization of AI prompts for different scenarios:

- **Templates Directory**: `src/vcs_cc_hook/templates/`
- **VCS-Specific Templates**: Organized by VCS type (`jj/`, `git/`, `common/`)
- **Language Support**: Templates automatically use the language specified in environment variables
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

### Summarize (AI-Powered Commit)

```bash
# Summarize uncommitted changes and create a commit using AI
vcs-cc-hook summarize

# Summarize from a specific path (e.g., a subdirectory)
vcs-cc-hook summarize --path ./src/my_module
```

### Authentication

```bash
# Authenticate with GitHub Copilot
vcs-cc-hook auth github-copilot

# Check authentication status
vcs-cc-hook auth --check
```

### Installation

```bash
# Install hooks in current directory
vcs-cc-hook install

# Install hooks in specific directory
vcs-cc-hook install --path /path/to/project

# Install sub-agent globally
vcs-cc-hook install-agent --global

# Install sub-agent in specific directory
vcs-cc-hook install-agent --path /path/to/project

# Install slash command globally
vcs-cc-hook install-slash-command --global

# Install slash command in specific directory
vcs-cc-hook install-slash-command --path /path/to/project

# Install all components at once
vcs-cc-hook install-all --global

# Preview installation without making changes
vcs-cc-hook install-all --dry-run
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
src/vcs_cc_hook/
├── __init__.py
├── cli_vcs.py                  # Universal CLI entry point (VCS auto-detection)
├── cli_jj.py                   # Jujutsu-specific CLI entry point
├── cli_git.py                  # Git-specific CLI entry point
├── summarizer.py               # AI functionality with multi-VCS support
├── template_loader.py          # Template system for prompts
├── vcs_backend.py              # VCS abstraction layer
├── jujutsu_backend.py          # Jujutsu implementation
├── git_backend.py              # Git implementation
├── hooks/
│   ├── __init__.py
│   ├── pre_tool_use.py         # Pre file-edit hook (new branch/revision creation)
│   └── post_tool_use.py        # Post file-edit hook (auto commit)
└── templates/
    ├── common/                 # Shared templates
    │   ├── agent_content.md    # Sub-agent definition template
    │   ├── branch_name.md      # Branch name generation template
    │   ├── commit_analysis.md  # Commit analysis template
    │   └── slash_command.md    # Slash command template
    ├── jj/                     # Jujutsu-specific templates
    │   ├── commit_message.md   # Jujutsu commit message template
    │   └── revision_description.md # Revision description template
    └── git/                    # Git-specific templates
        ├── commit_message.md   # Git commit message template
        └── commit_description.md # Commit description template
```

## Hook Details

### PreToolUse Hook (pre_tool_use.py)
- **Trigger**: Before Edit, Write, MultiEdit tool calls
- **Function**: Creates new branches (Git) or revisions (Jujutsu) with descriptive names
- **Behavior**: 
  - Auto-detects VCS type (Git/Jujutsu)
  - Skips temporary files and configuration files
  - Only creates new branches/revisions when appropriate
  - Generates descriptions based on file path and content

### PostToolUse Hook (post_tool_use.py)
- **Trigger**: After Edit, Write, MultiEdit tool calls
- **Function**: Automatically commits changes with AI-generated summaries
- **Behavior**:
  - Uses VCS-specific templates for commit messages
  - Uses LiteLLM to generate context-aware commit messages
  - Falls back to simple messages if AI generation fails
  - Only commits when changes are detected
  - Supports both Git and Jujutsu workflows

## Language Support

This project supports both English and Japanese:

- **English** (default): Set `JJ_HOOK_LANGUAGE=english` or leave unset
- **Japanese**: Set `JJ_HOOK_LANGUAGE=japanese`

For Japanese documentation, see [README.ja.md](README.ja.md).

## License

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
