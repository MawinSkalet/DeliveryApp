"""Create the source ZIP for the CP1 assignment upload without local secrets."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "DeliveryApp_CP1_submission.zip"
ROOT_FILES = ("README.md", "docker-compose.yml", ".env.example", ".gitignore")
SOURCE_DIRS = (".github", "backend", "frontend", "docs", "tools")
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "dist", ".pytest_cache", ".ruff_cache"}
SKIP_NAMES = {".env", ".DS_Store"}
SKIP_SUFFIXES = {".pyc", ".db", ".sqlite", ".sqlite3"}


def source_files() -> list[Path]:
    files = [ROOT / name for name in ROOT_FILES]
    for directory in SOURCE_DIRS:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    result = []
    for path in sorted(set(files)):
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            raise ValueError(f"Refusing to package a symbolic link: {relative}")
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if (
            path.name in SKIP_NAMES
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix.lower() in SKIP_SUFFIXES
        ):
            continue
        result.append(path)
    return result


def main() -> None:
    files = source_files()
    OUTPUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, arcname=f"DeliveryApp/{path.relative_to(ROOT).as_posix()}")

    with ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        required = {
            "DeliveryApp/README.md",
            "DeliveryApp/docker-compose.yml",
            "DeliveryApp/.env.example",
            "DeliveryApp/backend/app/orders.py",
            "DeliveryApp/backend/app/products.py",
            "DeliveryApp/backend/scripts/seed.py",
            "DeliveryApp/docs/cp1-submission.md",
        }
        if not required.issubset(names):
            raise RuntimeError(f"Missing required submission files: {sorted(required - set(names))}")
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity check failed")
        if any("/.git/" in name or name.endswith("/.env") for name in names):
            raise RuntimeError("ZIP contains a local Git or environment file")

    print(f"Created {OUTPUT} ({len(files)} files, {OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
