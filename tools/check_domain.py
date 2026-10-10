"""Cheap static enforcement of the pure-domain dependency boundary."""

import ast
from pathlib import Path

FORBIDDEN = {
    "django",
    "rest_framework",
    "httpx",
    "requests",
    "http",
    "urllib",
    "socket",
    "apps",
    "providers",
    "config",
}


def violations(source: str) -> list[str]:
    """Return forbidden static imports, including aliased imports."""
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.split(".")[0] in FORBIDDEN:
                problems.append(f"line {node.lineno}: {name}")
    return problems


def main() -> None:
    """Check every domain source file and fail if framework/I/O imports appear."""
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "backend" / "domain").rglob("*.py"))
    problems = [
        f"{path.relative_to(root)}: {item}"
        for path in paths
        for item in violations(path.read_text(encoding="utf-8"))
    ]
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Domain boundary: {len(paths)} files checked; no forbidden imports.")


if __name__ == "__main__":
    main()
