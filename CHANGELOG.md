# Changelog

## v1.0.5 - 2026-04-08

- pruned stale git metadata, removed the tracked Codex handoff document from the public repo surface, and ignore future `HANDOFF*.md` notes by default
- tightened contributor guidance and packaging checks so host-specific/private handoff details stay out of release docs
- hardened stop-hook continuation prompts so archive-ready follow-up work still re-anchors the standing subagent pool and honors explicit hard-stop reasons

## v1.0.4 - 2026-04-02

- made the runtime operationally subagent-first with a standing-pool planner, persisted `subagent_pool` metadata, and a continuation policy shared across setup, state, launch, and status artifacts
- expanded hook, helper, and contract coverage so resumed runs re-anchor the standing pool and continue by default after launch unless a stop condition or real blocker appears
- aligned the packaged plugin payload, launcher metadata, and contributor documentation with the subagent-first orchestration model and release workflow

## v1.0.3 - 2026-04-02

- added managed SessionStart/Stop hook support, repo-local hook context tracking, and mirrored plugin hook files for resumed or unattended autoresearch runs
- added foreground completion via `scripts/autoresearch_complete_run.py` plus automatic self-improvement and memory carry-forward artifacts for the next run
- added `scripts/check_plugin_distribution.py`, contributor/install docs, and release-time validation coverage for the packaged plugin payload
- refreshed README release copy and plugin marketplace interface text to reflect the current runtime, packaging, and release workflow

## v1.0.2 - 2026-04-02

- fixed plugin distribution coverage to validate the shipped GitHub marketplace source and root-to-plugin payload parity
- corrected background-control behavior so `launch` returns the active running state, foreground runs reject background-only mutations, `resume` clears `needs_human`, and fresh-start launches archive prior manifests deterministically
- hardened helper-layer validation for `verify_status` and `guard_status` during iteration recording
- aligned README and plugin metadata with the `Maleick/codex-autoresearch` release source and documented the root-first, mirror-second release workflow
