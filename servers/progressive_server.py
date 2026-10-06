#!/usr/bin/env python3
"""The progressive catalog: a small, fixed entry point that reveals more of
the catalog on demand. tools/list never grows, no matter how many tools or
categories live behind it -- that's the whole mechanism.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import catalog_data
import mcp_http

ENTRY_POINT_TOOLS = [
    {
        "name": "list_categories",
        "description": (
            "List the tool categories available in this catalog, with a tool "
            "count per category. Call this first before looking for a specific "
            "tool."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "expand_category",
        "description": (
            "List the tools available within one category, with full "
            "descriptions and input schemas. Call list_categories first to see "
            "valid category names."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "A category name from list_categories."},
            },
            "required": ["category"],
        },
    },
    {
        "name": "call_tool",
        "description": (
            "Invoke a specific tool by name with arguments. Call expand_category "
            "first to see the tool's exact name and expected arguments."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "arguments": {"type": "object"},
            },
            "required": ["name"],
        },
    },
]


def tools_list():
    return ENTRY_POINT_TOOLS


def call_tool(name, arguments):
    if name == "list_categories":
        return json.dumps(catalog_data.category_summary())
    if name == "expand_category":
        category = arguments.get("category", "")
        tools = catalog_data.tools_for_category(category)
        if not tools:
            return f"error: unknown category '{category}'"
        return json.dumps(tools)
    if name == "call_tool":
        target = arguments.get("name", "")
        target_args = arguments.get("arguments", {})
        return catalog_data.call_result(target, target_args)
    return f"error: no such entry-point tool '{name}'"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3006"))
    mcp_http.serve(port, "progressive-catalog", tools_list, call_tool)
