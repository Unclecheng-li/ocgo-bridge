"""
OpenCode Go -> WorkBuddy 本地转发代理

用途:
    WorkBuddy 的 models.json 不支持自定义 HTTP 请求头, 而 OpenCode Go 网关
    强制要求 x-opencode-session (缺了直接 400 MissingSessionID, 与 key 是否有效无关)。
支持的两种协议(实测确认):
    1. OpenAI Chat Completions   POST /v1/chat/completions
       -> 上游 /chat/completions, 鉴权只用 Authorization: Bearer
    2. Anthropic Messages        POST /v1/messages
       -> 上游 /messages,        鉴权只用 x-api-key (Bearer 会被拒, 返回 "Go requires a credential")

    两条链路都必须带 x-opencode-session, 这是本代理存在的唯一理由。

用法:
    python proxy.py                 # 前台运行, 日志打到 stdout 和 proxy.log
    python proxy.py --port 8787     # 指定端口

配置优先级: 环境变量 > 同目录 config.json > 内置默认值
    config.json 是可选的, 存在的意义是「搬机器只改一个文件」——
    API Key / 端口 / 上游地址都不必再去改代码。字段见 config.example.json:
        key          API Key (等价于 OPENCODE_GO_KEY)
        upstream     上游地址 (等价于 OPENCODE_GO_UPSTREAM)
        user_agent   上游看到的 User-Agent (等价于 OPENCODE_GO_UA)
        model        兜底模型 (等价于 OPENCODE_GO_MODEL)
        host / port  监听地址与端口
        http_proxy   出站代理; 留空则直连并忽略环境里的 HTTP(S)_PROXY
"""

import argparse
import json
import os
import socket
import sys
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlrequest
from urllib.error import HTTPError

UPSTREAM_DEFAULT = "https://opencode.ai/inference/go/v1"
UA_DEFAULT = "workbuddy-opencode-go/1.0"
MODEL_DEFAULT = "deepseek-v4.1-flash"

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config.json"
)


def load_config():
    """读取同目录 config.json。

    设计意图: 把「每个环境都不一样」的东西(key / 端口 / 上游 / 出站代理)
    集中到一个文件, 这样把整个目录拷到另一台机器时只需要改 config.json,
    不用动代码。文件不存在或损坏都不影响运行, 直接回落默认值。
    """
    if not os.path.isfile(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


CFG = load_config()


def cfg(name, env_name, default):
    """配置取值: 环境变量 > config.json > 默认值。"""
    v = os.environ.get(env_name)
    if v is None:
        v = CFG.get(name)
    if v is None or (isinstance(v, str) and not v.strip()):
        return default
    return v


UPSTREAM = str(cfg("upstream", "OPENCODE_GO_UPSTREAM", UPSTREAM_DEFAULT)).rstrip("/")
FALLBACK_KEY = str(cfg("key", "OPENCODE_GO_KEY", ""))
UA = str(cfg("user_agent", "OPENCODE_GO_UA", UA_DEFAULT))
OUTBOUND_PROXY = str(cfg("http_proxy", "OPENCODE_GO_HTTP_PROXY", ""))

# OpenCode 文档要求: 每个会话一个稳定 session id, 便于路由与 prompt 缓存。
# 客户端不传时, 用会话首条消息内容派生一个稳定 UUID, 保证同一对话多轮复用。
SESSION_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

# WorkBuddy 侧可以给模型起任意 id, 但上游网关只认自己的小写 id。
# 这里做一层映射: 命中就用映射值, 未命中但本身已是合法 Go id 则直接用,
# 都不满足时回落到 DEFAULT_MODEL, 避免把无意义的显示名丢给上游。
MODEL_MAP = {
    "opencode-go-deepseek-v4.1-flash": "deepseek-v4.1-flash",
    "opencode-go-deepseek-v4-flash": "deepseek-v4-flash",
    "opencode-go-deepseek-v4-pro": "deepseek-v4-pro",
    "opencode-go-mimo-v2.6-flash": "mimo-v2.6-flash",
}
KNOWN_IDS = set(MODEL_MAP.values()) | {
    "deepseek-v4.1-flash",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-flash",
    "mimo-v2.6-flash",
    "glm-5.3-flash",
    "kimi-k3",
}
DEFAULT_MODEL = str(cfg("model", "OPENCODE_GO_MODEL", MODEL_DEFAULT))


def build_opener():
    """构造上游 opener, 显式忽略环境里的 HTTP(S)_PROXY。

    urllib 默认会读 http_proxy / https_proxy 环境变量。本机这些变量有时指向
    沙箱或 Clash 之类的本地代理, 它们会拦掉 opencode.ai, 上游连接就变成
    "upstream connect failed / 目标计算机积极拒绝" 的 502, 而问题出在环境、
    不在代理本身。目标是固定域名, 直连即可, 所以默认绕过环境代理;
    确实需要走代理时用 OPENCODE_GO_HTTP_PROXY 显式指定。
    """
    custom = OUTBOUND_PROXY.strip() if OUTBOUND_PROXY else ""
    if custom:
        handler = urlrequest.ProxyHandler({"http": custom, "https": custom})
    else:
        handler = urlrequest.ProxyHandler({})
    return urlrequest.build_opener(handler)


_opener = None


def resolve_model(model):
    raw = (model or "").strip()
    if raw in MODEL_MAP:
        return MODEL_MAP[raw], raw != MODEL_MAP[raw]
    low = raw.lower()
    if low in MODEL_MAP:
        return MODEL_MAP[low], raw != MODEL_MAP[low]
    if low in KNOWN_IDS:
        return low, raw != low
    return DEFAULT_MODEL, raw != DEFAULT_MODEL

# 日志默认写在 proxy.py 旁边。允许 OPENCODE_GO_LOG 覆盖: 自检脚本会把日志
# 指到临时文件, 免得测试流量混进生产日志 —— 排错第一步就是看 proxy.log,
# 混进测试记录会干扰判断。
_LOG_OVERRIDE = str(cfg("log", "OPENCODE_GO_LOG", "")).strip()
LOG_PATH = _LOG_OVERRIDE or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "proxy.log")


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def derive_session_id(payload):
    """从请求体派生稳定的 session id."""
    try:
        msgs = payload.get("messages") or []
        if not msgs:
            return str(uuid.uuid4())
        first = msgs[0]
        content = first.get("content")
        if isinstance(content, list):
            content = "".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        # 只用会话首条消息做种子: 同一对话多轮追加消息时 session 保持不变,
        # 上游才能复用 prompt 缓存。不能把消息条数算进来, 否则每轮都会漂移。
        seed = "%s|%s" % (first.get("role", ""), content or "")
        return str(uuid.uuid5(SESSION_NAMESPACE, seed))
    except Exception:
        return str(uuid.uuid4())


def extract_key(auth_header):
    """从 Authorization / x-api-key 里剥出裸 key。

    两个上游端点认的鉴权头不同, 所以这里统一取裸值, 由调用方按目标端点重新包装。
    Anthropic 端点只认 x-api-key, chat/completions 只认 Bearer, 传反了会 401。
    """
    if auth_header:
        v = auth_header.strip()
        if v.lower().startswith("bearer "):
            return v[7:].strip()
        return v
    return FALLBACK_KEY


def is_anthropic_request(path, payload, headers):
    """判断是否为 Anthropic Messages 请求。

    Claude Code / CC Switch 走 Anthropic 格式: 路径是 /messages,
    且/或带 anthropic-version 头。cc-switch 直列传 Live 时两者都成立。
    """
    clean = path.split("?")[0].rstrip("/")
    if clean.endswith("/messages"):
        return True
    if headers.get("anthropic-version"):
        return True
    return False


def pick_anthropic_session_id(payload, headers):
    """Anthropic 侧的 session id 提取。

    优先用 Claude 自己的会话标识, 这样同一对话的 x-opencode-session 保持稳定,
    上游 prompt 缓存才能命中。都没有时按首条消息派生。
    """
    for h in ("x-opencode-session", "x-claude-code-session-id", "claude-code-session-id"):
        v = headers.get(h)
        if v:
            return v.strip()

    try:
        md = payload.get("metadata") or {}
        uid = md.get("user_id")
        if isinstance(uid, str) and "_session_" in uid:
            return uid.split("_session_")[-1]
        if md.get("session_id"):
            return str(md["session_id"])
    except Exception:
        pass

    return derive_session_id(payload)


# 同时兼容 OpenAI 与 Anthropic 两种 models 列表格式:
# OpenAI 取 data[].id, Anthropic 取 data[].id 与 data[].display_name。
PROBE_MODELS = [
    {
        "id": m,
        "object": "model",
        "type": "model",
        "display_name": m,
        "created": 0,
        "owned_by": "opencode",
    }
    for m in [
        "deepseek-v4.1-flash",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "mimo-v2.6-flash",
        "glm-5.3-flash",
        "kimi-k3",
    ]
]


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_response(self, code, ctype, resp):
        """流式响应: 边收边转发 SSE, 绝不预先 read。

        SSE 长度事先未知, 拿不到 Content-Length, 而 BaseHTTPRequestHandler 在
        HTTP/1.1 下不会自动做 chunked 编码 —— 不显式声明结束方式的话, 客户端
        会一直挂着等 body 结束, 表现为「请求发出去了但永远不返回」。
        这里用 Connection: close, 让 EOF 作为流结束的信号, 兼顾简单与可靠。
        """
        self.send_response(code)
        self.send_header("Content-Type", ctype or "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            log("client disconnected during streaming")
        finally:
            resp.close()

    def _body_response(self, code, ctype, body):
        """非流式响应: 整包读完一次性返回。

        HTTP/1.1 keep-alive 下必须给 Content-Length, 否则客户端无从判断
        响应何时结束, 会一直挂到超时。
        """
        self.send_response(code)
        self.send_header("Content-Type", ctype or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send_json(200, {"object": "list", "data": PROBE_MODELS})
        else:
            self._send_json(200, {"status": "ok", "upstream": UPSTREAM})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"

        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            self._send_json(400, {"error": {"message": "invalid JSON body"}})
            return

        # 协议分流: Anthropic Messages 与 OpenAI Chat Completions 的鉴权头不同,
        # 端点也不同。判错协议会直接 401 / 404。
        anthropic = is_anthropic_request(self.path, payload, self.headers)

        key = extract_key(self.headers.get("Authorization") or self.headers.get("x-api-key"))
        if not key:
            self._send_json(
                401,
                {"error": {"message": "no credential: send Authorization / x-api-key "
                                      "header, or set OPENCODE_GO_KEY"}},
            )
            return

        if anthropic:
            session_id = pick_anthropic_session_id(payload, self.headers)
        else:
            session_id = self.headers.get("x-opencode-session") or derive_session_id(payload)

        # 模型名兜底修正: 网关只认自己的小写 id
        model = payload.get("model") or ""
        resolved, changed = resolve_model(model)
        if changed:
            log("model mapped: %s -> %s" % (model, resolved))
            payload["model"] = resolved
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        # Claude 默认模型的兜底: Anthropic 侧若未指定模型, 用默认而不是原样转发
        if anthropic and not payload.get("model"):
            payload["model"] = DEFAULT_MODEL
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if anthropic:
            upstream_url = UPSTREAM + "/messages"
            auth_mode = "x-api-key"
        else:
            upstream_url = UPSTREAM + "/chat/completions"
            auth_mode = "Bearer"
        wants_stream = bool(payload.get("stream"))

        req = urlrequest.Request(upstream_url, data=raw, method="POST")
        req.add_header("Content-Type", "application/json")
        # Anthropic 端点只认 x-api-key, chat/completions 只认 Bearer
        if anthropic:
            req.add_header("x-api-key", key)
        else:
            req.add_header("Authorization", "Bearer %s" % key)
        req.add_header("x-opencode-session", session_id)
        req.add_header("User-Agent", UA)
        if anthropic:
            req.add_header(
                "anthropic-version",
                self.headers.get("anthropic-version") or "2023-06-01",
            )
        if self.headers.get("Accept"):
            req.add_header("Accept", self.headers.get("Accept"))

        log("[%s] -> %s session=%s stream=%s"
            % (auth_mode, payload.get("model"), session_id[:8], wants_stream))

        try:
            resp = _opener.open(req, timeout=600)
            ctype = resp.headers.get("Content-Type")
            # 流式和整包必须分开走: 预先 read() 会把 SSE 流抽干,
            # 导致后续转发出来的是空 body(表现为 HTTP 200 但内容为空)。
            if wants_stream:
                self._stream_response(resp.status, ctype, resp)
            else:
                self._body_response(resp.status, ctype, resp.read())
                resp.close()

        except HTTPError as e:
            detail = e.read()
            ctype = e.headers.get("Content-Type") if e.headers else None
            try:
                up = json.loads(detail)
                msg = up.get("error", {}).get("message") or up.get("error", {}).get("type")
            except ValueError:
                msg = detail.decode("utf-8", "replace")[:300]
            log("!! upstream %s: %s" % (e.code, msg))
            self.send_response(e.code)
            self.send_header("Content-Type", ctype or "application/json")
            self.send_header("Content-Length", str(len(detail)))
            self.end_headers()
            try:
                self.wfile.write(detail)
            except (BrokenPipeError, ConnectionResetError):
                pass

        except Exception as e:
            log("!! upstream error: %r" % (e,))
            self._send_json(
                502, {"error": {"message": "upstream unreachable: %s" % (e,)}}
            )


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """独占端口, 防止重复双击攒出多个实例。

    Python 的 HTTPServer 默认 allow_reuse_address = 1, 而 Windows 上
    SO_REUSEADDR 的语义是「允许其它进程再绑定同一端口」(与 Linux 相反),
    于是第二个实例也能 bind 成功并静默生效, 请求被随机分发到两个实例上。
    改用 SO_EXCLUSIVEADDRUSE 独占端口: 端口已被占用时直接抛 WinError 10048。
    """

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
            )
        ThreadingHTTPServer.server_bind(self)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=str(cfg("host", "OPENCODE_GO_HOST", "127.0.0.1")))
    ap.add_argument("--port", type=int, default=int(cfg("port", "OPENCODE_GO_PORT", 8787)))
    args = ap.parse_args()

    global _opener
    _opener = build_opener()

    if os.path.isfile(CONFIG_PATH):
        log("config loaded from %s" % CONFIG_PATH)
    else:
        log("no config.json; using defaults (copy config.example.json)")
    log("upstream = %s" % UPSTREAM)
    if OUTBOUND_PROXY:
        log("outbound via proxy %s" % OUTBOUND_PROXY)
    else:
        log("env HTTP(S)_PROXY ignored; connecting upstream directly")
    if FALLBACK_KEY:
        log("fallback key loaded (%d chars) - clients may also send their own" % len(FALLBACK_KEY))
    else:
        log("no fallback key; clients must send Authorization / x-api-key")

    try:
        srv = ExclusiveThreadingHTTPServer((args.host, args.port), ProxyHandler)
    except OSError as e:
        log("bind failed on %s:%d -> %s" % (args.host, args.port, e))
        log("port already in use; another instance is probably running.")
        sys.exit(2)

    log("OpenCode Go proxy listening on http://%s:%d" % (args.host, args.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped")
        sys.exit(0)
