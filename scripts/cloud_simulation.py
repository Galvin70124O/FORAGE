"""Simulate a Streamlit Community Cloud deployment from what is committed to git.

1. export the committed files (git archive HEAD) into a fresh temporary folder: no untracked files, no data/real/, no secrets;
2. create a fresh virtual environment and install ONLY requirements.txt;
3. optionally copy a secrets file into the clone (never printed); if it has [connections.sql], run
   scripts/init_db.py and scripts/check_database.py against that database first;
4. start the app, wait for it to be healthy, crawl every page x source x theme (scripts/crawl_pages.py,
   using this machine's Playwright) and exercise a purchase and a pantry check;
5. scan the server log for tracebacks, errors and warnings.

Usage (from the project root, after committing):
    python scripts/cloud_simulation.py                                   # (a) no secrets: demo mode
    python scripts/cloud_simulation.py --secrets .streamlit/secrets.toml # (b) with your database / sign-in

Exit code 0 only if every step passed.
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENIGN = [re.compile(p) for p in (r"ConnectionResetError", r"WinError 10054", r"missing ScriptRunContext")]


def log_issues(lines: list[str]) -> list[str]:
    """Warning/error lines, judging each traceback by its final exception line.

    Windows' asyncio prints a ConnectionResetError traceback when a browser tab closes; that is
    client-side noise (it does not happen on Linux hosts such as Streamlit Cloud) and is ignored.
    """
    issues, block = [], []
    for line in lines + [""]:
        if block:
            block.append(line)
            if line and not line.startswith((" ", "	")) and not line.startswith("Traceback"):
                if not any(p.search(line) for p in BENIGN):
                    issues.append(" / ".join(block[-2:]))
                block = []
            continue
        if line.startswith("Traceback"):
            block = [line]
        elif line.startswith("Exception in callback") or line.startswith("handle: <Handle"):
            continue
        elif re.search(r"ERROR|Error|WARNING|Warning", line) and not any(p.search(line) for p in BENIGN):
            issues.append(line)
    return issues


def run(command, cwd, env=None, label=""):
    print(f"--> {label or ' '.join(map(str, command))}")
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        print(result.stdout[-3000:], result.stderr[-3000:])
        sys.exit(f"step failed: {label}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", type=Path, help="secrets.toml to copy into the clone (contents never printed)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--modes", nargs="+", default=["light", "dark"])
    parser.add_argument("--keep", action="store_true", help="keep the temporary clone for inspection")
    parser.add_argument("--no-exercise", action="store_true", help="skip logging a purchase (e.g. sign-in required)")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="forage-cloud-"))
    clone = workdir / "app"
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:  # exactly the committed files at HEAD
        tar.extractall(clone, filter="data")
    print("--> exported committed files (git archive HEAD)")
    untracked = [p for p in ("data/real", "dataset", "data/my_food_data.csv", ".streamlit/secrets.toml")
                 if (clone / p).exists()]
    if untracked:
        sys.exit(f"clone unexpectedly contains: {untracked}")
    venv = workdir / "venv"
    run([sys.executable, "-m", "venv", str(venv)], cwd=workdir, label="fresh virtual environment")
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-m", "pip", "install", "--quiet", "-r", "requirements.txt"], cwd=clone,
        label="pip install -r requirements.txt (only)")
    mode = "no secrets (demo mode)"
    if args.secrets:
        (clone / ".streamlit").mkdir(exist_ok=True)
        shutil.copy(args.secrets, clone / ".streamlit" / "secrets.toml")
        config = tomllib.loads(args.secrets.read_text(encoding="utf-8"))
        has_db = "sql" in config.get("connections", {})
        mode = f"secrets: auth={'auth' in config}, database={has_db}"
        if has_db:
            run([str(python), "scripts/init_db.py"], cwd=clone, label="init_db.py against the configured database")
            print(run([str(python), "scripts/check_database.py"], cwd=clone,
                      label="check_database.py (isolation smoke test)").stdout.strip())
    print(f"mode: {mode}")

    log_path = workdir / "server.log"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with open(log_path, "w", encoding="utf-8") as log:
        server = subprocess.Popen([str(python), "-m", "streamlit", "run", "app.py", "--server.port", str(args.port),
                                   "--server.headless", "true"], cwd=clone, stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        for _ in range(120):
            try:
                if urllib.request.urlopen(f"http://localhost:{args.port}/_stcore/health", timeout=2).status == 200:
                    break
            except Exception:
                time.sleep(1)
        else:
            sys.exit("app did not become healthy")
        print("--> app healthy; crawling")
        crawl = subprocess.run([sys.executable, str(ROOT / "scripts" / "crawl_pages.py"), "--url",
                                f"http://localhost:{args.port}", "--out", str(workdir / "shots"), "--modes",
                                *args.modes, *([] if args.no_exercise else ["--exercise"])], cwd=clone, env=env)
    finally:
        server.terminate()
        server.wait(timeout=30)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    issues = log_issues(lines)
    print(f"server log: {len(lines)} lines, {len(issues)} warning/error lines")
    for line in issues[:20]:
        print("    " + line)
    print(f"artifacts: {workdir}" if args.keep else "")
    if not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    sys.exit(0 if crawl.returncode == 0 and not issues else 1)


if __name__ == "__main__":
    main()
