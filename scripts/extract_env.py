# move_env.py

import shutil
import sys
from pathlib import Path

def ensure_gitignore_has_env(repo_root: Path) -> None:
    gi = repo_root / ".gitignore"
    try:
        if gi.exists():
            content = gi.read_text(encoding="utf-8").splitlines()
        else:
            content = []
        if ".env" not in content:
            content.append(".env")
            gi.write_text("\n".join(content) + "\n", encoding="utf-8")
            print("Updated .gitignore to include .env")
    except Exception as e:
        print(f"⚠️ Could not update .gitignore: {e}", file=sys.stderr)

def main(argv=None):
    argv = argv or sys.argv[1:]
    copy_only = "--copy" in argv
    force = "--force" in argv

    repo_root = Path.cwd()  # you said you always run from root
    src = repo_root / ".env"
    dst_dir = repo_root / "config"
    dst = dst_dir / "example.env"

    if not src.exists():
        print("No .env found; nothing to do.")
        return 0

    dst_dir.mkdir(parents=True, exist_ok=True)

    if dst.exists() and not force:
        print(f"{dst} already exists. Use --force to overwrite, or remove it first.")
        return 1

    try:
        if copy_only:
            shutil.copy2(src, dst)
            print("Copied .env → config/example.env.")
        else:
            # true move (preserves metadata where possible)
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            print("Moved .env → config/example.env.")
    except Exception as e:
        print(f"❌ Failed to write {dst}: {e}", file=sys.stderr)
        return 1

    ensure_gitignore_has_env(repo_root)
    print("Rotate any secrets in config/example.env and load via os.environ.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())