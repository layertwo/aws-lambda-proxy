"""Regex patterns for path parsing and route matching."""

import re

# Pattern matching expressions
params_expr = re.compile(r"(<[^>]*>)")
proxy_pattern = re.compile(r"/{(?P<name>.+)\+}$")
param_pattern = re.compile(
    r"^<((?P<type>[a-zA-Z0-9_]+)(\((?P<pattern>.+)\))?\:)?(?P<name>[a-zA-Z0-9_]+)>$"
)
regex_pattern = re.compile(
    r"^<(?P<type>regex)\((?P<pattern>.+)\):(?P<name>[a-zA-Z0-9_]+)>$"
)
