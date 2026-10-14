# AGENTS.md — OpenCode Go Proxy

**You are an AI agent. This file tells you everything needed to install, configure, verify, and use this package on a Windows machine.** Read it fully before acting. It is self-contained: you do not need the internet, and this package has no external dependencies.

---

## 0. What this is, in one paragraph

OpenCode Go is a subscription gateway (`https://opencode.ai/inference/go/v1`) that serves models like `deepseek-v4.1-flash`. Since 2026-09-05 it **requires an `x-opencode-session` HTTP header on every request**; without it, the gateway returns `400 MissingSessionID` even with a perfectly valid API key. Most third-party clients — notably **WorkBuddy's `models.json`, which has no field for custom headers** — cannot send that header. This package is a small local HTTP proxy that runs on `127.0.0.1`, receives requests from such clients, injects the required session header, and forwards them upstream. It uses only the Python standard library.

**Your job when handed this package:** get the proxy running on this machine, point the target client at it, and prove it works.

---

## 1. Absolute rules — read these first

1. **Never write non-ASCII bytes into any `.vbs` file in this package.** wscript reads `.vbs` as ANSI/GBK on Chinese Windows. A Chinese comment corrupts the file and produces a misleading `800A0400 / 缺少语句 / expected statement` compile error with a wrong line number. English only, ASCII only. Keep CRLF line endings.
2. **Never change `config.json` → `upstream`** away from `https://opencode.ai/inference/go/v1`. Other paths (`/zen/v1`, `/inference/openai/v1`) silently route to the **Zen pay-as-you-go** billing channel and return `Insufficient account funds` instead of using the Go subscription.
3. **Never bind the proxy to `0.0.0.0`.** The API key is stored in plaintext; listening on all interfaces exposes it to the LAN. Default `127.0.0.1` is correct.
4. **Model IDs are lowercase.** The gateway rejects `DeepSeek-V4.1-Flash` with `Model is unavailable.` The proxy normalizes this, but do not introduce uppercase IDs in client config.
5. **Do not run `pip install`.** The proxy depends only on the standard library. If something seems to need a package, that is a misdiagnosis.
6. **`SO_REUSEADDR` on Windows is not port exclusivity** — it *permits* a second process to bind an already-listening port. This proxy already sets `SO_EXCLUSIVEADDRUSE`; do not "simplify" that code.

---

## 2. Verify the environment

Run these checks before anything else.

**Step 2.1 — is Python available?**

```powershell
python -V
py -V
```

You need **Python 3.9 or newer**. `py` (the launcher) is preferred when present since it is version-agnostic. If neither works, tell the user to install Python 3.9+ from https://www.python.org/downloads/windows/ and to tick **"Add python.exe to PATH"** during setup. Do not attempt to install Python yourself unless the user asks.

**Step 2.2 — is the proxy already running?**

```powershell
Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
```

If this returns a result, an instance is already up. If you need to restart it, see §5.

**Step 2.3 — locate the package root.**

The folder containing `proxy.py`. All scripts resolve paths relative to themselves, so the folder can live anywhere. If unclear:

```powershell
Get-ChildItem -Recurse -Filter proxy.py | Select-Object -ExpandProperty FullName
```

---

## 3. Install

**Step 3.1 — run the installer.** This is the intended path; it does discovery, config bootstrap, self-test, and optional autostart in one pass.

```powershell
cd <package-root>
powershell -ExecutionPolicy Bypass -File install.ps1
```

Useful flags:

| Flag | Effect |
|---|---|
| `-Yes` | enable autostart without prompting |
| `-NoAutostart` | never register autostart |

`-ExecutionPolicy Bypass` is required when the machine blocks unsigned scripts. If the user reports "running scripts is disabled on this system", that flag is the fix — do not tell them to change the machine-wide policy.

**Step 3.2 — confirm what the installer produced.** You should now have:

- `python.txt` — absolute path to the chosen interpreter, single line, no trailing newline
- `config.json` — copied from `config.example.json` on first run, otherwise left untouched
- A self-test result ending in `RESULT: PASS`

The installer's self-test spins up a **local mock upstream** and exercises all four protocol/streaming combinations. It **does not need the internet**. If it fails, the problem is in the package or the environment, not the network or the API key.

**Step 3.3 — set the API key.** If `config.json` still contains `oc_sk_REPLACE_WITH_YOUR_KEY`, the user must supply a real key. Edit the file:

```json
{
  "key": "oc_sk_...",
  "upstream": "https://opencode.ai/inference/go/v1",
  "user_agent": "workbuddy-opencode-go/1.0",
  "model": "deepseek-v4.1-flash",
  "host": "127.0.0.1",
  "port": 8787,
  "http_proxy": ""
}
```

Valid keys start with `oc_sk_`. Get them from the OpenCode Console.

**Step 3.4 — confirm the account region.** Tell the user to open the OpenCode Console → workspace **Privacy settings** → set region to **Global**. Without this, the entire DeepSeek family returns:

```
This Go model requires Global regions. Select Global in your workspace's Privacy settings.
```

This is an account-side setting. **No change to this package can work around it.** Do not try.

---

## 4. Start and verify

**Step 4.1 — start it.** Either works:

```powershell
# silent, detached (normal use)
wscript start-proxy.vbs

# foreground with live output (debugging)
python proxy.py
```

Do not use `cscript`; it is commonly blocked by endpoint security as a LOLBin.

**Step 4.2 — confirm the listener.**

```powershell
Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
```

Expect exactly **one** result. Two or more means duplicate instances — see §5.

**Step 4.3 — read the startup log.** `proxy.log` in the package root. A healthy start looks like:

```
[hh:mm:ss] config loaded from <package-root>\config.json
[hh:mm:ss] upstream = https://opencode.ai/inference/go/v1
[hh:mm:ss] env HTTP(S)_PROXY ignored; connecting upstream directly
[hh:mm:ss] fallback key loaded (NN chars) - clients may also send their own
[hh:mm:ss] OpenCode Go proxy listening on http://127.0.0.1:8787
```

**Step 4.4 — probe without spending tokens.**

```powershell
curl http://127.0.0.1:8787/v1/models
```

Any JSON response means the proxy is alive. This endpoint is served locally and never reaches upstream.

**Step 4.5 — make a real call.**

```powershell
curl http://127.0.0.1:8787/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer oc_sk_YOUR_KEY" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"say OK\"}],\"max_tokens\":16}'
```

A `200` with a completion body is end-to-end success. Note `deepseek-v4.1-flash` is a reasoning model: the response will also carry `reasoning_content` (OpenAI shape) or `type: thinking` blocks (Anthropic shape). That is expected, not an error.

---

## 5. Operating it

**Stop:**

```powershell
wscript stop-proxy.vbs
```

Or by port:

```powershell
Get-NetTCPConnection -LocalPort 8787 -State Listen |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**Restart** (needed after any `config.json` edit — config is read once at startup):

```powershell
wscript stop-proxy.vbs
Start-Sleep -Seconds 2
wscript start-proxy.vbs
```

**Autostart.** `install.ps1` copies `startup-template.vbs` into the Startup folder as `OpenCodeGoProxy.vbs`, and writes the package's real location to `proxy_dir.txt` **in the Startup folder**. That second file matters: the Startup copy sits next to nothing, so it cannot infer where `proxy.py` lives from its own path. If you ever move the package, re-run `install.ps1` — otherwise autostart breaks silently.

Startup folder path: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` (or `shell:startup` in the Run box).

To disable autostart, delete both `OpenCodeGoProxy.vbs` and `proxy_dir.txt` from that folder.

---

## 6. Wiring up clients

The proxy speaks **both** OpenAI and Anthropic protocols, so most clients work. Base URL is always:

```
http://127.0.0.1:8787/v1
```

API key is the same `oc_sk_...` value from `config.json`.

### 6.1 WorkBuddy

Edit `C:\Users\<user>\.workbuddy\models.json` and add:

```json
{
  "id": "opencode-go-deepseek-v4.1-flash",
  "name": "DeepSeek V4.1 Flash (OpenCode Go)",
  "vendor": "Custom",
  "url": "http://127.0.0.1:8787/v1/chat/completions",
  "apiKey": "oc_sk_YOUR_KEY",
  "supportsToolCall": true,
  "supportsImages": true,
  "supportsReasoning": true,
  "maxInputTokens": 1000000,
  "maxOutputTokens": 384000,
  "useCustomProtocol": false,
  "reasoning": {
    "supportedEfforts": ["max", "medium", "high", "low", "xhigh"]
  }
}
```

Three things that must be right:

- `url` **must end with `/v1/chat/completions`**
- `id` may be an alias — the proxy maps `opencode-go-*` names to real upstream IDs. Setting `id` to the bare `deepseek-v4.1-flash` also works.
- **WorkBuddy must be restarted** after editing; it reads this file at launch.

WorkBuddy has **no field for custom headers**. That is precisely why this proxy exists — do not try to solve the `MissingSessionID` error by editing `models.json` alone.

### 6.2 Claude Code (Anthropic protocol)

```powershell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8787"
$env:ANTHROPIC_API_KEY  = "oc_sk_YOUR_KEY"
claude
```

The proxy detects `/v1/messages` and authenticates upstream with **`x-api-key`**. On this path a `Bearer` header is rejected with `Go requires a credential` — the proxy handles the switch automatically.

### 6.3 Any other OpenAI-compatible client

| Field | Value |
|---|---|
| Base URL / API Host | `http://127.0.0.1:8787/v1` |
| API Key | `oc_sk_...` |
| Model | `deepseek-v4.1-flash` |

---

## 7. Diagnostic table

Match the `proxy.log` line or the client error to a cause. These are specific and unambiguous.

| Observed | Meaning | Action |
|---|---|---|
| `400 MissingSessionID` | Request bypassed the proxy and hit upstream directly | Fix the client's Base URL to `127.0.0.1:8787` |
| `401 Go requires a credential` | Auth header wrong for that endpoint. `/v1/messages` needs `x-api-key`; `/v1/chat/completions` needs `Bearer` | If it appears, the request did not go through the proxy — fix the Base URL |
| `Model is unavailable.` | Model ID case mismatch | Use lowercase `deepseek-v4.1-flash` |
| `This Go model requires Global regions` | Account region is not Global | User must change it in OpenCode Console → Privacy settings |
| `Insufficient account funds` | Routed to the Zen pay-as-you-go channel | `upstream` must be `https://opencode.ai/inference/go/v1` |
| `502 upstream unreachable: ...` | **Proxy's own** error — it could not reach upstream | Network/firewall/DNS issue on this machine |
| `502 upstream connect failed: ... (os error 10061)` | **Not** the proxy's phrasing — a third-party local proxy (Clash, sandbox, etc.) intercepted the connection | Set `http_proxy` in `config.json` to that proxy, or disable it |
| `bind failed ... [WinError 10048]` | Port already in use | Another instance is running; use `stop-proxy.vbs`, or change `port` |
| `no config.json; using defaults` | Config file absent | Copy `config.example.json` → `config.json` and set `key` |
| `no fallback key; clients must send their own` | No key in config | Set `key`, or ensure the client sends its own |
| VBScript `800A0400 / 缺少语句` | The `.vbs` has non-ASCII bytes or bare LF | Restore from the pristine copy; ASCII + CRLF only |
| Double-click does nothing | `python.txt` path stale, or proxy already running | Run `start.bat` to see the error; check `python.txt` |
| Changed `config.json`, no effect | Config is read only at startup | Restart the proxy |

Two 502 variants look alike but have different owners. `upstream unreachable` is this proxy speaking. `upstream connect failed` comes from a different local proxy in the chain. Distinguishing them saves a lot of time.

---

## 8. Configuration reference

`config.json` — all fields optional; env vars override it; built-in defaults apply last.

| Field | Env var | Default | Notes |
|---|---|---|---|
| `key` | `OPENCODE_GO_KEY` | `""` | Fallback key, used only when the client sends none |
| `upstream` | `OPENCODE_GO_UPSTREAM` | `https://opencode.ai/inference/go/v1` | **Do not change** |
| `user_agent` | `OPENCODE_GO_UA` | `workbuddy-opencode-go/1.0` | UA seen upstream |
| `model` | `OPENCODE_GO_MODEL` | `deepseek-v4.1-flash` | Fallback when the client omits `model` |
| `host` | `OPENCODE_GO_HOST` | `127.0.0.1` | **Do not use `0.0.0.0`** |
| `port` | `OPENCODE_GO_PORT` | `8787` | Used by all VBS scripts and the installer |
| `http_proxy` | `OPENCODE_GO_HTTP_PROXY` | `""` | Empty = direct connection, and **ignores** the `HTTP_PROXY`/`HTTPS_PROXY` environment variables |

The `http_proxy` default is deliberate. `urllib` normally honors `HTTP_PROXY`/`HTTPS_PROXY`; if a local proxy like Clash is configured there, it may hijack traffic to `opencode.ai` and produce the misleading `upstream connect failed` 502. This proxy ignores those variables unless you explicitly opt in.

**Precedence: environment variable > `config.json` > built-in default.**

---

## 9. Package contents

| File | Role | Editable? |
|---|---|---|
| `proxy.py` | The proxy. Standard library only. **Only essential file.** | Only to fix bugs |
| `config.json` | Per-machine settings | **Yes — the one to edit** |
| `config.example.json` | Template for the above | No |
| `install.ps1` | Discovery + config bootstrap + self-test + autostart | No |
| `start-proxy.vbs` | Start with popup feedback | No |
| `stop-proxy.vbs` | Stop | No |
| `startup-template.vbs` | Autostart template; `install.ps1` copies it to the Startup folder | No |
| `start.bat` | Foreground launcher with live log | No |
| `tools/selftest.py` | Offline self-test: mock upstream on 8899, proxy on 8790 | No |
| `python.txt` | Interpreter path, written by `install.ps1` | Regenerated |
| `proxy.log` | Runtime log — check here first | Auto |
| `README.md` / `README_EN.md` | Human-facing documentation (Chinese / English) | No |
| `docs/CLIENTS.md` | Per-client wiring details | No |
| `docs/TROUBLESHOOTING.md` | Full troubleshooting manual | No |
| `AGENTS.md` | This file — the agent-facing manual | No |
| `CLAUDE.md` | Claude Code entry point; points here | No |
| `LICENSE` | MIT | No |

Files **not** in this table but present after a run: `proxy_dir.txt`, written into the Startup folder by the installer (§5).

---

## 10. Running the self-test

The installer runs it automatically. To re-run it standalone:

```powershell
python tools/selftest.py
```

It starts a mock upstream on port 8899, runs the proxy on 8790, sends four protocol/streaming combinations plus fallback cases, and asserts:

1. Every upstream request carries `x-opencode-session`
2. `/messages` uses `x-api-key` and never `Bearer`
3. `/chat/completions` uses `Bearer` and never `x-api-key`
4. Model IDs are all normalized to valid lowercase IDs
5. Multi-turn conversations keep a stable session ID

It also requires all four protocol/streaming probes to return HTTP 200. Exit code `0` = `RESULT: PASS`.

It needs **no internet**. Use it to separate "package broken" from "network or account broken".

---

## 11. Technical background

Read this if you need to modify behavior.

### Why a proxy is unavoidable

OpenCode Go enforces `x-opencode-session` since 2026-09-05; absence yields `400 MissingSessionID` regardless of key validity. WorkBuddy's `models.json` schema has no headers field. A local intermediary is therefore the only viable integration path.

### Dual-protocol gateway with mutually exclusive auth

| Client path | Upstream path | Accepted auth | Wrong auth result |
|---|---|---|---|
| `POST /v1/chat/completions` | `/chat/completions` | `Authorization: Bearer` | `x-api-key` → `Go requires a credential` |
| `POST /v1/messages` | `/messages` | `x-api-key` | `Bearer` → `Go requires a credential` |

The proxy routes by path, or by presence of an `anthropic-version` header.

Not every model supports both protocols. `mimo-v2.6-flash` on `/messages` returns `ModelProtocolUnsupported`. The DeepSeek family works on both.

### Session ID derivation

- **OpenAI path**: if the client sends no `x-opencode-session`, derive a uuid5 seeded by **the first message only**.
- **Anthropic path**: prefer the client's own session identifier, fall back to the same derivation.

Seeding from the first message alone is essential. Including the message count makes the session ID change on every turn, which defeats upstream prompt caching.

### Two implementation traps

**Never pre-read a non-streaming response.** Calling `resp.read()` drains an SSE stream; forwarding afterwards yields an empty body — an HTTP 200 with zero content. Streaming and whole-body paths are therefore kept strictly separate.

**Streaming needs an explicit terminator.** `BaseHTTPRequestHandler` does no automatic chunked encoding under HTTP/1.1, and SSE has no `Content-Length`. Without handling, the client waits forever. The proxy sends `Connection: close` and lets EOF signal completion.

### Port exclusivity

On Windows `SO_REUSEADDR` means *permit another process to bind the same port* — the opposite of Linux semantics. Python's `HTTPServer` sets it by default, so repeated launches silently stack up multiple listeners with requests spread across them. The proxy sets `SO_EXCLUSIVEADDRUSE` instead, so a second launch fails fast with `WinError 10048` and `exit 2`.

---

## 12. Uninstall

1. Delete `OpenCodeGoProxy.vbs` and `proxy_dir.txt` from the Startup folder.
2. Stop the process (`stop-proxy.vbs`).
3. Delete the package folder.

No registry entries, no services, no writes outside the package folder and the Startup folder.

---

## 13. Platform notes

- `proxy.py` is **cross-platform** — it runs on macOS and Linux unchanged.
- The `.vbs` launchers, `start.bat`, and `install.ps1` are **Windows-only**.
- On macOS/Linux: run `python3 proxy.py`, and use `systemd` or `launchd` if autostart is needed.

---

## 14. Security

- `config.json` holds the **API key in plaintext**. Do not commit it, do not share the folder.
- Keep `host` at `127.0.0.1`. Binding `0.0.0.0` exposes the key to the local network.
- If a key is ever exposed, revoke and reissue it in the OpenCode Console.
