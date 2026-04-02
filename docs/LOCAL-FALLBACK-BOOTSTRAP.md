# Local Fallback Plugin Bootstrap

Use this path when Codex cannot refresh GitHub-backed plugins on your machine and local plugin discovery has to rely on a fallback marketplace instead of remote sync alone.

Typical symptom:

- Codex log entries show plugin-sync failures such as HTTP 403 responses

This repository now includes a helper that recreates the machine-local pieces for `codex-autoresearch` from the repo source of truth:

```bash
python3 scripts/bootstrap_local_plugin.py
```

By default the script:

- syncs the packaged plugin payload from the repo root into `plugins/codex-autoresearch`
- copies the packaged bundle into `~/plugins/codex-autoresearch`
- merges the `codex-autoresearch` entry into `~/.agents/plugins/marketplace.json`
- preserves unrelated plugin entries that already exist in the local fallback marketplace

The command also prints the enabled-plugin reference that matches the resulting marketplace identifier. When you are using the common local fallback name, that reference is:

```text
codex-autoresearch@openai-curated
```

Useful variants:

```bash
python3 scripts/bootstrap_local_plugin.py --skip-sync
python3 scripts/bootstrap_local_plugin.py --marketplace-name openai-curated
python3 scripts/bootstrap_local_plugin.py --marketplace ~/.agents/plugins/marketplace.json --install-root ~/plugins
```

Notes:

- The script does not rewrite `~/.codex/config.toml`; keep that change explicit.
- Reload Codex after updating the local install or marketplace manifest.
- This workflow is machine-local state. Do not copy those generated local files into another repository by accident.
