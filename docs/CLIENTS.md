# 各客户端接入细节

统一的入口信息：

| 项目 | 值 |
|---|---|
| Base URL（OpenAI 协议） | `http://127.0.0.1:8787/v1` |
| Base URL（Anthropic 协议） | `http://127.0.0.1:8787` |
| API Key | `config.json` 里那个 `oc_sk_...` |
| 默认模型 | `deepseek-v4.1-flash` |

改任何客户端配置前，先确认代理活着：

```powershell
curl http://127.0.0.1:8787/v1/models
```

---

## WorkBuddy

配置文件：`C:\Users\<用户名>\.workbuddy\models.json`（一个 JSON 数组）

在数组里追加一条：

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

**为什么非得走代理**：WorkBuddy 的 `models.json` 能配 `url`、能配 `apiKey`，但**没有自定义请求头字段**。OpenCode Go 却强制要 `x-opencode-session`。架构上塞不进去，所以必须有个本地中转。

三个易错点：

1. `url` 结尾**必须**是 `/v1/chat/completions`，只写到 `/v1` 会 404
2. `id` 可以随便起（代理会映射），但**不要用大写**，避免踩上游的大小写敏感
3. **改完必须重启 WorkBuddy** —— 它只在启动时读这个文件

> 如果 `models.json` 里原本有指向 `opencode.ai` 直连的条目，把它删掉或改走代理，否则会一直吃 `400 MissingSessionID`。

---

## Claude Code

Claude Code 走 Anthropic 协议，直接改环境变量：

```powershell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8787"
$env:ANTHROPIC_API_KEY  = "oc_sk_你的key"
claude
```

想持久化就写进用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://127.0.0.1:8787", "User")
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "oc_sk_你的key", "User")
```

注意 `ANTHROPIC_BASE_URL` **不带 `/v1`** —— Claude Code 自己会拼 `/v1/messages`。代理识别到这条路径后，会用 `x-api-key` 去上游鉴权（不是 Bearer）。

---

## CC Switch

CC Switch 支持填 Anthropic 兼容的 Base URL：

- **Provider 类型**：Anthropic
- **Base URL**：`http://127.0.0.1:8787/v1`
- **API Key**：`oc_sk_你的key`

**不需要开 CC Switch 的 Local Routing。** 它自带的 session 处理只用于本地日志统计，**不会**向上游注入 `x-opencode-session` —— 所以直连上游必定 400。让 CC Switch 只管切换 provider，补头交给本代理，少一层转发更稳。

---

## Codex

Codex 走 OpenAI 协议。编辑 `~/.codex/config.toml`：

```toml
[model_providers.ocgo]
name = "OpenCode Go"
base_url = "http://127.0.0.1:8787/v1"
env_key = "OPENCODE_GO_KEY"

[profiles.ocgo]
model_provider = "ocgo"
model = "deepseek-v4.1-flash"
```

然后设好 `OPENCODE_GO_KEY` 环境变量，用 `codex --profile ocgo` 启动。

> Codex 默认走 Responses API。如果你的版本用的是 `/v1/responses`，本代理不提供该端点，需要在配置里指定走 chat completions。

---

## Cursor

`Settings → Models → OpenAI API Key`：

- **Override OpenAI Base URL**：`http://127.0.0.1:8787/v1`
- **API Key**：`oc_sk_你的key`
- **Model**：手动添加 `deepseek-v4.1-flash`

Cursor 会对模型做能力探测，如果它拒绝这个模型名，就直接手填模型 id。

---

## Cherry Studio / Continue / Chatbox / NextChat 等

这些都是标准 OpenAI 兼容客户端，填法一样：

| 字段 | 值 |
|---|---|
| API Host / Base URL | `http://127.0.0.1:8787/v1` |
| API Key | `oc_sk_你的key` |
| Model | `deepseek-v4.1-flash` |

如果客户端要求「API Host」和「完整 URL」分开填，注意别拼成 `/v1/v1/chat/completions`。

---

## 通用 curl 验证

排任何客户端问题之前，先用 curl 确认代理本身是好的：

```powershell
# 1. 代理活着吗（本地端点，不花额度）
curl http://127.0.0.1:8787/v1/models

# 2. OpenAI 协议
curl http://127.0.0.1:8787/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer oc_sk_你的key" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":16}'

# 3. Anthropic 协议（注意鉴权头不同）
curl http://127.0.0.1:8787/v1/messages `
  -H "Content-Type: application/json" `
  -H "x-api-key: oc_sk_你的key" `
  -H "anthropic-version: 2023-06-01" `
  -d '{\"model\":\"deepseek-v4.1-flash\",\"max_tokens\":64,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'
```

三条都通 → 问题在客户端配置。只有第 2 条通 → 客户端用错了协议。三条都不通 → 代理本身或账号侧有问题，去看 `proxy.log`。

---

## 关于推理模型

`deepseek-v4.1-flash` 是推理模型，响应会包含思考过程：

- **OpenAI 形状**：`choices[0].message.reasoning_content`（和 `content` 并列）
- **Anthropic 形状**：`content` 数组里多一个 `{"type": "thinking", ...}` 块

两个后果：

1. **`max_tokens` 要给够**。给 16 或 32 时，思考过程会把额度吃光，导致 `content` 为空、`stop_reason` 是 `max_tokens`。这不是故障，加大额度即可（测试时给 256 以上比较稳）。
2. 部分客户端不认 `reasoning_content` 字段，会忽略它 —— 忽略就忽略，`content` 照样正常。
