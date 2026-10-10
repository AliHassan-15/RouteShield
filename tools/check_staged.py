"""Review the Git index without printing any potential secret content."""

import re
import subprocess


def git(*arguments: str) -> bytes:
    """Read local Git state only."""
    return subprocess.check_output(["git", *arguments])


def main() -> None:
    """Fail if forbidden artifacts, ignored files or recognizable secrets are staged."""
    paths = [
        path for path in git("diff", "--cached", "--name-only", "-z").decode().split("\0") if path
    ]
    if not paths:
        raise SystemExit("No staged files to review; stage the authorized change first.")
    problems: list[str] = []
    ignored = git("ls-files", "--cached", "--ignored", "--exclude-standard", "-z").decode()
    if ignored.strip("\0"):
        problems.append("Ignored artifacts are staged.")
    secret_patterns = [
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    ]
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        if (name.startswith(".env") and name != ".env.example") or path.lower().endswith(".pdf"):
            problems.append(f"Forbidden file: {path}")
            continue
        content = git("show", ":" + path)
        if any(pattern.search(content) for pattern in secret_patterns):
            problems.append(f"Possible secret in {path} (value withheld).")
        if name == ".env.example":
            for line in content.decode().splitlines():
                key, separator, value = line.partition("=")
                if separator and key in {"SECRET_KEY", "TOMTOM_API_KEY"} and value.strip():
                    problems.append(f"Nonempty secret example in {path}.")
    if problems:
        raise SystemExit("\n".join(problems))
    print(
        f"Staged review: {len(paths)} files; no PDF, real .env, ignored artifacts or "
        "recognized secret patterns."
    )
    print("Pattern scanning complements the staged-file review; it is not a guarantee.")


if __name__ == "__main__":
    main()
