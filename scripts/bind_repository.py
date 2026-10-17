"""Bind release metadata to an actual, explicitly supplied GitHub repository."""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bind(repository: str) -> str:
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([a-zA-Z0-9-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?",
        repository,
    )
    if not match:
        raise ValueError("Eine vollständige GitHub-HTTPS- oder SSH-Repository-URL ist erforderlich")
    owner, name = match.groups()
    url = f"https://github.com/{owner}/{name}"
    path = ROOT / "custom_components" / "iqalarm" / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        documentation=url + "#readme", issue_tracker=url + "/issues", codeowners=[f"@{owner}"]
    )
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository")
    args = parser.parse_args()
    print(bind(args.repository))
