<div align="center">

<h1>ocgo-bridge</h1>

<p><strong>零依赖本地代理 — 让 WorkBuddy / Claude Code / 任意 OpenAI·Anthropic 兼容客户端用上 OpenCode Go 订阅</strong></p>

<p>上游要 <code>x-opencode-session</code>，客户端不会发。这个代理替你发。</p>

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

**English version**: [`README_EN.md`](README_EN.md)

</div>

---

> ## 3 分钟快速上手
>
> ```powershell
> powershell -ExecutionPolicy Bypass -File install.ps1
> ```
>
> 装完改一个 `config.json` 填上 Key → 双击 `start-proxy.vbs` → 把客户端的 Base URL 指到 `http://127.0.0.1:8787/v1`。完事。
>
> **不用 pip 装任何东西**（纯标准库），**不用开终端窗口**（静默常驻 + 开机自启），**不用改一行代码**（`config.json` 说了算）。

---

## 它解决什么问题

OpenCode Go 订阅网关从 **2026-09-05** 起强制要求每个请求带 `x-opencode-session` 头。缺了它，**你的 API Key 再对也一律返回**：

```
400 MissingSessionID
```

问题在于 —— 大多数第三方客户端**根本没有填写自定义 HTTP 请求头的地方**。典型例子就是 WorkBuddy 的 `models.json`：它能配 `url`、能配 `apiKey`，但**没有 headers 字段**。于是无论你怎么配，都调不通。

这个代理就跑在你本机，客户端连它，它补上那个头，再转发给 OpenCode Go。

```
┌───────────────────────────────────────────────────────────────┐
│                    你的客户端（全部走本机）                       │
│                                                               │
│    WorkBuddy     Claude Code     Cursor     Cherry Studio ...  │
│    ↑ models.json 没有自定义 header 字段                          │
└───────────────────────────────┬───────────────────────────────┘
                                │  POST /v1/chat/completions
                                │  POST /v1/messages
                                │  （客户端发不出 x-opencode-session）
                                ▼
                 ┌──────────────────────────────────┐
                 │   ocgo-bridge   127.0.0.1:8787    │
                 │                                  │
                 │   1. 识别 OpenAI / Anthropic 协议  │
                 │   2. 补 x-opencode-session        │
                 │   3. 按端点切换鉴权头（互斥）        │
                 │   4. 归一化 model id              │
                 └───────────────┬──────────────────┘
                                 │  带着完整请求头
                                 ▼
                 ┌──────────────────────────────────┐
                 │  opencode.ai/inference/go/v1      │
                 │  （OpenCode Go 订阅网关）           │
                 └──────────────────────────────────┘
```

## 为什么不直接用别的办法

| 方案 | 你需要付出什么 | 结果 |
|---|---|---|
| 客户端直连 OpenCode Go | 客户端得支持自定义请求头 | ❌ 绝大多数不支持，`400 MissingSessionID` |
| 换个支持多上游路由的客户端 | 放弃现在用的客户端 | ❌ 被工具绑架 |
| 手动开个终端跑代理 | 一个**不能关**的终端窗口 | ❌ 关了就没，重启要手动重开 |
| 装成 Windows 服务 | 管理员权限 + 服务框架 | ❌ 为了 200 行脚本太重 |
| **ocgo-bridge** | 跑一次 `install.ps1` | ✅ 零依赖、静默常驻、开机自启 |

---

## 快速开始

### 环境要求

- **Python 3.9+**（`install.ps1` 会自动找，找不到会告诉你）
- **Windows 10 / 11**（启动脚本用 VBS；`proxy.py` 本身是跨平台的）
- 能访问 `opencode.ai`

> 不需要 pip 装任何包。整个项目只用到 Python 标准库。

### 安装

把仓库下载/克隆到任意目录，然后在**该目录里**跑：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

它按顺序做四件事：

1. **找 Python** —— 依次试 `py` → `python` → 用户级安装目录 → 全机安装目录，并且**实际运行验证**，不只是看文件存在（损坏的解释器文件仍然存在，只看存在会踩坑）。找到后写进 `python.txt`。
2. **建配置** —— 没有 `config.json` 就从 `config.example.json` 复制一份。
3. **跑自检** —— 起一个本地假上游，把四条协议链路全打一遍。**不联网、不花额度**。这一步失败说明是包或环境的问题，不是网络或账号的问题。
4. **问你要不要开机自启** —— 要的话把启动脚本装进 Startup 文件夹。

> 参数：`-Yes` 直接装自启不询问；`-NoAutostart` 强制跳过自启。

### 配置

用记事本打开 `config.json`：

```json
{
  "key": "oc_sk_你的key",
  "port": 8787
}
```

Key 在 OpenCode Console 拿，以 `oc_sk_` 开头。

> **⚠️ 还有一步别漏**：去 OpenCode Console 的 workspace **Privacy settings**，把区域改成 **Global**。
> 不改的话 DeepSeek 全系列会报 `This Go model requires Global regions` —— 这是账号侧设置，**代理无法绕过**。

### 启动

| 操作 | 方式 |
|---|---|
| 启动（静默） | 双击 `start-proxy.vbs` |
| 停止 | 双击 `stop-proxy.vbs` |
| 启动（看实时日志） | 双击 `start.bat` |
| 开机自启 | `install.ps1` 里选 Y，或跑 `install.ps1 -Yes` |

### 验证

```powershell
# 代理活着吗（本地端点，不消耗额度）
curl http://127.0.0.1:8787/v1/models

# 真打一发
curl http://127.0.0.1:8787/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer oc_sk_你的key" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"say OK\"}],\"max_tokens\":16}'
```

返回 `200` + 正常补全就通了。注意 DeepSeek V4.1 Flash 是推理模型，响应里还会带 `reasoning_content`（OpenAI 形状）或 `type: thinking` 块（Anthropic 形状）——**这是正常的，不是错误**。

---

## 接入客户端

Base URL 统一是 `http://127.0.0.1:8787/v1`，API Key 填你 `config.json` 里那个。

| 客户端 | 协议 | Base URL | 状态 |
|---|---|---|---|
| **WorkBuddy** | OpenAI | `http://127.0.0.1:8787/v1/chat/completions` | ✅ 见下 |
| **Claude Code** | Anthropic | `http://127.0.0.1:8787` | ✅ 见下 |
| Cursor / Cherry Studio / Continue 等 | OpenAI | `http://127.0.0.1:8787/v1` | ✅ 通用 |
| CC Switch | Anthropic | `http://127.0.0.1:8787/v1` | ✅ 无需开 Local Routing |

### WorkBuddy

编辑 `C:\Users\<你>\.workbuddy\models.json`，加一条：

```json
{
  "id": "opencode-go-deepseek-v4.1-flash",
  "name": "DeepSeek V4.1 Flash (OpenCode Go)",
  "vendor": "Custom",
  "url": "http://127.0.0.1:8787/v1/chat/completions",
  "apiKey": "oc_sk_你的key",
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

三个必须对的地方：

- `url` **必须带 `/v1/chat/completions`**
- `id` 可以是别名，代理会把 `opencode-go-*` 映射成上游认的真名；直接写 `deepseek-v4.1-flash` 也行
- **改完必须重启 WorkBuddy**，它在启动时读这个文件

### Claude Code

```powershell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8787"
$env:ANTHROPIC_API_KEY  = "oc_sk_你的key"
claude
```

代理识别到 `/v1/messages` 后，会用 **`x-api-key`** 去上游鉴权。这条链路传 `Bearer` 会被拒（见下文「双协议」）。

### 详细版

各客户端的截图级步骤、CC Switch / Codex 的具体配法，见 **[`docs/CLIENTS.md`](docs/CLIENTS.md)**。

---

## 支持的模型

模型 id **必须小写**。传 `DeepSeek-V4.1-Flash` 会得到 `Model is unavailable.`（代理已自动兜底归一化，但客户端配置里最好直接写对）。

| 模型 id | 上游协议支持 | 状态 |
|---|---|---|
| `deepseek-v4.1-flash` | OpenAI + Anthropic | ✅ 本仓库主力验证，含推理输出 |
| `deepseek-v4-flash` | OpenAI + Anthropic | 透传 |
| `deepseek-v4-pro` | OpenAI + Anthropic | 透传 |
| `mimo-v2.6-flash` | **仅 OpenAI** | ⚠️ 走 `/v1/messages` 会报 `ModelProtocolUnsupported` |
| `glm-5.3-flash` / `kimi-k3` | 取决于账号开通情况 | 透传 |

> 你实际能用哪些，取决于你的订阅和 workspace 区域设置。代理不做白名单拦截，只做 id 归一化后透传。

---

## 配置项

`config.json` 全部字段都可选。

| 字段 | 默认值 | 说明 |
|---|---|---|
| `key` | 空 | API Key。客户端自己带了就用客户端的，这里是兜底 |
| `upstream` | `https://opencode.ai/inference/go/v1` | 上游地址。**别改**，改错会跳到 Zen 按量计费通道 |
| `user_agent` | `workbuddy-opencode-go/1.0` | 上游看到的 UA |
| `model` | `deepseek-v4.1-flash` | 客户端没指定模型时的兜底 |
| `host` | `127.0.0.1` | 监听地址。**建议保持本机** |
| `port` | `8787` | 监听端口 |
| `http_proxy` | 空 | 出站代理。留空 = 直连，并**忽略**环境变量里的 `HTTP_PROXY` |

**优先级：环境变量 > `config.json` > 内置默认值。**

需要临时覆盖时不改文件：

```powershell
$env:OPENCODE_GO_PORT = "9000"
$env:OPENCODE_GO_KEY  = "oc_sk_xxx"
python proxy.py
```

支持的变量：`OPENCODE_GO_KEY`、`OPENCODE_GO_UPSTREAM`、`OPENCODE_GO_UA`、`OPENCODE_GO_MODEL`、`OPENCODE_GO_HOST`、`OPENCODE_GO_PORT`、`OPENCODE_GO_HTTP_PROXY`、`OPENCODE_GO_LOG`。

> `OPENCODE_GO_LOG` 覆盖日志路径，默认是 `proxy.py` 旁边的 `proxy.log`。自检脚本用它把测试流量写到临时文件，免得污染生产日志。

---

## 命令行

不用启动脚本也能直接跑：

```bash
python proxy.py                  # 读 config.json
python proxy.py --port 9000      # 覆盖端口
python proxy.py --host 0.0.0.0   # 覆盖监听地址（不建议）
python tools/selftest.py         # 离线自检，返回码 0 = 全过
```

---

## 项目结构

```
ocgo-bridge/
├── proxy.py                  # 代理本体，唯一的核心文件（纯标准库）
├── config.example.json       # 配置模板
├── config.json               # 你的配置（.gitignore 已排除，不会进仓库）
├── install.ps1               # 安装 + 自检 + 可选自启
├── start-proxy.vbs           # 双击启动（有弹窗反馈）
├── stop-proxy.vbs            # 双击停止
├── start.bat                 # 前台运行，看实时日志
├── startup-template.vbs      # 自启模板，由 install.ps1 装到 Startup 文件夹
├── python.txt                # 安装时写入的解释器路径（.gitignore 已排除）
├── proxy.log                 # 运行日志
├── AGENTS.md                 # 给 AI agent 读的完整操作手册
├── CLAUDE.md                 # Claude Code 入口，指向 AGENTS.md
├── README.md / README_EN.md  # 本文件 / 英文版
├── LICENSE                   # MIT
├── docs/
│   ├── CLIENTS.md            # 各客户端接入细节
│   └── TROUBLESHOOTING.md    # 排错手册
└── tools/
    └── selftest.py           # 离线自检（本地假上游，不联网）
```

---

## 工作原理

要看懂代码或自己改的人看这节。

### 双协议网关，鉴权头互斥

OpenCode Go 网关**同时**提供 OpenAI 和 Anthropic 两套接口，而这两条链路的鉴权方式**互斥** —— 传反直接 401：

| 客户端路径 | 上游路径 | 认的鉴权头 | 传错的结果 |
|---|---|---|---|
| `POST /v1/chat/completions` | `/chat/completions` | `Authorization: Bearer` | 用 `x-api-key` → `Go requires a credential` |
| `POST /v1/messages` | `/messages` | `x-api-key` | 用 Bearer → `Go requires a credential` |

代理按路径（或 `anthropic-version` 头）自动分流并把鉴权头换成正确的那个。

### session id 怎么来的

- **OpenAI 链路**：客户端没带 `x-opencode-session` 时，用**会话首条消息**派生 uuid5
- **Anthropic 链路**：优先取 Claude 自己的会话标识，没有才派生

关键在于**种子只用首条消息**。如果把消息条数也算进去，多轮对话每轮都会算出不同的 session，上游的 prompt 缓存就永远命中不了。

### 两个容易踩的实现坑（都已处理）

**非流式响应不能预先 `read()`。** 那会把 SSE 流抽干，之后再转发就是空 body —— 表现为 **HTTP 200 但内容为空**。所以流式和整包走两条独立路径。

**流式响应必须显式声明结束。** `BaseHTTPRequestHandler` 在 HTTP/1.1 下不会自动做 chunked 编码，而 SSE 没有 `Content-Length`，不处理的话客户端会一直挂着等。代理用 `Connection: close`，让 EOF 作为结束信号。

### 端口独占

Windows 上 `SO_REUSEADDR` 的语义和 Linux **相反** —— 它**允许第二个进程绑定已经在监听的端口**。Python 的 `HTTPServer` 默认开着这个选项，所以重复双击会攒出多个实例、请求被随机分发。

代理显式改用 `SO_EXCLUSIVEADDRUSE`，重复启动会直接 `WinError 10048` 并 `exit 2`。

### 出站代理

`urllib` 默认会读 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量。如果本机有 Clash 之类的代理，可能把到 `opencode.ai` 的请求劫持掉，报出一个**看起来像代码 bug** 的 502。代理默认**忽略**这些环境变量直连；确实需要走代理时，用 `config.json` 的 `http_proxy` 显式指定。

### VBS 文件的编码要求（改启动脚本前必读）

所有 `.vbs` 都是**纯 ASCII + CRLF**，这是硬性要求。

wscript 在中文 Windows 上按 **ANSI/GBK** 读 `.vbs`。文件里一旦有非 ASCII 字节（哪怕只是中文注释），就会被当 GBK 解码成乱码。GBK 是双字节编码，乱码的第二个字节可能**吃掉行尾的换行符**，导致两行合并、语法错误行号错位，报出一个莫名其妙的：

```
Microsoft VBScript 编译器错误 / 行 18 / 字符 1 / 缺少语句 / 800A0400
```

**所以：不要在这些 `.vbs` 里写中文，注释也不行。** 解释器和端口都是运行时从 `python.txt` / `config.json` 读的，脚本里没有任何需要写中文的地方。

---

## 排错

**先看 `proxy.log`**，九成问题都在里面。

| 现象 | 原因 & 解法 |
|---|---|
| `400 MissingSessionID` | 请求没走代理，客户端直连上游了。检查 Base URL 是不是 `127.0.0.1:8787` |
| `401 Go requires a credential` | 鉴权头传反。`/v1/messages` 要 `x-api-key`，`/v1/chat/completions` 要 Bearer。代理已自动处理，出现这个说明请求没经过代理 |
| `Model is unavailable.` | model id 大小写不对，上游只认小写 |
| `This Go model requires Global regions` | 去 Console 把 workspace 区域改成 **Global**。账号侧设置，代理绕不过 |
| `Insufficient account funds` | 走错网关，跑到 Zen 按量计费通道了。`upstream` 必须是 `.../inference/go/v1` |
| `502 upstream unreachable: ...` | **代理自己**报的 —— 本机到不了 `opencode.ai`。查网络/防火墙/DNS |
| `502 upstream connect failed: ...` | **不是代理的措辞** —— 有另一个本地代理（Clash、沙箱等）劫持了连接。配 `http_proxy` 或关掉它 |
| `bind failed ... [WinError 10048]` | 端口被占。双击 `stop-proxy.vbs`，或改 `config.json` 的 `port` |
| 双击 vbs 没反应 | 双击 `start.bat` 看报错。常见是 `python.txt` 里的路径失效 |
| 改了 `config.json` 不生效 | 配置只在启动时读一次。重启代理 |
| VBS 报 `800A0400 / 缺少语句` | 该 `.vbs` 里有非 ASCII 字节或裸 LF。恢复成纯 ASCII + CRLF |

> 两个 502 长得像但**责任方不同**：`upstream unreachable` 是本代理说的，`upstream connect failed` 是链路上另一个代理说的。分清这个能省很多时间。

详细版（含 `AGENTS.md` 里的完整诊断表）见 **[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)**。

---

## 常见问题

**Q：这算不算绕过 OpenCode 的限制？**

不算。你用的是**自己付费的**订阅，只是补一个客户端架构上发不出来的必要请求头。代理不改配额、不共享账号、不伪造身份，纯粹是协议适配层。

**Q：Key 存在哪？安全吗？**

明文存在 `config.json`，只在本机。代理默认只监听 `127.0.0.1`，外部连不上。**不要把 `config.json` 提交到 Git**（`.gitignore` 已排除），也别把这个目录发给别人。万一泄露，去 Console 吊销重发。

**Q：能装在 macOS / Linux 上吗？**

`proxy.py` 是跨平台的，`python3 proxy.py` 直接跑。但 `.vbs` 和 `install.ps1` 是 Windows 专用的，自启需要你自己配 systemd / launchd。

**Q：会不会重复启动攒一堆进程？**

不会。端口用了排他绑定，第二个实例会立刻 `exit 2`。

**Q：开机自启为什么需要 `proxy_dir.txt`？**

因为启动脚本被复制到 Startup 文件夹后，它**无法从自己的位置推断出代理装在哪**。所以安装时把真实路径写进 `proxy_dir.txt`。**如果你移动了整个目录，重跑一次 `install.ps1` 即可**，否则自启会静默失效。

---

## 安全

- `config.json` 存着**明文 API Key**。不要提交、不要外传。
- `host` 保持 `127.0.0.1`。改成 `0.0.0.0` 等于把 Key 暴露给整个局域网。
- 本项目**不收集、不上报**任何数据，所有流量只在你本机和 `opencode.ai` 之间。

---

## 开源协议

本项目采用 [MIT License](LICENSE)。

---

**如果对你有帮助，欢迎 Star ⭐**
