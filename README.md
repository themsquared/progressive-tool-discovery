# progressive-tool-discovery

A small, fixed MCP entry point that reveals the rest of a tool catalog on
demand, fronted by [agentgateway](https://github.com/agentgateway/agentgateway)
v1.6.0, measured against a flat catalog exposing the same 50 tools.

## The problem

MCP's `tools/list` response is model context. Every tool definition it
returns, every word of every description, is tokens the model reads before it
does any work. A server with 50 tools sends all 50 definitions on every
connection whether the agent needs one of them or none of them. The
[2026-08-22 MCP roadmap](https://modelcontextprotocol.io/development/roadmap)
names this directly as a priority: servers should "offer a small entry point
and reveal more of the catalog" instead of front-loading everything.

Cloudflare's "Code Mode" is the framing most people have heard for this
problem, but Code Mode solves a different problem: it turns N tools into one
script-executor tool, so the model writes code instead of reading N
definitions. That cuts tokens too, but the mechanism is composition, not
discovery. **Progressive (hierarchical) discovery** is the other idea: keep
the entry point small, and let the agent ask for more of the catalog only
when it needs it. This repo builds that mechanism and nothing else.

## What's native and what's hand-rolled

agentgateway (OSS) ships a real primitive for progressive disclosure, but
it's gated. In [Solo Enterprise's agentgateway build](https://docs.solo.io/agentgateway/latest/mcp/tool-mode/),
an `EnterpriseAgentgatewayBackend` can set `entMcp.toolMode: Search`, which
replaces a backend's tool list with two meta-tools (`get_tool` /
`invoke_tool`) and discloses one tool definition at a time. That is exactly
the pattern this repo demonstrates. It is not in the open-source agentgateway
binary this repo runs: the field name (`entMcp`) and the resource name
(`EnterpriseAgentgatewayBackend`) are both Enterprise-only, and the OSS docs'
[MCP connectivity](https://agentgateway.dev/docs/standalone/latest/documentation/mcp/)
section has no tool-mode page at all.

What OSS agentgateway v1.6.0 *does* have is [MCP multiplexing and separate-path
routing](https://agentgateway.dev/docs/standalone/latest/documentation/mcp/configuration-modes/):
federate several upstream MCP servers behind one backend, or give each its own
route. Multiplexing flattens tool catalogs together (with name prefixing to
avoid collisions) — it's the opposite direction from what this repo needs, so
this demo uses separate-path routing instead, one path per catalog shape.

So the entry-point/expand-on-demand mechanism itself — `list_categories`,
`expand_category`, `call_tool` — is hand-rolled in about 130 lines of Python
(`servers/progressive_server.py` + `servers/catalog_data.py`), not an
agentgateway feature. agentgateway's job in this demo is what it's good at
regardless of license tier: routing, a stable client-facing endpoint, and
(in a real deployment) the auth, rate limiting, and observability policies
that would sit in front of either catalog shape the same way.

I checked [agentregistry v0.4.0](https://github.com/agentregistry-dev/agentregistry)
too, since it's the other half of this campaign's registry work. It's a
catalog of *which MCP servers exist* (npm/PyPI/OCI packages, versioned,
curated, deployable with `arctl`) — a different layer of discovery than *which
tools one running server exposes*. Its API has no pagination or hierarchy
primitive for a single server's tool list, because that was never its job.
It's a good fit for finding the progressive-catalog server in the first
place; it has nothing to do with how that server shapes its own `tools/list`.
I'm not forcing it into the architecture below.

## Architecture

```
                      agentgateway v1.6.0 (:3900 -> :3000)
                     /                                    \
            route: /flat                           route: /progressive
                     |                                      |
            flat-server (:3005)                 progressive-server (:3006)
            tools/list -> all 50 tools           tools/list -> 3 entry-point tools:
            (10 per category x 5 categories)       list_categories
                                                    expand_category(category)
                                                    call_tool(name, arguments)
```

Both servers share one synthetic catalog (`servers/catalog_data.py`): 5
business-domain categories (billing, inventory, support, devops, analytics),
10 tools each, with realistic-length descriptions and JSON schemas. Only the
*shape* of what's exposed differs:

- **`flat-server`** returns every one of the 50 tool definitions from
  `tools/list`, every time, matching how most MCP servers behave today.
- **`progressive-server`** returns exactly 3 tools from `tools/list`,
  regardless of how many categories or tools live behind it. `list_categories`
  gives the agent a map of what exists. `expand_category` reveals one
  category's full tool definitions, on demand. `call_tool` dispatches to the
  underlying tool once the agent knows its name and schema.

Both are plain Python stdlib HTTP servers speaking enough of MCP's
Streamable HTTP transport (`servers/mcp_http.py`) for this demo:
`initialize`, `tools/list`, `tools/call`. No MCP SDK dependency, so there's
no SDK version pin to fight (the [Virtual MCP
docs](https://agentgateway.dev/docs/standalone/latest/integrations/mcp/servers/virtual/)
call out exactly this kind of breakage with `mcp-server-time` and `uvx`). It
is not a spec-complete MCP server: no SSE push, no session resumption. That's
why `config.yaml` runs agentgateway with `statefulMode: stateless` in front
of both.

`config.yaml` uses agentgateway's routing-based configuration mode: one
gateway on port 3000, two routes (`/flat`, `/progressive`), each its own MCP
backend with a single target. Real agentgateway v1.6.0, unmodified, no custom
plugin.

## Quickstart

Requires Docker with Compose v2+. Validated on Docker 29.8.1 / Compose
v5.5.1, arm64 macOS, against `ghcr.io/agentgateway/agentgateway:v1.6.0`.

```bash
git clone https://github.com/themsquared/progressive-tool-discovery
cd progressive-tool-discovery
./demo.sh
```

`demo.sh` builds the two Python servers, starts agentgateway, waits for
readiness, runs `measure.py` (which hits the real `/flat` and `/progressive`
routes over HTTP and prints byte counts captured from that run), then tears
everything down. One run, end to end, well under 15 minutes including the
image pulls.

Real output from a run of this repo:

```
agentgateway v1.6.0, two routes, same 50-tool catalog, two shapes.

                      tools/list bytes   tools exposed
flat                             16358              50
progressive                        922               3

tools/list reduction: 94.4% fewer bytes, 47 fewer tools in the initial exposure.

Scenario: the agent only ever needs the billing category (10 of 50 tools).

  flat tools/list alone:                        16358 bytes, 50 tools seen
  progressive tools/list:                         922 bytes, 3 tools seen
  + list_categories call:                         781 bytes
  + expand_category('billing') call:             3818 bytes, 10 tools revealed
  progressive total for this scenario:            5521 bytes

  net bytes saved vs. the flat catalog: 66.2%
```

These are **bytes on the wire**, not model tokens — a tokenizer would count
differently, but the two scale together since both payloads are the same
JSON shape with the same kind of content (tool names, descriptions, JSON
schemas). The point that survives any tokenizer: the entry point stays fixed
at 3 tools and ~900 bytes no matter how large the catalog behind it grows,
while the flat catalog's `tools/list` grows linearly with every tool you add.

To run the pieces by hand instead of via `demo.sh`:

```bash
docker compose up -d --build
python3 measure.py
docker compose down
```

## What this does not show

- This is not a benchmark of model tool-selection accuracy (that's
  [Anthropic's internal MCP eval numbers](https://www.anthropic.com/engineering/advanced-tool-use),
  cited and discussed in [Conway's Law Is Coming for Your MCP
  Servers](https://webofmike.com/conways-law-mcp-servers/)). This repo
  measures the catalog payload shape, not whether a model calls the right
  tool more often because of it.
- `expand_category` and `call_tool` here are unauthenticated and return
  canned responses. A real deployment would put MCP authorization
  ([agentgateway JWT + CEL policy](https://agentgateway.dev/docs/standalone/latest/documentation/mcp/mcp-authz/))
  in front of which categories a given caller can even list.
- 50 tools is a demo-sized catalog. The byte gap between flat and progressive
  grows, not shrinks, as the real catalog gets bigger, since the progressive
  entry point never changes size.

## License

Apache-2.0. See [LICENSE](LICENSE).

Topics: `mcp`, `agentgateway`, `ai-agents`, `tool-discovery`, `platform-engineering`
