#!/usr/bin/env python3
"""Measure the real byte cost of a flat tools/list vs. progressive discovery,
through the actual agentgateway v1.6.0 proxy. Stdlib only.

Every number this script prints comes from an HTTP response captured in the
same run -- nothing here is estimated or hand-typed.
"""

import json
import re
import sys
import urllib.request

GATEWAY = "http://localhost:3900"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def rpc(path: str, method: str, params: dict | None = None, req_id: int = 1) -> tuple[bytes, dict]:
    body = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        body["params"] = params
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{GATEWAY}{path}", data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
    # agentgateway replies as an SSE frame ("event: message\ndata: {...}");
    # pull the JSON payload out of the data: line but keep `raw` (the full
    # wire response) as the byte count that matters -- that's what the
    # agent's HTTP client actually received.
    m = re.search(rb"^data: (.*)$", raw, re.M)
    payload = json.loads(m.group(1)) if m else json.loads(raw)
    return raw, payload


def tool_count(payload: dict) -> int:
    return len(payload.get("result", {}).get("tools", []))


def call_bytes(raw: bytes) -> int:
    return len(raw)


def main() -> int:
    print("agentgateway v1.6.0, two routes, same 50-tool catalog, two shapes.\n")

    flat_raw, flat_payload = rpc("/flat", "tools/list", req_id=1)
    prog_raw, prog_payload = rpc("/progressive", "tools/list", req_id=1)

    flat_tools = tool_count(flat_payload)
    prog_tools = tool_count(prog_payload)
    flat_bytes = call_bytes(flat_raw)
    prog_bytes = call_bytes(prog_raw)

    print(f"{'':20}{'tools/list bytes':>18}{'tools exposed':>16}")
    print(f"{'flat':20}{flat_bytes:>18}{flat_tools:>16}")
    print(f"{'progressive':20}{prog_bytes:>18}{prog_tools:>16}")
    reduction = 100 * (1 - prog_bytes / flat_bytes)
    print(f"\ntools/list reduction: {reduction:.1f}% fewer bytes, "
          f"{flat_tools - prog_tools} fewer tools in the initial exposure.\n")

    # Now walk the progressive path an agent would actually take: it needs
    # exactly one category (billing), never sees the other 40 tools.
    list_cat_raw, _ = rpc("/progressive", "tools/call",
                          {"name": "list_categories", "arguments": {}}, req_id=2)
    expand_raw, expand_payload = rpc("/progressive", "tools/call",
                                      {"name": "expand_category", "arguments": {"category": "billing"}},
                                      req_id=3)
    revealed = json.loads(expand_payload["result"]["content"][0]["text"])

    progressive_total = prog_bytes + len(list_cat_raw) + len(expand_raw)

    print("Scenario: the agent only ever needs the billing category (10 of 50 tools).\n")
    print(f"  flat tools/list alone:                     {flat_bytes:>8} bytes, {flat_tools} tools seen")
    print(f"  progressive tools/list:                    {prog_bytes:>8} bytes, {prog_tools} tools seen")
    print(f"  + list_categories call:                    {len(list_cat_raw):>8} bytes")
    print(f"  + expand_category('billing') call:         {len(expand_raw):>8} bytes, {len(revealed)} tools revealed")
    print(f"  progressive total for this scenario:        {progressive_total:>8} bytes")
    scenario_reduction = 100 * (1 - progressive_total / flat_bytes)
    print(f"\n  net bytes saved vs. the flat catalog: {scenario_reduction:.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
