# Changelog

## v1.0.2 - 2026-04-02

- fixed plugin distribution coverage to validate the shipped GitHub marketplace source and root-to-plugin payload parity
- corrected background-control behavior so `launch` returns the active running state, foreground runs reject background-only mutations, `resume` clears `needs_human`, and fresh-start launches archive prior manifests deterministically
- hardened helper-layer validation for `verify_status` and `guard_status` during iteration recording
- aligned README and plugin metadata with the `Maleick/codex-autoresearch` release source and documented the root-first, mirror-second release workflow
