# 排错手册

`README.md` 里的排错表是速查版，这份是完整版 —— 带排查顺序、证据收集方法，以及每个错误的根因解释。

---

## 一、先按这个顺序排查

**90% 的问题在第 2 步就能定位。** 不要跳。

| # | 做什么 | 看到什么说明什么 |
|---|---|---|
| 1 | 看 `proxy.log` 最后 20 行 | 代理自己报的错都在这里。日志里没有报错 → 问题不在代理 |
| 2 | `curl http://127.0.0.1:8787/v1/models` | 有 JSON 返回 = 代理活着；连不上 = 代理没起或端口不对 |
| 3 | 同一个 curl 打个真请求（见 README） | 200 = 代理链路完全通，问题 100% 在客户端配置 |
| 4 | `python tools/selftest.py` | 失败 = 包本身或 Python 环境坏了，跟网络/账号无关 |

**为什么这个顺序**：第 2、3 步把「代理坏了」和「客户端配错了」彻底分开。跳过它们直接去翻客户端配置，是最常见的浪费时间方式 —— 大部分「客户端连不上」其实是代理根本没起来。

---

## 二、症状速查（完整版）

### 代理相关

| 现象 | 根因 | 解法 |
|---|---|---|
| `bind failed on 127.0.0.1:8787 -> [WinError 10048]` | 端口已被另一个实例占用 | 双击 `stop-proxy.vbs` 后重启；或改 `config.json` 的 `port` |
| 日志停在 `listening on ...` 之后再无输出 | 正常。代理是静默的，只在请求到来时记日志 | 发个请求再看 |
| 日志里 `no config.json; using defaults` | `config.json` 不存在 | 从 `config.example.json` 复制一份，填 `key` |
| 日志里 `no fallback key; clients must send their own` | `config.json` 的 `key` 是空的 | 填上，或者确认客户端自己带了 Key |
| 日志里 `fallback key loaded (0 chars)` | `key` 字段存在但是空串 | 填上真实 Key |
| 改完 `config.json` 毫无变化 | 配置**只在启动时读一次** | 重启代理。没有热重载，这是设计如此 |
| 日志里 `env HTTP(S)_PROXY ignored; connecting upstream directly` | 说明本机设了环境变量代理，被代理主动忽略了 | 正常。要真走代理就在 `config.json` 里显式写 `http_proxy` |

### 鉴权 / 会话相关

| 现象 | 根因 | 解法 |
|---|---|---|
| `400 MissingSessionID` | 请求**没走代理**，客户端直连上游了 | 检查 Base URL 是不是 `127.0.0.1:8787`。WorkBuddy 的 `url` 必须写到 `/v1/chat/completions` |
| `401 Go requires a credential` | 鉴权头与该端点不匹配 | `/v1/messages` 要 `x-api-key`；`/v1/chat/completions` 要 `Bearer`。代理已自动处理 —— **出现这个说明请求根本没经过代理**，去查 Base URL |
| `401 Invalid API key` / 类似 | Key 本身不对 | 去 OpenCode Console 重新复制，注意以 `oc_sk_` 开头、没有多余空格 |
| 客户端报 404 | Base URL 少写或多写了 `/v1` | OpenAI 协议要到 `/v1`（或完整 `/v1/chat/completions`）；Anthropic 协议（Claude Code）**不带 `/v1`** |

> **这两个 401/400 的共同点**：它们都是**上游**返回的。只要请求真的进了代理，代理就会补上正确的头，不会产生这两个错误。所以看到它们，永远先怀疑「客户端没连到代理」。

### 账号 / 模型相关

| 现象 | 根因 | 解法 |
|---|---|---|
| `This Go model requires Global regions` | workspace 区域不是 Global | OpenCode Console → workspace **Privacy settings** → 改成 **Global**。**账号侧设置，代理绕不过去** |
| `Model is unavailable.` | model id 大小写不对 | 上游只认小写。用 `deepseek-v4.1-flash`，不要 `DeepSeek-V4.1-Flash` |
| `ModelProtocolUnsupported` | 该模型不支持当前协议 | 例：`mimo-v2.6-flash` 只支持 OpenAI 协议，走 `/v1/messages` 必报。换模型或换协议 |
| `Insufficient account funds` | 走错网关，跑到 **Zen 按量计费**通道了 | `config.json` 的 `upstream` 必须是 `https://opencode.ai/inference/go/v1`。检查是不是被改成了 `/zen/v1` |

### 网络相关

| 现象 | 根因 | 解法 |
|---|---|---|
| `502 upstream unreachable: ...` | **本代理**报的 —— 本机到不了 `opencode.ai` | 查 DNS / 防火墙 / 网络连通性 |
| `502 upstream connect failed: ... (os error 10061)` | **不是本代理的措辞** —— 链路上**另一个**本地代理（Clash 等）劫持了连接 | 在 `config.json` 写明 `http_proxy`，或临时关掉那个代理 |
| 请求长时间挂住不返回 | 网络慢，或上游在长思考 | 等；或加 `max_tokens` 上限测试能否快速返回 |

> **两个 502 长得像但责任方不同，这是最容易误判的一处。**
>
> `upstream unreachable` 是**本代理**的措辞 —— 说明代理正常运行，只是自己出不去，问题在本机网络。
>
> `upstream connect failed` 带 `os error` 的写法**不是本代理的输出** —— 说明在代理和上游之间还夹着另一个代理进程。此时关掉 Clash 之类，或者在 `config.json` 里把 `http_proxy` 指向它。
>
> 分不清这两个，会把「另一个软件的问题」误判成「本项目的问题」，反过来也一样。

### 启动脚本相关

| 现象 | 根因 | 解法 |
|---|---|---|
| 双击 `start-proxy.vbs` 没任何反应 | `python.txt` 里的路径失效，或代理已经在跑 | 双击 `start.bat`（前台运行）看真实报错。检查 `python.txt` 内容 |
| VBS 报 `800A0400 / 缺少语句 / expected statement` | 该 `.vbs` 里混进了**非 ASCII 字节**或**裸 LF 换行** | 见下方专节。这三个 `.vbs` 必须恢复成纯 ASCII + CRLF |
| 双击后弹出「已停止 / 已在运行」提示 | 代理已在跑，排他绑定挡住了第二个实例 | 正常行为，不用管 |
| 换机器后双击就报找不到 `proxy.py` | 第一次运行时 `python.txt` 记录的路径在新机器不存在 | 在新机器上重跑一次 `install.ps1` |

### 自启相关

| 现象 | 根因 | 解法 |
|---|---|---|
| 开机后代理没起来 | Startup 文件夹里的 `proxy_dir.txt` 指向的目录已经不存在（移动过目录） | **重跑 `install.ps1`**。它会重写 `proxy_dir.txt` |
| Startup 文件夹里只有 `OpenCodeGoProxy.vbs`，没有 `proxy_dir.txt` | 装自启那一步没跑完，或被手动删了 | 重跑 `install.ps1` |
| 想彻底关掉自启 | —— | 把 Startup 文件夹里的 `OpenCodeGoProxy.vbs` 和 `proxy_dir.txt` 都删掉 |

Startup 文件夹路径：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`，或在运行框里敲 `shell:startup`。

> **自启为什么需要两个文件**：`OpenCodeGoProxy.vbs` 被复制到 Startup 文件夹后，它**无法从自己的位置推断出代理装在哪**（它旁边没有 `proxy.py`）。所以安装时把真实路径写进同目录的 `proxy_dir.txt`，脚本启动时读它来找家。这是本项目唯一一处「移动目录必须重装」的地方。

---

## 三、VBS 报 `800A0400` 的完整解释

这是本项目里**最容易被误判成代码 bug** 的一个坑，单独说清楚。

**现象**：双击某个 `.vbs` 弹出

```
Microsoft VBScript 编译器错误
行 18 / 字符 1 / 缺少语句 / 800A0400
```

**根因**：wscript 在中文 Windows 上按 **ANSI / GBK** 读 `.vbs`。

文件里只要有一个非 ASCII 字节（**哪怕只是中文注释**），后面整段就会被当 GBK 解码。GBK 是双字节编码 —— 一个乱码的尾字节可能是 `0x0A`（换行）的高位的一半，于是**行尾的换行符被吃掉**，两行合并成一行。语法在这种合并处崩掉，行号也随之前移或后移。

所以：

- **报错行号是错的**，别盯着它改
- **看起来像语法错误，其实文件语法没错**，错的是编码
- 删掉那一行「可疑代码」没用，因为不是那行的问题

**硬规则**：这三个 `.vbs` 里**不要出现任何中文，注释也不行**。

- 纯 ASCII
- CRLF 换行（不能是裸 LF）
- 不放 `^` 或 `|` 这类在命令行里有特殊含义的字符

解释器路径从 `python.txt` 读，端口从 `config.json` 读 —— **脚本里没有任何需要写中文的地方**，这个规则不需要你妥协任何东西。

**怎么判断某个 `.vbs` 有没有被污染**：

```powershell
# 列出所有非 ASCII 字符的位置（应该无输出）
$p = 'start-proxy.vbs'
$b = [System.IO.File]::ReadAllBytes($p)
for ($i = 0; $i -lt $b.Length; $i++) {
    if ($b[$i] -gt 127) { "non-ASCII byte $($b[$i]) at offset $i" }
}

# 检查是否有裸 LF（应该无输出）
$t = [System.IO.File]::ReadAllText($p)
if ($t -match "(?<!`r)`n") { 'bare LF found' } else { 'CRLF ok' }
```

两条命令都无输出 → 文件是干净的，`800A0400` 一定另有原因（此时去看 `python.txt` 和 `proxy.log`）。

---

## 四、怎么收集证据

排错时把下面这一组输出一次性收集齐，比来回猜快得多。

```powershell
# 1. 代理在听吗？应该只有 1 条
Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue

# 2. 日志最后 30 行
Get-Content .\proxy.log -Tail 30 -Encoding UTF8

# 3. 代理活着吗（本地端点，不花额度）
curl http://127.0.0.1:8787/v1/models

# 4. python.txt 里记的解释器还能用吗
$py = Get-Content .\python.txt -Raw -Encoding UTF8
& $py.Trim() -V
if ($LASTEXITCODE -ne 0) { 'python.txt 记录的解释器已失效' }

# 5. 包本身是好的吗
& $py.Trim() .\tools\selftest.py
```

第 3 步能返回 JSON、第 5 步 `RESULT: PASS` → **代理和包都是好的**，问题在客户端配置或账号侧。

---

## 五、客户端连不上时的二分法

代理已验证正常（上面第 3、5 步都过），但某个客户端就是不行 —— 按协议分流：

```powershell
# A. OpenAI 协议
curl http://127.0.0.1:8787/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer oc_sk_你的key" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":16}'

# B. Anthropic 协议（注意鉴权头不同）
curl http://127.0.0.1:8787/v1/messages `
  -H "Content-Type: application/json" `
  -H "x-api-key: oc_sk_你的key" `
  -H "anthropic-version: 2023-06-01" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"max_tokens\":64,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'
```

| A | B | 结论 |
|---|---|---|
| 通 | 通 | 代理和账号都好，**问题 100% 在客户端配置**。去核对 Base URL / Key / model id |
| 通 | 不通 | 该客户端用 Anthropic 协议但配错了。Base URL 不带 `/v1`、鉴权头必须是 `x-api-key` |
| 不通 | 通 | 该客户端用 OpenAI 协议但配错了。`url` 要写到 `/v1/chat/completions` |
| 不通 | 不通 | 偏账号侧。看 `proxy.log` 里的上游返回，对照第二节的账号表 |

---

## 六、确认不是故障的几件事

这几个现象看起来像 bug，其实都是**设计如此或上游特性**。

| 现象 | 说明 |
|---|---|
| 响应里有 `reasoning_content`（OpenAI）或 `type: thinking` 块（Anthropic） | `deepseek-v4.1-flash` 是**推理模型**，思考过程就是这么输出的。正常 |
| 给了 `max_tokens: 16` 或 `32`，`content` 是空的、`stop_reason` 是 `max_tokens` | 思考过程先把额度吃光了。**加大到 256 以上**。不是故障 |
| 双击 `start-proxy.vbs` 完全没有窗口 | 设计如此 —— 静默常驻，不弹终端。要看输出用 `start.bat` |
| 重复双击 `start-proxy.vbs` 第二次只弹个提示 | 排他绑定在起作用，不会攒出多个实例。正常 |
| 日志里明明设了 `HTTP_PROXY` 却写「ignoring」 | 代理**故意忽略**环境变量代理，防止被本机 Clash 之类劫持。要真走代理请在 `config.json` 里显式写 |
| `curl /v1/models` 返回的列表不全 | 该端点由代理本地生成，不代表你账号实际可用范围。真实可用性取决于订阅和区域设置 |

---

## 七、完全重置

所有状态都在两处：包目录，和 Startup 文件夹。**没有注册表、没有服务、没有别处写入**。

```powershell
# 1. 停掉
wscript .\stop-proxy.vbs
# 兜底：按端口杀
Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# 2. 清掉生成物
Remove-Item .\python.txt, .\proxy.log -Force -ErrorAction SilentlyContinue

# 3. 清掉 Startup 里的两个文件
$sf = [Environment]::GetFolderPath('Startup')
Remove-Item (Join-Path $sf 'OpenCodeGoProxy.vbs') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $sf 'proxy_dir.txt')       -Force -ErrorAction SilentlyContinue

# 4. 从头装一遍
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

`config.json` **不要删** —— 里面是你的 Key。重置只针对生成物和自启。

---

## 八、还是不通

按这个模板收集信息再提 issue：

```
1. 操作系统 / Python 版本：
2. install.ps1 是否跑过、结果（自检 PASS 还是 FAIL）：
3. python tools/selftest.py 的输出：
4. proxy.log 最后 30 行：
5. Get-NetTCPConnection -LocalPort 8787 -State Listen 的结果：
6. 第 3 步 curl /v1/models 的返回：
7. 客户端名字 + Base URL 配置截图：
8. 客户端报的完整错误文本：
```

**提交前把 Key 打码。** 第 4、6 步的输出里可能带 `oc_sk_...`。

更底层的原理（双协议鉴权、session id 派生、两个 HTTP 实现坑、端口独占）见仓库根目录的 `AGENTS.md` 第 11 节，以及 `README.md` 的「工作原理」。
