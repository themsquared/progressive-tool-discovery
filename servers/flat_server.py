#!/usr/bin/env python3
"""The flat catalog: every tool, every time. This is the baseline."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import catalog_data
import mcp_http


def tools_list():
    return catalog_data.all_tools()


def call_tool(name, arguments):
    return catalog_data.call_result(name, arguments)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3005"))
    mcp_http.serve(port, "flat-catalog", tools_list, call_tool)
