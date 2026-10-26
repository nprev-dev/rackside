"""Checks that a release is ready and writes its notes.

    python .github/release_notes.py REF NOTES_FILE

REF is what was pushed: refs/tags/vX.Y.Z for a release, anything else for a rehearsal. The version
in the code (rack_dashboard/__init__.py) must match the tag, and CHANGELOG.md must have a section
for it, which becomes the release's notes. Prints the version.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def code_version() -> str:
    found = re.search(r'^__version__ = "([^"]+)"', (ROOT / "rack_dashboard" / "__init__.py").read_text(), re.M)
    if not found:
        raise SystemExit("no __version__ in rack_dashboard/__init__.py")
    return found.group(1)


def section(changelog: str, version: str) -> str:
    """The text under "## VERSION" in the changelog, up to the next section."""
    found = re.search(rf"^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)", changelog, re.M | re.S)
    return found.group(1).strip() if found else ""


def main(argv: list[str]) -> int:
    ref, notes_file = argv[1], Path(argv[2])
    version = code_version()
    if ref.startswith("refs/tags/"):
        tag = ref[len("refs/tags/"):]
        if tag != f"v{version}":
            print(f"The tag is {tag}, but the code says {version}. Change __version__ in rack_dashboard/__init__.py, or tag v{version}.", file=sys.stderr)
            return 1
    notes = section((ROOT / "CHANGELOG.md").read_text(), version)
    if not notes:
        print(f"CHANGELOG.md has no section \"## {version}\" (or it is empty). Write what changed there first.", file=sys.stderr)
        return 1
    notes_file.write_text(notes + "\n")
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
