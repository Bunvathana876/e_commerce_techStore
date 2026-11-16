# Blue Panda Git Repository Migration Plan

**Status:** Plan only. No Git index entries, nested repositories, branches, remotes, history, or working-tree files were changed during this audit.

## Verified topology

The root repository is on `main` and has its own remote. Its index records these paths as mode `160000` gitlinks:

| Path | Root-recorded commit | Nested repository state |
|---|---|---|
| `backend/` | `999de816…` | Independent `main` repository and remote; clean; current commit differs from the root-recorded commit. |
| `mobile-app/` | `4aa7a690…` | Independent `main` repository and remote; clean; current commit differs from the root-recorded commit. |
| `web-app/` | `ea164cf2…` | Independent `main` repository and remote; current commit differs from the root-recorded commit; substantial staged/unstaged migration work exists. |

No `.gitmodules` file exists in the root worktree or root `HEAD`, and no root `submodule.*` configuration was found. Therefore these are orphaned gitlinks, not cloneable/reproducible Git submodules. A new clone of the root cannot discover the nested repository URLs through standard submodule commands.

`storefront/` and `management/` are currently ordinary untracked root directories rather than independent repositories or gitlinks. Root configuration and documentation couple them directly to the backend and mobile clients.

## Strategy comparison

### A. Proper submodules

Advantages: preserves independent histories/remotes and permits component-specific release cycles. Disadvantages: adds pointer-update discipline, two-step reviews, recursive clone requirements, detached-HEAD confusion, and difficult atomic cross-client changes. It would also require careful reconciliation of the current orphaned gitlinks and dirty legacy repository.

**Assessment:** Valid, but not the simplest operating model for this small, tightly coupled product.

### B. True monorepo — recommended

Advantages: one atomic commit can update API contracts, storefront, management, mobile, Compose, tests, and documentation; CI can evaluate the exact combined revision; deployment artifacts naturally live beside the code they deploy. It eliminates broken gitlink pointers and missing `.gitmodules` metadata.

Disadvantages: component histories must be imported carefully, repository size/access becomes shared, and CI needs path filters. Migration must preserve nested histories and all uncommitted work.

**Assessment:** Simplest maintainable strategy for Blue Panda's current team and cross-client release model.

### C. Separate application repositories plus a deployment repository

Advantages: strongest release/access separation and independent application lifecycles. Disadvantages: requires a mature image registry, version manifest, coordinated API compatibility policy, automated integration environment, and release orchestration across at least five repositories.

**Assessment:** A reasonable future model for independent teams, but unnecessary operational overhead today.

## Recommended migration procedure

This procedure requires separate approval and a maintenance window. Do not execute it while any nested worktree is dirty.

1. Inventory every root and nested branch, tag, remote, Git LFS object, ignored local file, and unpushed commit.
2. Commit or safely preserve all current work in its owning repository. The dirty `web-app/` migration is the immediate blocker. Back up every repository, including `.git` metadata, and verify the backup.
3. Decide whether legacy `web-app/` remains as an archived directory/history in the monorepo. It must not be deleted as part of repository conversion.
4. Create a temporary migration branch from a clean root clone. Import each component history with a history-preserving method such as `git subtree` or a reviewed `git filter-repo` workflow into its existing path.
5. Import `storefront/` and `management/` as ordinary monorepo directories after confirming their complete file/ignore state.
6. Remove mode-160000 entries and nested `.git` directories only inside the disposable migration clone, never in the current working copy. Confirm ordinary files are tracked at the intended paths.
7. Reconcile root ignores, ownership rules, CI path filters, dependency scanning, and release tags. Treat the backend, web, mobile, and deployment checks as a single required pipeline with path-aware optimization.
8. Compare file trees and histories against all source repositories. Run full builds/tests and Compose syntax checks. Confirm the development stack remains functional.
9. Review the migration branch, document old repository archival/read-only policy, and merge only after explicit owner approval. Keep old remotes intact until the monorepo has been verified and backed up.

## Immediate rules before migration

- Do not run `git rm --cached` on the gitlinks, delete nested `.git` directories, or create an improvised `.gitmodules` file.
- Do not stage the current root worktree wholesale; it contains unrelated user changes and untracked project documents.
- Commit changes in the repository that currently owns them. In particular, protect the dirty `web-app/` state.
- Do not rewrite or force-push any repository history.
- Deployment automation must not rely on the root gitlink commits until topology is repaired; they do not describe the checked-out component versions.
