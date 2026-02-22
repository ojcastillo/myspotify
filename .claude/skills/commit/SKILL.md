---
name: commit
description: Create a git commit with auto-formatting, CLAUDE.md update proposals, and conventional commit messages. Use when the user wants to commit changes.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep, Edit
---

# Commit Skill

When the user invokes `/commit`, follow these steps **in order**:

## Step 1: Auto-format with Black

Run `black` on all modified/staged Python files:

```
black $(git diff --name-only --diff-filter=d HEAD | grep '\.py$')
```

If no Python files changed, skip this step. Report what was reformatted (if anything).

## Step 2: Review changes and propose CLAUDE.md updates

1. Run `git diff` (staged + unstaged) and `git status` to understand all changes.
2. Read the current `CLAUDE.md` file.
3. Analyze whether the changes make any part of `CLAUDE.md` out of date. Consider:
   - New or renamed files/modules
   - Changed architecture or data flow
   - New or removed commands, scripts, or environment variables
   - Changed database schema or API
   - New dependencies or configuration
4. If `CLAUDE.md` needs updates:
   - Clearly list the proposed changes and **ask the user for approval** before editing.
   - Only edit `CLAUDE.md` after explicit approval.
5. If `CLAUDE.md` is already up to date, say so briefly and move on.

## Step 3: Create commit with conventional commit style

This repo uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Follow these rules:

### Format
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types used in this repo (pick the most appropriate):
- `feat`: A new feature or capability
- `fix`: A bug fix
- `refactor`: Code restructuring without behavior change
- `docs`: Documentation-only changes
- `chore`: Maintenance tasks (deps, gitignore, etc.)
- `style`: Formatting, whitespace (no logic change)
- `perf`: Performance improvement
- `test`: Adding or updating tests

### Rules
- Type and description are **required**. Scope is optional.
- Description should be lowercase, imperative mood, no period at end.
- Keep the first line under 72 characters.
- Use the body (separated by blank line) for additional context if the change is non-trivial.
- Append `!` after type/scope for breaking changes.

### Process
1. Run `git status` and `git diff --staged` to see what will be committed.
2. Run `git log --oneline -5` to see recent commit style for consistency.
3. Stage all relevant changed files (be specific, don't use `git add -A`).
4. Draft the commit message and **show it to the user for approval**.
5. After approval, create the commit using a HEREDOC:

```bash
git commit -m "$(cat <<'EOF'
<type>[scope]: <description>

<optional body>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

6. Run `git status` after committing to confirm success.

**IMPORTANT**: Always get user approval on the commit message before committing. Never amend previous commits unless explicitly asked.
