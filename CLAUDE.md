# CLAUDE.md

This file provides guidance to Claude Code and other AI assistants working in this repository.

---

## Repository Overview

**Repository:** `alexnefera-dot/cladue`
**Status:** Newly initialized repository

> This repository is in its initial state. Update this section as the project evolves to describe its purpose, primary use case, and high-level architecture.

---

## Project Structure

```
cladue/
├── CLAUDE.md          # AI assistant guidance (this file)
└── .git/              # Git metadata
```

As the project grows, document new top-level directories here. Example:

```
cladue/
├── src/               # Source code
├── tests/             # Test suite
├── docs/              # Documentation
├── scripts/           # Utility scripts
├── .github/           # GitHub Actions / CI configuration
└── CLAUDE.md
```

---

## Development Setup

### Prerequisites

Document required tools here as they are introduced. For example:
- Node.js >= 20, Python >= 3.11, Go >= 1.22, Rust >= 1.75, etc.
- Package manager (npm, pnpm, yarn, pip, cargo, etc.)
- Any required system dependencies

### Initial Setup

```bash
# Clone the repository
git clone <repo-url>
cd cladue

# Install dependencies (update command to match the project)
# npm install
# pip install -e ".[dev]"
# cargo build
```

### Environment Variables

If the project requires environment variables, document them here. Prefer an `.env.example` file at the root:

```bash
cp .env.example .env
# Fill in values in .env
```

---

## Common Commands

Update this section with the actual commands once the project is set up.

| Task | Command |
|------|---------|
| Install dependencies | `<command>` |
| Run development server | `<command>` |
| Run all tests | `<command>` |
| Run linter | `<command>` |
| Format code | `<command>` |
| Type check | `<command>` |
| Build for production | `<command>` |

---

## Testing

Document the test framework, how to run tests, and how to write new ones.

```bash
# Run all tests
<test command>

# Run a single test file
<test command> path/to/test

# Run tests matching a pattern
<test command> -k "pattern"

# Run with coverage
<test command> --coverage
```

### Testing Conventions

- Write tests for all new features and bug fixes
- Test files should live adjacent to the code they test, or in a dedicated `tests/` directory
- Prefer unit tests; add integration tests for critical paths
- Tests must pass before merging any PR

---

## Code Style & Linting

Document the linting and formatting tools here once established.

```bash
# Lint
<lint command>

# Auto-fix lint issues
<lint command> --fix

# Format code
<format command>
```

### Style Conventions

- Follow the existing code style in each file
- Use consistent naming conventions across the codebase (document the convention here)
- Keep functions small and focused — single responsibility principle
- Prefer explicit over implicit
- Add comments only where logic is non-obvious; code should be self-documenting

---

## Git Workflow

### Branch Naming

```
main              # Protected; production-ready code
feature/<name>    # New features
fix/<name>        # Bug fixes
chore/<name>      # Maintenance, dependency updates, etc.
claude/<name>     # Branches created by Claude Code
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

**Examples:**

```
feat(auth): add OAuth2 login support
fix(api): handle null response from external service
docs: update setup instructions in CLAUDE.md
chore: upgrade dependencies to latest patch versions
```

### Pull Request Process

1. Create a branch from `main`
2. Make changes with clear, atomic commits
3. Ensure all tests and linters pass
4. Open a PR with a descriptive title and summary
5. Request review; address feedback
6. Squash and merge once approved

---

## Architecture & Key Conventions

> Fill this section in as the architecture becomes defined.

### Directory Conventions

Describe where different types of code live (e.g., "API handlers go in `src/api/`", "shared utilities go in `src/lib/`").

### Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Files | `kebab-case` | `user-service.ts` |
| Classes | `PascalCase` | `UserService` |
| Functions/variables | `camelCase` | `getUserById` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Database tables | `snake_case` | `user_accounts` |

> Adjust the table above to match the actual conventions used in this project.

### Error Handling

Document the preferred approach to error handling — whether that's exceptions, result types, error codes, etc.

### Logging

Document the logging library and conventions (log levels, structured fields, etc.).

---

## External Services & Dependencies

Document any external services the project depends on:

| Service | Purpose | Local Alternative |
|---------|---------|------------------|
| _None yet_ | — | — |

---

## CI/CD

Document the CI pipeline once configured. For GitHub Actions, the workflow files live in `.github/workflows/`.

**Expected checks on every PR:**
- Tests pass
- Linting passes
- Type checking passes (if applicable)
- Build succeeds (if applicable)

---

## Security

- Never commit secrets, API keys, or credentials — use environment variables
- Do not disable security linting rules without a documented reason
- Validate all user input at system boundaries
- Keep dependencies up to date; address high/critical CVEs promptly

---

## AI Assistant Notes

### What to Do

- Read existing code before modifying it; understand context first
- Follow existing patterns and conventions in each file
- Keep changes minimal and focused — avoid scope creep
- Run tests and linters after making changes
- Write clear commit messages following the Conventional Commits spec

### What to Avoid

- Do not add unnecessary abstractions, utilities, or helpers for one-time use
- Do not add comments or docstrings to code you didn't change
- Do not introduce new dependencies without discussion
- Do not refactor code beyond the scope of the task
- Do not add error handling for scenarios that cannot happen
- Do not commit `.env` files, secrets, or credentials

### Branch Discipline

AI-created branches follow the pattern `claude/<description>-<session-id>`. Always:
1. Develop on the designated branch
2. Commit with descriptive messages
3. Push with `git push -u origin <branch-name>`

---

*This CLAUDE.md was auto-generated for an empty repository. Update all sections as the project is built out.*
