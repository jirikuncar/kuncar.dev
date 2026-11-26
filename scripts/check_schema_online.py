"""Validate the structured data of HTML pages with https://validator.schema.org/.

Sends each page to the validator. Without network the check is skipped, not failed.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://validator.schema.org/validate"


def validate(html: str) -> dict:
    body = urllib.parse.urlencode({"html": html}).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=body), timeout=20) as response:
        return json.loads(response.read().decode().removeprefix(")]}'"))


def errors(node: object) -> list[dict]:
    if isinstance(node, list):
        return [e for item in node for e in errors(item)]
    if not isinstance(node, dict):
        return []
    return list(node.get("errors", [])) + [e for k, v in node.items() if k != "errors" for e in errors(v)]


def main(paths: list[str]) -> int:
    failed = False
    for path in paths:
        try:
            result = validate(Path(path).read_text())
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"{path}: skipped, {URL} unreachable: {e}")
            continue
        seen = set()
        for e in errors(result):
            key = (e["errorType"], tuple(e.get("args", [])))
            if key in seen:
                continue
            seen.add(key)
            severity = "error" if e.get("isSevere") else "warning"
            print(f"{path}: {severity} {e['errorType']} {e.get('args', [])} at offset {e.get('begin')}")
            failed |= e.get("isSevere", False)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
