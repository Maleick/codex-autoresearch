# Local Fallback Plugin Bootstrap

Use this path when Codex cannot refresh or install the GitHub-backed plugin directly on a machine and the local marketplace has to point at a machine-local plugin directory instead.

Typical symptoms:

- Codex does not show the plugin marketplace UI on that machine
- Codex logs show remote plugin sync/auth failures
- a local Codex build rejects non-`local` sources in `~/.agents/plugins/marketplace.json`

This repository includes a helper that recreates the machine-local pieces for `codex-autoresearch` from the repo source of truth:

```bash
python3 scripts/bootstrap_local_plugin.py
```

By default the script:

- syncs the packaged plugin payload from the repo root into `plugins/codex-autoresearch`
- copies the packaged bundle into `~/plugins/codex-autoresearch`
- merges a `local` source entry for `./plugins/codex-autoresearch` into `~/.agents/plugins/marketplace.json`
- preserves unrelated plugin entries that already exist in the local fallback marketplace

The command also prints the enabled-plugin reference that matches the resulting marketplace identifier. With the default machine-local marketplace name, that reference is:

```text
codex-autoresearch@local-plugins
```

Useful variants:

```bash
python3 scripts/bootstrap_local_plugin.py --skip-sync
python3 scripts/bootstrap_local_plugin.py --marketplace-name team-marketplace
python3 scripts/bootstrap_local_plugin.py --marketplace ~/.agents/plugins/marketplace.json --install-root ~/plugins
```

Notes:

- The repository marketplace entry stays GitHub-backed. The fallback bootstrap intentionally rewrites the machine-local marketplace entry to a `local` source because some Codex builds only accept local sources there.
- The script does not rewrite `~/.codex/config.toml`; keep the enabled-plugin entry explicit.
- Reload Codex after updating the local install or marketplace manifest.
- This workflow is machine-local state. Do not commit those generated local files back into the repository.
