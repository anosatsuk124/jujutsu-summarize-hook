# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains hooks and configurations for Claude Code, specifically focused on integrating with the Jujutsu version control system (jj). The project provides a CLI tool `jj-hook` for installing hooks that work with Claude Code's hook system.

## Project Structure

- `README.md` - Main project documentation with CLI usage instructions
- `docs/anthropic/` - Documentation directory containing Claude Code hook reference materials
  - `hooks.md` - Comprehensive Claude Code hooks reference documentation
  - `READEME.md` - Directory overview explaining the Anthropic documentation contents

## CLI Usage

### Installing Hooks

Install hooks in a specific directory:
```bash
jj-hook install --path .
```

Install hooks in the current directory:
```bash
jj-hook install
```

## Development Context

This is a documentation and configuration project focused on:
- Jujutsu (jj) version control system integration
- Claude Code hook system configuration
- Providing reference documentation for hook development

The repository contains no build system, test framework, or package management files, indicating it's primarily a documentation and configuration repository rather than a traditional software project.

## Key Files

- `README.md:6-20` - Contains the main CLI usage instructions for the `jj-hook` tool
- `docs/anthropic/hooks.md` - Complete reference documentation for Claude Code hooks system (sourced from Anthropic's official documentation)