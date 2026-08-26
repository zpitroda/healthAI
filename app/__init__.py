import os
from pathlib import Path

def _load_env() -> None:
    """
    Automatically discovers and loads .env file variables into os.environ
    checking the current working directory, the project root, and parent directories.
    Existing environment variables are preserved.
    """
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    seen = set()
    for env_path in candidates:
        try:
            resolved = env_path.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            with open(resolved, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            continue

_load_env()
