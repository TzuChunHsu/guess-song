"""A small stand-in for the Firebase Realtime Database REST API, for tests.

Supports GET / PUT / PATCH (multi-path keys) / DELETE on /<path>.json, {".sv": "timestamp"},
server-sent-event streaming (put / patch / keep-alive / cancel), CORS, the same security rules
as the real database (rooms/<4 chars> readable and writable, board write-once), and serves the
game's static files from a folder so the page and the database share one origin.

    python3 fake_firebase.py <static-dir> [port]
"""
import json, os, queue, re, sys, threading, time, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

TREE = {}
LOCK = threading.RLock()
LISTENERS = []                     # (path parts, queue)
LOG = []                           # (method, path) for tests
DELAY = {"ms": 0}                  # artificial latency for writes
NO_STREAM = {"on": False}          # pretend event streams are blocked on this network
ROOM = re.compile(r"^[A-Z2-9]{4}$")


def parts(path):
    return [p for p in path.strip("/").split("/") if p]


def get_at(parts_):
    node = TREE
    for p in parts_:
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node


def resolve(v):
    if isinstance(v, dict):
        if v == {".sv": "timestamp"}:
            return int(time.time() * 1000)
        return {k: resolve(x) for k, x in v.items() if x is not None}
    if isinstance(v, list):
        return {str(i): resolve(x) for i, x in enumerate(v) if x is not None}
    return v


def prune(v):
    if isinstance(v, dict):
        out = {k: prune(x) for k, x in v.items()}
        out = {k: x for k, x in out.items() if x is not None and x != {}}
        return out or None
    return v


def set_at(parts_, value):
    global TREE
    if not parts_:
        TREE = prune(value) or {}
        return
    node = TREE
    for p in parts_[:-1]:
        if not isinstance(node.get(p), dict):
            node[p] = {}
        node = node[p]
    value = prune(value)
    if value is None:
        node.pop(parts_[-1], None)
    else:
        node[parts_[-1]] = value
    TREE = prune(TREE) or {}


def out(v):
    """Firebase hands objects with keys 0..n back as arrays."""
    if isinstance(v, dict):
        keys = list(v.keys())
        if keys and all(k.isdigit() for k in keys):
            n = max(int(k) for k in keys)
            if len(keys) * 2 > n:
                return [out(v.get(str(i))) for i in range(n + 1)]
        return {k: out(x) for k, x in v.items()}
    return v


def can_read(p):
    return (len(p) >= 2 and p[0] == "rooms" and bool(ROOM.match(p[1]))) or (len(p) >= 1 and p[0] == "board")


def can_write(p, value):
    if len(p) >= 2 and p[0] == "rooms" and ROOM.match(p[1]):
        return True
    if len(p) == 2 and p[0] == "board":
        if get_at(p) is not None:
            return False
        v = value if isinstance(value, dict) else {}
        return isinstance(v.get("n"), str) and len(v["n"]) <= 20 and isinstance(v.get("s"), (int, float)) and "ts" in v
    return False


def notify(write_parts, patch_obj=None):
    for lp, q in list(LISTENERS):
        if write_parts[:len(lp)] == lp:                     # the write is at or below the listener
            rel = "/" + "/".join(write_parts[len(lp):])
            if patch_obj is not None:
                q.put(("patch", {"path": rel, "data": out(patch_obj)}))
            else:
                q.put(("put", {"path": rel, "data": out(get_at(write_parts))}))
        elif lp[:len(write_parts)] == write_parts:          # the write replaced something above the listener
            q.put(("put", {"path": "/", "data": out(get_at(lp))}))


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    static = "."

    def log_message(self, *a):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, PATCH, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def reply(self, code, obj, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def dbpath(self):
        u = urllib.parse.urlparse(self.path)
        if not u.path.endswith(".json"):
            return None, None
        return parts(urllib.parse.unquote(u.path[:-5])), urllib.parse.parse_qs(u.query)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        p, qs = self.dbpath()
        if p is None:
            f = os.path.join(self.static, urllib.parse.urlparse(self.path).path.lstrip("/") or "index.html")
            if os.path.isfile(f):
                ctype = "text/html; charset=utf-8" if f.endswith(".html") else "application/octet-stream"
                return self.reply(200, open(f, "rb").read(), ctype)
            return self.reply(404, {"error": "not found"})
        LOG.append(("GET", "/".join(p)))
        if "text/event-stream" in (self.headers.get("Accept") or ""):
            if NO_STREAM["on"]:
                return self.reply(503, {"error": "streams blocked"})
            return self.stream(p)
        if not can_read(p):
            return self.reply(401, {"error": "Permission denied"})
        with LOCK:
            v = get_at(p)
            if qs.get("orderBy") == ['"$key"'] and isinstance(v, dict):
                lo = json.loads(qs.get("startAt", ['""'])[0]); hi = json.loads(qs.get("endAt", ['""'])[0])
                v = {k: x for k, x in v.items() if lo <= k <= hi}
            return self.reply(200, out(v))

    def stream(self, p):
        self.send_response(200)
        self.cors()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        q = queue.Queue()

        def send(ev, data):
            self.wfile.write(f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

        try:
            if not can_read(p):
                send("cancel", None)
                return
            with LOCK:
                LISTENERS.append((p, q))
                send("put", {"path": "/", "data": out(get_at(p))})
            while True:
                try:
                    ev, data = q.get(timeout=10)
                except queue.Empty:
                    ev, data = "keep-alive", None
                if ev == "close":
                    return
                send(ev, data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with LOCK:
                LISTENERS[:] = [x for x in LISTENERS if x[1] is not q]
            self.close_connection = True

    def write(self, method):
        p, _ = self.dbpath()
        if p is None:
            return self.reply(404, {"error": "not found"})
        if DELAY["ms"]:
            time.sleep(DELAY["ms"] / 1000)
        LOG.append((method, "/".join(p)))
        val = None if method == "DELETE" else self.body()
        with LOCK:
            if method == "PATCH":
                if not isinstance(val, dict):
                    return self.reply(400, {"error": "Invalid data"})
                keys = list(val.keys())
                for a in keys:
                    for b in keys:
                        if a != b and (b + "/").startswith(a.rstrip("/") + "/"):
                            return self.reply(400, {"error": "Invalid data; path overlap"})
                res = {}
                for k, v in val.items():
                    sub = p + parts(k)
                    if not can_write(sub, v):
                        return self.reply(401, {"error": "Permission denied"})
                for k, v in val.items():
                    rv = resolve(v)
                    set_at(p + parts(k), rv)
                    res[k] = rv
                notify(p, res)
                return self.reply(200, out(res))
            if not can_write(p, val):
                return self.reply(401, {"error": "Permission denied"})
            rv = resolve(val)
            set_at(p, rv)
            notify(p)
            return self.reply(200, out(rv))

    def do_PUT(self):
        self.write("PUT")

    def do_PATCH(self):
        self.write("PATCH")

    def do_DELETE(self):
        self.write("DELETE")


def start(static, port=0):
    H.static = static
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def drop_streams():
    """Simulate a network blip: every open stream is closed."""
    with LOCK:
        for _, q in LISTENERS:
            q.put(("close", None))


if __name__ == "__main__":
    s = start(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8765)
    print("listening on", s.server_address)
    threading.Event().wait()
