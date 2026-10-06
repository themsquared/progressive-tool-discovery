"""Synthetic MCP tool catalog shared by both demo servers.

Five business-domain categories, ten tools each: 50 tools total. The
descriptions are deliberately realistic-length (not one-liners) because a
flat tools/list response pays for every word of every description whether
the agent will ever call that tool or not.
"""

CATEGORIES = {
    "billing": "Invoices, charges, credits, and payment methods for customer accounts.",
    "inventory": "Stock levels, warehouse locations, and reorder thresholds for SKUs.",
    "support": "Support tickets, customer conversations, and escalation routing.",
    "devops": "Deploys, feature flags, service health, and rollback operations.",
    "analytics": "Usage metrics, cohort reports, and funnel conversion queries.",
}

_ACTION_VERBS = [
    "get", "list", "create", "update", "delete",
    "search", "export", "archive", "restore", "summarize",
]

_NOUNS = {
    "billing": "invoice",
    "inventory": "sku",
    "support": "ticket",
    "devops": "deployment",
    "analytics": "report",
}


def _description(category: str, verb: str, noun: str) -> str:
    return (
        f"{verb.capitalize()} a {noun} record in the {category} domain. "
        f"Returns the {noun}'s current state and the fields a caller in "
        f"the {category} system would expect to see."
    )


def build_tool(category: str, verb: str) -> dict:
    noun = _NOUNS[category]
    name = f"{category}_{verb}_{noun}"
    return {
        "name": name,
        "description": _description(category, verb, noun),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": f"The {noun} identifier."},
            },
            "required": [] if verb in ("list", "create", "export", "summarize") else ["id"],
        },
    }


def all_tools() -> list:
    """Every tool in every category, flattened -- what a flat MCP server exposes."""
    tools = []
    for category in CATEGORIES:
        for verb in _ACTION_VERBS:
            tools.append(build_tool(category, verb))
    return tools


def tools_for_category(category: str) -> list:
    if category not in CATEGORIES:
        return []
    return [build_tool(category, verb) for verb in _ACTION_VERBS]


def category_summary() -> list:
    return [
        {
            "name": name,
            "description": desc,
            "tool_count": len(_ACTION_VERBS),
        }
        for name, desc in CATEGORIES.items()
    ]


def find_tool(name: str) -> dict | None:
    for t in all_tools():
        if t["name"] == name:
            return t
    return None


def call_result(name: str, arguments: dict) -> str:
    tool = find_tool(name)
    if tool is None:
        return f"error: no such tool '{name}'"
    return f"ok: called {name} with arguments={arguments!r} (canned demo response, no real backend)"
