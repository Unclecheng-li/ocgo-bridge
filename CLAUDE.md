# OpenCode Go Proxy

> Claude Code and other agents: **read `AGENTS.md` in this directory first.** It is the complete, self-contained operating manual for this package — install, configure, verify, troubleshoot, and client wiring.

Quick orientation:

- `proxy.py` — the proxy (Python 3.9+, standard library only, no `pip install`)
- `config.json` — the one file to edit (set your `oc_sk_...` key)
- `install.ps1` — run once on a new machine: `powershell -ExecutionPolicy Bypass -File install.ps1`
- `AGENTS.md` — full instructions, diagnostic table, and technical background
- `README.md` — human-facing version of the same

Base URL for clients: `http://127.0.0.1:8787/v1`

Two things that will waste your time if you skip them:

1. The proxy exists because OpenCode Go requires an `x-opencode-session` header that most clients cannot send. Do not attempt to bypass it by editing client config alone.
2. Never put non-ASCII characters in any `.vbs` file here. wscript reads them as GBK on Chinese Windows and will report a bogus compile error. ASCII + CRLF only.
