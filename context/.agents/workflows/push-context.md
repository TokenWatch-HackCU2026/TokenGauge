---
description: Auto-push changes in the overall project context folders (architecture, requirements, skills, tools) to origin/main
---

// turbo-all

This workflow stages and pushes any changes made to the "overall" project context folders:
- `context/architecture/`
- `context/requirements/`
- `context/skills/`
- `context/tools/`
- `context/.gitignore`
- `README.md`

The personal context folders (`.memory/`, `.prompts/`, `.agents/`) are gitignored and will never be pushed.

## Steps

1. Check git status to see what has changed.

```bash
cd /Users/Matthew/Desktop/CompSci/TokenGauge && git status
```

2. Stage only the overall context files (never the ignored personal folders).

```bash
cd /Users/Matthew/Desktop/CompSci/TokenGauge && git add context/architecture/ context/requirements/ context/skills/ context/tools/ context/.gitignore README.md
```

3. Commit with a timestamped message if there are staged changes.

```bash
cd /Users/Matthew/Desktop/CompSci/TokenGauge && git diff --cached --quiet || git commit -m "chore: auto-update project context [$(date '+%Y-%m-%d %H:%M')]"
```

4. Push the commit to origin/main.

```bash
cd /Users/Matthew/Desktop/CompSci/TokenGauge && git push origin main
```
