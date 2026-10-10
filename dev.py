"""One project-local entry point; subprocess argument lists preserve spaced paths."""

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def execute(arguments: Sequence[str], cwd: Path = ROOT) -> None:
    """Run a command without shell interpolation and propagate failures."""
    print("> " + subprocess.list2cmdline(list(arguments)), flush=True)
    subprocess.run(list(arguments), cwd=cwd, check=True)


def python_command(*arguments: str) -> list[str]:
    """Use the explicit project venv, never an activation script."""
    if not PYTHON.is_file():
        raise SystemExit('Run python "./dev.py" setup first.')
    return [str(PYTHON), *arguments]


def npm_command(*arguments: str) -> list[str]:
    """Resolve npm without assuming its install path has no spaces."""
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not executable:
        raise SystemExit("Node.js/npm must already be available; nothing is installed globally.")
    return [executable, *arguments]


def setup() -> None:
    """Install locked dependencies and caches exclusively inside the project."""
    if sys.version_info < (3, 12):  # noqa: UP036 - bootstrap may use an older interpreter.
        raise SystemExit("Python 3.12+ is required.")
    if not PYTHON.is_file():
        execute([sys.executable, "-m", "venv", str(BACKEND / ".venv")])
    requirements = BACKEND / "requirements.lock"
    if not requirements.is_file():
        requirements = BACKEND / "requirements.in"
    execute(
        python_command(
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--cache-dir",
            str(BACKEND / ".cache" / "pip"),
            "-r",
            str(requirements),
        )
    )
    install = "ci" if (FRONTEND / "package-lock.json").is_file() else "install"
    execute(
        npm_command(install, "--cache", str(FRONTEND / ".cache" / "npm"), "--no-audit"), FRONTEND
    )
    (BACKEND / "staticfiles").mkdir(exist_ok=True)


def forward_output(stream: TextIO, label: str) -> None:
    """Forward child output even when Windows starts a hidden process."""
    for line in stream:
        print(f"[{label}] {line}", end="", flush=True)


def run_servers() -> None:
    """Run both servers; stop only these child processes on exit."""
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js is required.")
    commands = [
        (python_command("manage.py", "runserver", "127.0.0.1:8000", "--noreload"), BACKEND),
        ([node, str(FRONTEND / "node_modules" / "vite" / "bin" / "vite.js")], FRONTEND),
    ]
    processes: list[subprocess.Popen[str]] = []
    try:
        for command, directory in commands:
            environment = dict(os.environ, PYTHONUNBUFFERED="1")
            if directory == FRONTEND:
                for key in ("SECRET_KEY", "TOMTOM_API_KEY"):
                    environment.pop(key, None)
            process = subprocess.Popen(
                command,
                cwd=directory,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append(process)
            assert process.stdout is not None
            threading.Thread(
                target=forward_output, args=(process.stdout, directory.name), daemon=True
            ).start()
        print("Frontend http://127.0.0.1:5173 | Backend http://127.0.0.1:8000", flush=True)
        print("Press Ctrl+C to stop both servers.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        raise SystemExit("A dev server exited; see its output above.")
    except KeyboardInterrupt:
        print("Stopping project dev servers.", flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def backend_check(command: str) -> None:
    """Run the named backend pipeline with a fixed working directory."""
    config = str(BACKEND / "pyproject.toml")
    paths = [str(BACKEND), str(ROOT / "dev.py"), str(ROOT / "tools")]
    if command == "test":
        execute(python_command("-m", "pytest"), BACKEND)
    elif command in {"lint", "format"}:
        if command == "lint":
            execute(python_command("-m", "ruff", "check", "--config", config, *paths))
            execute(python_command("-m", "ruff", "format", "--check", "--config", config, *paths))
            execute(python_command(str(ROOT / "tools" / "check_domain.py")))
        else:
            execute(python_command("-m", "ruff", "check", "--fix", "--config", config, *paths))
            execute(python_command("-m", "ruff", "format", "--config", config, *paths))
    elif command == "typecheck":
        execute(
            python_command(
                "-m",
                "mypy",
                "--config-file",
                config,
                "config",
                "apps",
                "domain",
                "providers",
                "tests",
                str(ROOT / "dev.py"),
                str(ROOT / "tools"),
            ),
            BACKEND,
        )
    elif command == "build":
        execute(python_command("manage.py", "check"), BACKEND)
        (BACKEND / "staticfiles").mkdir(exist_ok=True)
        execute(python_command("manage.py", "collectstatic", "--noinput"), BACKEND)
        execute(
            python_command("-m", "compileall", "-q", "config", "apps", "domain", "providers"),
            BACKEND,
        )


def browser_command(install: bool) -> None:
    """Keep browser downloads and execution inside the approved project setup."""
    environment = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(ROOT / ".cache" / "ms-playwright"))
    command = (
        npm_command("exec", "--", "playwright", "install", "chromium")
        if install
        else (npm_command("run", "e2e"))
    )
    subprocess.run(command, cwd=FRONTEND, env=environment, check=True)


def main() -> None:
    """Dispatch setup, run, checks and optional browser/audit commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "setup",
            "run",
            "test",
            "lint",
            "format",
            "typecheck",
            "build",
            "browser-install",
            "e2e",
            "audit",
            "ci-check",
        ],
    )
    parser.add_argument("--only", choices=["all", "backend", "frontend"], default="all")
    args = parser.parse_args()
    if args.command == "setup":
        setup()
    elif args.command == "run":
        run_servers()
    elif args.command in {"browser-install", "e2e"}:
        browser_command(args.command == "browser-install")
    elif args.command == "audit":
        failures = []
        for command, directory in [
            (python_command(str(ROOT / "tools" / "audit_python.py")), ROOT),
            (npm_command("audit"), FRONTEND),
        ]:
            try:
                execute(command, directory)
            except subprocess.CalledProcessError as error:
                failures.append(error.returncode)
        if failures:
            raise SystemExit(max(failures))
    elif args.command == "ci-check":
        execute([shutil.which("node") or "node", str(ROOT / "tools" / "check_ci.mjs")])
    else:
        if args.only in {"all", "backend"}:
            backend_check(args.command)
        if args.only in {"all", "frontend"}:
            execute(npm_command("run", args.command), FRONTEND)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
