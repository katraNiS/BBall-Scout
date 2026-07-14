"""
Production entry point για τον backend — καθαρός, χωρίς --reload.

Χρησιμοποιείται από το Electron main process (spawn) στο packaged app:
    python run_server.py --host 127.0.0.1 --port 8000
ή ως PyInstaller target (prospectmatch-backend.exe).

Το dev workflow παραμένει `uvicorn main:app --reload`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="ProspectMatch backend server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn
    from main import app

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
