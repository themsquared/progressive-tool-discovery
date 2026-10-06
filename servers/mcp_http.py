"""Minimal MCP-over-streamable-HTTP server, stdlib only.

Implements just enough of the MCP JSON-RPC surface (initialize, tools/list,
tools/call) to demonstrate progressive discovery. It is not a spec-complete
MCP server: no SSE streaming, no session resumption. agentgateway is run in
`statefulMode: stateless` in front of it for exactly that reason -- see the
README. Good enough to prove the token-shape argument; not a library.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(server_name: str, tools_list_fn, call_tool_fn):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            sys.stderr.write("[%s] %s\n" % (server_name, fmt % args))

        def _send_json(self, obj, status=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._send_json(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "parse error"}},
                    status=400,
                )
                return

            method = req.get("method")
            req_id = req.get("id")

            # Notifications (no "id") get a bare 202, no body.
            if req_id is None and method and method.startswith("notifications/"):
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": server_name, "version": "0.1.0"},
                }
            elif method == "tools/list":
                result = {"tools": tools_list_fn()}
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {})
                text = call_tool_fn(name, arguments)
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            else:
                self._send_json({
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                })
                return

            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": result})

        def do_GET(self):
            # Streamable HTTP clients may probe GET for an SSE stream; we
            # don't support server-initiated messages in this demo.
            self._send_json({"status": "ok", "server": server_name})

    return Handler


def serve(port: int, server_name: str, tools_list_fn, call_tool_fn):
    handler = make_handler(server_name, tools_list_fn, call_tool_fn)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    sys.stderr.write(f"[{server_name}] listening on :{port}\n")
    httpd.serve_forever()
