# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository provides AI-powered hooks for Claude Code that integrate with the Jujutsu version control system (jj). The project includes a CLI tool `jj-hook` for setting up automatic commit and branch creation workflows using LiteLLM.

## Project Structure

### Core Files
- `pyproject.toml` - Python package configuration using uv/hatchling
- `.mise.toml` - Development environment and task configuration
- `README.md` - Complete project documentation with installation instructions

### Source Code (`src/jj_hook/`)
- `cli.py` - Main CLI implementation with click framework
- `summarizer.py` - LiteLLM integration for AI-powered commit messages
- `config.py` - Configuration management with environment variables
- `template_loader.py` - Template system for loading slash command prompts
- `hooks/post_tool_use.py` - Hook for automatic commits after file edits
- `hooks/user_prompt_submit.py` - Hook for automatic branch creation from prompts

### Documentation
- `docs/anthropic/hooks.md` - Claude Code hooks reference (from Anthropic docs)

## Development Environment

### Package Management
- Uses `uv` for Python package management
- Uses `mise` for environment management and task running
- Python 3.9+ required

### Key Dependencies
- `click` - CLI framework
- `litellm` - Multi-provider LLM integration
- `rich` - Terminal formatting
- `pydantic` - Configuration validation

### Development Commands
```bash
mise install          # Install Python and tools
uv sync --dev         # Install dependencies
uv run ruff format .  # Format code
uv run mypy src/     # Type checking
uv run pytest       # Run tests
```

## CLI Usage

### Installing Hooks
```bash
jj-hook install --path .  # Install in specific directory
jj-hook install           # Install in current directory
```

### Configuration
Environment variables for LLM configuration:
- `JJ_HOOK_MODEL` - LLM model (default: gpt-3.5-turbo)
- `JJ_HOOK_LANGUAGE` - Prompt language (default: english)
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` - API keys

## Hook Functionality

### PostToolUse Hook
- Triggers after Edit/Write/MultiEdit operations
- Generates AI-powered commit messages from `jj status` and `jj diff`
- Automatically commits changes with descriptive messages

### UserPromptSubmit Hook  
- Triggers when user submits prompts to Claude Code
- Creates new jj branches for work-related prompts
- Skips question-type prompts to avoid unnecessary branches

## Implementation Notes

### Error Handling
- Graceful fallbacks when LiteLLM is unavailable
- Non-blocking failures for branch creation
- Proper exit codes for Claude Code hook system

### Localization
- Primary language: Japanese (as per CLAUDE.md requirements)
- Supports both Japanese and English prompts
- Japanese commit messages and error reporting

### Security
- No hardcoded API keys or secrets
- Environment variable configuration only
- Safe subprocess execution with timeouts