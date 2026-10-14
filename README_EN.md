<div align="center">

<h1>ocgo-bridge</h1>

<p><strong>A zero-dependency local proxy — use your OpenCode Go subscription from WorkBuddy / Claude Code / any OpenAI·Anthropic-compatible client</strong></p>

<p>Upstream demands <code>x-opencode-session</code>. Your client can't send it. This proxy sends it for you.</p>

<p>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Unclecheng-li/ocgo-bridge?color=blue" alt="License"></a>
  <a href="https://github.com/Unclecheng-li/ocgo-bridge/stargazers"><img src="https://img.shields.io/github/stars/Unclecheng-li/ocgo-bridge?style=social" alt="Stars"></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero Dependency">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/protocol-OpenAI%20%2B%20Anthropic-8A2BE2" alt="Protocols">
</p>

**中文版**: [`README.md`](README.md)

</div>

---

> ## 3-minute quick start
>
> ```powershell
> powershell -ExecutionPolicy Bypass -File install.ps1
> ```
>
> Set your key in `config.json` → double-click `start-proxy.vbs` → point your client's Base URL at `http://127.0.0.1:8787/v1`. Done.
>
> **No `pip install`** (standard library only), **no terminal window** (runs silently, survives reboots), **no code edits** (`config.json` decides everything).

---

## The problem it solves

Since **2026-09-05** the OpenCode Go gateway requires an `x-opencode-session` header on every request. Without it, **even a perfectly valid API key gets**:

```
400 MissingSessionID
```

The trouble is that most third-party clients **have nowhere to put a custom HTTP header**. The canonical example is WorkBuddy's `models.json`: it accepts a `url` and an `apiKey`, but **there is no headers field**. So no matter how you configure it, it cannot work.

This proxy runs on your machine. Your client talks to it, it adds the missing header, and forwards upstream.

```
┌───────────────────────────────────────────────────────────────┐
│                 Your clients (all talk to localhost)           │
│                                                               │
│    WorkBuddy     Claude Code     Cursor     Cherry Studio ...  │
│    ↑ no custom-header field in models.json                     │
└───────────────────────────────┬───────────────────────────────┘
                                │  POST /v1/chat/completions
                                │  POST /v1/messages
                                │  (client cannot send x-opencode-session)
                                ▼
                 ┌──────────────────────────────────┐
                 │   ocgo-bridge   127.0.0.1:8787    │
                 │                                  │
                 │   1. detect OpenAI / Anthropic   │
                 │   2. inject x-opencode-session   │
                 │   3. switch auth header (mutually│
                 │      exclusive per endpoint)     │
                 │   4. normalise the model id      │
                 └───────────────┬──────────────────┘
                                 │  with the complete header set
                                 ▼
                 ┌──────────────────────────────────┐
                 │  opencode.ai/inference/go/v1      │
                 │  (OpenCode Go subscription gateway)│
                 └──────────────────────────────────┘
```

## Why not something else

| Approach | What it costs you | Verdict |
|---|---|---|
| Point the client straight at OpenCode Go | The client must support custom headers | ❌ Most don't. `400 MissingSessionID` |
| Switch to a client with multi-upstream routing | Abandon the client you already use | ❌ Held hostage by your tools |
| Run the proxy manually in a terminal | A terminal window you **cannot close** | ❌ Close it and it's gone; reopen by hand after every reboot |
| Install it as a Windows service | Admin rights + a service framework | ❌ Far too heavy for a 200-line script |
| **ocgo-bridge** | Run `install.ps1` once | ✅ Zero deps, silent, autostart |

---

## Getting started

### Requirements

- **Python 3.9+** (`install.ps1` will find it, and tells you if it can't)
- **Windows 10 / 11** (the launchers are VBS; `proxy.py` itself is cross-platform)
- Network access to `opencode.ai`

> No `pip install` needed. The whole project uses only the Python standard library.

### Install

Download or clone the repo anywhere, then run this **from inside that folder**:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

It does four things, in order:

1. **Find Python** — tries `py` → `python` → per-user install dir → machine-wide install dir, and **actually executes each candidate**, not just checks the file exists (a corrupted interpreter file still exists; a mere `Test-Path` check will fool you). The winner is written to `python.txt`.
2. **Create config** — copies `config.example.json` to `config.json` if the latter is missing.
3. **Run the self-test** — spins up a local mock upstream and exercises all four protocol/streaming paths. **No network, no token spend.** A failure here means the package or the environment is broken, not your network or your account.
4. **Ask about autostart** — if you say yes, it installs the launcher into your Startup folder.

> Flags: `-Yes` enables autostart without prompting; `-NoAutostart` skips it entirely.

### Configure

Open `config.json` in Notepad:

```json
{
  "key": "oc_sk_your_key",
  "port": 8787
}
```

Get the key from the OpenCode Console. Valid keys start with `oc_sk_`.

> **⚠️ One more step, easy to miss**: in the OpenCode Console, open your workspace **Privacy settings** and set the region to **Global**.
> Skip this and the whole DeepSeek family returns `This Go model requires Global regions`. It is an **account-side setting — the proxy cannot work around it.**

### Run

| Action | How |
|---|---|
| Start (silent) | Double-click `start-proxy.vbs` |
| Stop | Double-click `stop-proxy.vbs` |
| Start (live log) | Double-click `start.bat` |
| Autostart at login | Answer Y in `install.ps1`, or run `install.ps1 -Yes` |

### Verify

```powershell
# Is the proxy alive? (local endpoint, no token spend)
curl http://127.0.0.1:8787/v1/models

# A real request
curl http://127.0.0.1:8787/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer oc_sk_your_key" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"say OK\"}],\"max_tokens\":16}'
```

A `200` with a normal completion means you're through. Note that DeepSeek V4.1 Flash is a reasoning model — the response also carries `reasoning_content` (OpenAI shape) or `type: thinking` blocks (Anthropic shape). **That is normal, not an error.**

---

## Wiring up clients

The Base URL is always `http://127.0.0.1:8787/v1`, and the API key is the one in your `config.json`.

| Client | Protocol | Base URL | Status |
|---|---|---|---|
| **WorkBuddy** | OpenAI | `http://127.0.0.1:8787/v1/chat/completions` | ✅ see below |
| **Claude Code** | Anthropic | `http://127.0.0.1:8787` | ✅ see below |
| Cursor / Cherry Studio / Continue, etc. | OpenAI | `http://127.0.0.1:8787/v1` | ✅ generic |
| CC Switch | Anthropic | `http://127.0.0.1:8787/v1` | ✅ no Local Routing needed |

### WorkBuddy

Edit `C:\Users\<you>\.workbuddy\models.json` and add an entry:

```json
{
  "id": "opencode-go-deepseek-v4.1-flash",
  "name": "DeepSeek V4.1 Flash (OpenCode Go)",
  "vendor": "Custom",
  "url": "http://127.0.0.1:8787/v1/chat/completions",
  "apiKey": "oc_sk_your_key",
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
- `id` may be an alias — the proxy maps `opencode-go-*` to the real upstream ID. The bare `deepseek-v4.1-flash` works too
- **WorkBuddy must be restarted** after editing; it reads this file at launch

### Claude Code

```powershell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8787"
$env:ANTHROPIC_API_KEY  = "oc_sk_your_key"
claude
```

The proxy detects `/v1/messages` and authenticates upstream with **`x-api-key`**. A `Bearer` header on this path is rejected (see "Dual protocol" below).

### Detailed version

Per-client walkthroughs, plus the specifics for CC Switch and Codex, live in **[`docs/CLIENTS.md`](docs/CLIENTS.md)**.

---

## Supported models

Model IDs **must be lowercase**. Passing `DeepSeek-V4.1-Flash` yields `Model is unavailable.` (the proxy normalises this defensively, but write it correctly in your client config anyway).

| Model ID | Upstream protocols | Status |
|---|---|---|
| `deepseek-v4.1-flash` | OpenAI + Anthropic | ✅ The main model this repo was verified against, reasoning output included |
| `deepseek-v4-flash` | OpenAI + Anthropic | Pass-through |
| `deepseek-v4-pro` | OpenAI + Anthropic | Pass-through |
| `mimo-v2.6-flash` | **OpenAI only** | ⚠️ On `/v1/messages` it returns `ModelProtocolUnsupported` |
| `glm-5.3-flash` / `kimi-k3` | Depends on your subscription | Pass-through |

> What you can actually use depends on your plan and workspace region. The proxy applies no whitelist — it only normalises the ID and forwards.

---

## Configuration reference

Every field in `config.json` is optional.

| Field | Default | Notes |
|---|---|---|
| `key` | empty | API key. If the client sends its own, that one wins; this is the fallback |
| `upstream` | `https://opencode.ai/inference/go/v1` | Upstream URL. **Do not change** — get it wrong and you silently land on the Zen pay-as-you-go channel |
| `user_agent` | `workbuddy-opencode-go/1.0` | UA seen by upstream |
| `model` | `deepseek-v4.1-flash` | Fallback when the client omits `model` |
| `host` | `127.0.0.1` | Listen address. **Keep it local** |
| `port` | `8787` | Listen port |
| `http_proxy` | empty | Outbound proxy. Empty = direct, and **ignores** the `HTTP_PROXY` environment variable |

**Precedence: environment variable > `config.json` > built-in default.**

To override temporarily without editing the file:

```powershell
$env:OPENCODE_GO_PORT = "9000"
$env:OPENCODE_GO_KEY  = "oc_sk_xxx"
python proxy.py
```

Supported variables: `OPENCODE_GO_KEY`, `OPENCODE_GO_UPSTREAM`, `OPENCODE_GO_UA`, `OPENCODE_GO_MODEL`, `OPENCODE_GO_HOST`, `OPENCODE_GO_PORT`, `OPENCODE_GO_HTTP_PROXY`, `OPENCODE_GO_LOG`.

> `OPENCODE_GO_LOG` overrides the log path, which defaults to `proxy.log` next to `proxy.py`. The self-test uses it to send test traffic to a temp file instead of polluting the production log.

---

## Command line

You don't need the launchers:

```bash
python proxy.py                  # read config.json
python proxy.py --port 9000      # override the port
python proxy.py --host 0.0.0.0   # override the listen address (not recommended)
python tools/selftest.py         # offline self-test; exit code 0 = all passed
```

---

## Project layout

```
ocgo-bridge/
├── proxy.py                  # The proxy. The only essential file (stdlib only)
├── config.example.json       # Config template
├── config.json               # Your config (.gitignore'd, never committed)
├── install.ps1               # Install + self-test + optional autostart
├── start-proxy.vbs           # Double-click to start (with popup feedback)
├── stop-proxy.vbs            # Double-click to stop
├── start.bat                 # Foreground run, live log
├── startup-template.vbs      # Autostart template; install.ps1 copies it to Startup
├── python.txt                # Interpreter path written at install time (.gitignore'd)
├── proxy.log                 # Runtime log
├── AGENTS.md                 # Full operating manual written for AI agents
├── CLAUDE.md                 # Claude Code entry point, points at AGENTS.md
├── README.md / README_EN.md  # Chinese / this file
├── LICENSE                   # MIT
├── docs/
│   ├── CLIENTS.md            # Per-client integration details
│   └── TROUBLESHOOTING.md    # Troubleshooting manual
└── tools/
    └── selftest.py           # Offline self-test (mock upstream, no network)
```

---

## How it works

For people reading or modifying the code.

### Dual-protocol gateway with mutually exclusive auth

The OpenCode Go gateway exposes **both** an OpenAI and an Anthropic surface, and the two authenticate **incompatibly** — mixing them up is an immediate 401:

| Client path | Upstream path | Accepted auth | Wrong header result |
|---|---|---|---|
| `POST /v1/chat/completions` | `/chat/completions` | `Authorization: Bearer` | `x-api-key` → `Go requires a credential` |
| `POST /v1/messages` | `/messages` | `x-api-key` | `Bearer` → `Go requires a credential` |

The proxy routes by path (or by the presence of an `anthropic-version` header) and rewrites the auth header to whichever one is correct.

### Where the session ID comes from

- **OpenAI path**: when the client sends no `x-opencode-session`, derive a uuid5 from **the first message of the conversation**
- **Anthropic path**: prefer Claude's own session identifier; fall back to the same derivation

The crucial detail is that **only the first message seeds it**. Include the message count and every turn produces a different session ID — which means upstream prompt caching never hits.

### Two implementation traps (both handled)

**A non-streaming response must never be pre-read.** Calling `read()` drains an SSE stream; forwarding afterwards yields an empty body — an HTTP 200 with zero content. Streaming and whole-body responses therefore take two strictly separate paths.

**A streaming response needs an explicit terminator.** Under HTTP/1.1 `BaseHTTPRequestHandler` does no automatic chunked encoding, and SSE has no `Content-Length`; without handling, the client hangs forever. The proxy uses `Connection: close` and lets EOF signal completion.

### Port exclusivity

On Windows `SO_REUSEADDR` means the **opposite** of its Linux meaning — it **permits** a second process to bind an already-listening port. Python's `HTTPServer` sets it by default, so repeated double-clicks stack up multiple listeners with requests spread randomly across them.

The proxy switches to `SO_EXCLUSIVEADDRUSE` instead: a second launch fails immediately with `WinError 10048` and `exit 2`.

### Outbound proxy

`urllib` honours `HTTP_PROXY` / `HTTPS_PROXY` by default. If you have something like Clash running locally, it can hijack traffic to `opencode.ai` and surface a 502 that **looks like a code bug**. The proxy **ignores** those variables and connects directly by default; if you genuinely need a proxy, set `http_proxy` in `config.json` explicitly.

### VBS encoding requirements (read before editing the launchers)

Every `.vbs` file is **pure ASCII + CRLF**. This is mandatory.

wscript reads `.vbs` as **ANSI/GBK** on Chinese Windows. A single non-ASCII byte — **even inside a comment** — gets decoded as GBK. GBK is double-byte, so a mangled trailing byte can **swallow the line's newline**, merging two lines and shifting reported line numbers, producing a baffling:

```
Microsoft VBScript 编译器错误 / 行 18 / 字符 1 / 缺少语句 / 800A0400
```

**So: never write Chinese into these `.vbs` files, not even in comments.** The interpreter and the port are both read at runtime from `python.txt` / `config.json` — nothing in the scripts needs Chinese.

---

## Troubleshooting

**Check `proxy.log` first.** Nine out of ten issues are in there.

| Symptom | Cause & fix |
|---|---|
| `400 MissingSessionID` | The request bypassed the proxy and hit upstream directly. Check that the Base URL is `127.0.0.1:8787` |
| `401 Go requires a credential` | Auth header mismatch. `/v1/messages` needs `x-api-key`, `/v1/chat/completions` needs Bearer. The proxy handles this — seeing it means the request didn't go through the proxy |
| `Model is unavailable.` | Model ID case mismatch; upstream only accepts lowercase |
| `This Go model requires Global regions` | Set your workspace region to **Global** in the Console. Account-side setting, unreachable from the proxy |
| `Insufficient account funds` | You're on the wrong gateway — the Zen pay-as-you-go channel. `upstream` must be `.../inference/go/v1` |
| `502 upstream unreachable: ...` | **The proxy itself** reporting — this machine can't reach `opencode.ai`. Check network/firewall/DNS |
| `502 upstream connect failed: ...` | **Not the proxy's wording** — another local proxy (Clash, a sandbox, etc.) hijacked the connection. Set `http_proxy` or turn it off |
| `bind failed ... [WinError 10048]` | Port in use. Double-click `stop-proxy.vbs`, or change `port` |
| Double-clicking the .vbs does nothing | Run `start.bat` to see the error. Usually a stale path in `python.txt` |
| Changed `config.json`, no effect | Config is read once at startup. Restart the proxy |
| VBS reports `800A0400 / 缺少语句` | That `.vbs` has non-ASCII bytes or bare LF. Restore it to pure ASCII + CRLF |

> The two 502s look alike but have **different owners**: `upstream unreachable` is this proxy speaking, `upstream connect failed` comes from a different proxy in the chain. Telling them apart saves a lot of time.

The full manual — including the complete diagnostic table from `AGENTS.md` — is in **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)**.

---

## FAQ

**Q: Does this bypass OpenCode's restrictions?**

No. You're using **your own paid subscription**; the proxy only supplies a required header that certain clients are architecturally unable to send. It doesn't alter quotas, share accounts, or spoof identity — it's purely a protocol adapter.

**Q: Where is the key stored? Is that safe?**

In plaintext in `config.json`, on your machine only. The proxy listens on `127.0.0.1` by default, so nothing external can reach it. **Never commit `config.json`** (`.gitignore` already excludes it), and don't hand the folder to anyone. If it leaks, revoke and reissue in the Console.

**Q: Can I run this on macOS / Linux?**

`proxy.py` is cross-platform — `python3 proxy.py` just works. But the `.vbs` files and `install.ps1` are Windows-only, and autostart needs your own systemd / launchd setup.

**Q: Will repeated launches pile up processes?**

No. The port uses exclusive binding, so the second instance exits immediately with code 2.

**Q: Why does autostart need `proxy_dir.txt`?**

Because once the launcher is copied into the Startup folder, it **cannot infer where the proxy is installed** from its own location. So the installer writes the real path there. **If you move the folder, re-run `install.ps1`** — otherwise autostart fails silently.

---

## Security

- `config.json` holds a **plaintext API key**. Don't commit it, don't share it.
- Keep `host` at `127.0.0.1`. Setting `0.0.0.0` exposes your key to the whole LAN.
- This project **collects and reports nothing**. All traffic stays between your machine and `opencode.ai`.

---

## License

[MIT](LICENSE)

---

**If this helped you, a Star ⭐ is appreciated.**
