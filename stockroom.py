import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ON_WINDOWS = os.name == "nt"
ENV_DIR = ROOT / (".venv" if ON_WINDOWS else ".venv-linux")
MANAGE = ROOT / "backend" / "manage.py"
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
FRONTEND_INDEX = ROOT / "frontend" / "dist" / "stockroom" / "browser" / "index.html"


def environment_python():
    native = ROOT / ".venv-windows" / "Scripts" / "python.exe"
    if ON_WINDOWS and native.is_file():
        return native
    paths = ("Scripts/python.exe", "bin/python.exe") if ON_WINDOWS else ("bin/python",)
    for path in paths:
        candidate = ENV_DIR / path
        if candidate.is_file():
            return candidate
    return None


def run_command(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def has_pip(python):
    return subprocess.run(
        [python, "-m", "pip", "--version"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Set up or run the local Stockroom demo.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Install dependencies and initialize the database.")
    server = commands.add_parser("run", help="Start Stockroom and its scheduled backup check.")
    server.add_argument("--port", type=int, default=8000, help="Local port (default: 8000).")
    args = parser.parse_args()

    if sys.version_info < (3, 11):
        parser.exit(1, "Stockroom needs Python 3.11 or newer.\n")

    python = environment_python()
    try:
        if args.command == "setup":
            if python is None or not has_pip(python):
                run_command(sys.executable, "-m", "venv", ENV_DIR)
                python = environment_python()
            if python is None:
                parser.exit(1, f"Python was not found in {ENV_DIR}.\n")
            run_command(
                python, "-m", "pip", "--disable-pip-version-check", "install", "-r", REQUIREMENTS
            )
            run_command(python, MANAGE, "migrate", "--noinput")
            run_command(python, MANAGE, "seed")
            run_command(python, MANAGE, "seed_week11", "--catalogue", "--if-demo")
            return 0

        if python is None:
            parser.exit(1, "Run stockroom.py setup first with your system Python.\n")
        if not FRONTEND_INDEX.is_file():
            parser.exit(1, "Frontend build missing. From frontend, run npm ci and npm run build.\n")
        if not 1 <= args.port <= 65535:
            server.error("--port must be between 1 and 65535")

        try:
            run_command(python, MANAGE, "migrate", "--check")
        except subprocess.CalledProcessError:
            parser.exit(1, "Run stockroom.py setup to update the database before starting.\n")

        address = f"127.0.0.1:{args.port}"
        stop_key = "Ctrl+Break" if ON_WINDOWS else "Ctrl+C"
        print(f"Open http://{address}. Press {stop_key} to stop.", flush=True)
        run_command(python, MANAGE, "run_stockroom", address, "--noreload")
    except subprocess.CalledProcessError as error:
        return error.returncode
    except OSError as error:
        parser.exit(1, f"Could not start a required command: {error}\n")
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
