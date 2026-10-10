"""Audit installed pinned PyPI versions against OSV without adding an audit dependency."""

import importlib.metadata
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    """Query all installed distributions and preserve the exact audit response."""
    root = Path(__file__).resolve().parents[1]
    packages = sorted(
        ((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions()),
        key=lambda item: item[0].lower(),
    )
    payload = {
        "queries": [
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
            for name, version in packages
        ]
    }
    request = Request(
        "https://api.osv.dev/v1/querybatch",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except Exception as error:
        print(f"Python audit unavailable: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(2) from error
    if len(result.get("results", [])) != len(packages):
        raise SystemExit("Python audit returned incomplete results.")
    findings = [
        {"name": name, "version": version, "advisories": row.get("vulns", [])}
        for (name, version), row in zip(packages, result["results"], strict=True)
        if row.get("vulns")
    ]
    output = root / ".cache" / "python-audit.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps({"packages": packages, "response": result}, indent=2), encoding="utf-8"
    )
    print(f"OSV PyPI audit: {len(packages)} packages, {len(findings)} affected packages.")
    for finding in findings:
        print(json.dumps(finding))
    print("This checks published OSV advisories, not the absence of all vulnerabilities.")
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
