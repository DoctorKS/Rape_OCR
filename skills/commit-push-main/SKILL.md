---
name: commit-push-main
description: >-
  Commit the current working changes and publish them straight to origin/main
  via fast-forward (no force, no pull request), then fast-forward the local
  main worktree to match. Use this skill WHENEVER the user authorizes or
  instructs a commit-and-push in this repo — explicit phrasings like "commit
  and push", "go ahead and push it", "ship it", "push to main", as well as a
  bare "sure" / "yes" / "do it" given in direct response to an offer to commit
  and push. The user works on short-lived branches (often a worktree branch)
  but wants main to be the published target, so do not push only to the
  feature branch and stop — carry it through to origin/main and local main.
---

# Commit & publish to origin/main

This repo (a single-developer personal project) uses `main` as the live
branch. Work often happens on a worktree/feature branch, but "commit and
push" here means: get the change onto `origin/main` and keep the local
`main` checkout in sync. There is no PR review step and no separate
integration branch — keeping the published history linear (fast-forward
only) is what the user wants, because a tangle of merge commits on a
solo project is just noise.

Only run this when the user has actually given the go-ahead for a commit
**and** a push. If they only asked to commit, stop after the commit.

## Step 1 — Commit the working changes

Follow the normal careful-commit routine:

1. In parallel: `git status`, `git diff` (staged + unstaged), and
   `git log --oneline -5` to match the repo's message style.
2. Stage the specific files that belong to this change by name. Avoid
   `git add -A` / `git add .` — it risks sweeping in secrets (`.env`,
   credentials) or unrelated files. Never commit files that look like
   secrets; warn the user if they explicitly ask to.
3. Commit with a concise message (why, not just what) using a HEREDOC,
   ending with the trailer:

   ```
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```

If there is nothing to commit, don't create an empty commit — just
proceed to publishing whatever is already ahead of `origin/main`.

## Step 2 — Verify it's a clean fast-forward

Pushing to a shared `main` is hard to undo, so confirm the publish is a
pure fast-forward before touching the remote:

```bash
git fetch origin
git log --oneline origin/main..HEAD   # commits we will add
git log --oneline HEAD..origin/main   # commits we are missing (should be empty)
git merge-base --is-ancestor origin/main HEAD && echo FF-OK || echo NOT-FF
```

- **FF-OK** (origin/main is an ancestor of HEAD): continue to Step 3.
- **NOT-FF** (history diverged): **stop**. Do not force-push, do not
  rewrite `main`. Report the divergence to the user and offer to rebase
  the branch onto `origin/main` (or merge) first, then re-run. Forcing
  would discard someone's published work — never do it here without an
  explicit, specific instruction.

## Step 3 — Publish to origin/main

From the current branch, push the commits to `main` with a refspec — no
branch checkout needed, works from a worktree branch:

```bash
git push origin HEAD:main
```

This is a normal fast-forward push. Never add `--force`/`--force-with-lease`
or `--no-verify` unless the user explicitly and specifically asks for it.
Then verify:

```bash
git fetch origin && git log --oneline -3 origin/main
```

The top commit should be the one you just made.

## Step 4 — Fast-forward the local main worktree

`main` is usually checked out in another worktree, so it won't move on
its own and will silently fall behind. Bring it up to date:

1. Find the main checkout: `git worktree list` — the entry tagged
   `[main]`.
2. Check it's safe to advance (no conflicting uncommitted tracked
   changes): `git -C <main-worktree> status --short`. Untracked files
   like `.claude/` are fine and won't be disturbed by a fast-forward.
3. Fast-forward it (don't `git checkout main` from another worktree —
   git won't allow main to be checked out twice):

   ```bash
   git -C <main-worktree> merge --ff-only origin/main
   ```

4. Confirm: `git -C <main-worktree> status --short --branch` should show
   `## main...origin/main` with no ahead/behind.

## Step 5 — Report

Give the user a tight summary: the commit hash + subject, the
`old..new` range now on `origin/main`, confirmation that local `main`
fast-forwarded, and the commit URL
(`https://github.com/<owner>/<repo>/commit/<hash>`; resolve the
owner/repo from `git remote get-url origin` if unknown).

## Safety boundaries

- Fast-forward only. Diverged history → stop and ask, never force.
- Stage named files, not blanket adds; don't commit secrets.
- Never skip hooks or bypass signing unless explicitly requested.
- This skill is authorized to push to `main` *because the user asked for
  exactly this workflow* — that standing permission covers the
  fast-forward case only. Anything destructive (force-push, history
  rewrite, deleting refs) still needs a fresh, explicit go-ahead.
