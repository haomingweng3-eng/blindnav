"""离线检查 requirements.txt 中的包是否存在并满足版本约束。"""

import argparse
import importlib.metadata
import json
import re
from pathlib import Path


REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*(==|>=|<=|>|<)\s*([^;\s]+)")


def _version_key(value):
    numbers = [int(part) for part in re.findall(r"\d+", str(value))]
    return tuple(numbers or [0])


def _satisfies(installed, operator, required):
    left = _version_key(installed)
    right = _version_key(required)
    return {
        "==": left == right,
        ">=": left >= right,
        "<=": left <= right,
        ">": left > right,
        "<": left < right,
    }[operator]


def check_requirements(lines, installed_versions):
    missing = []
    incompatible = []
    invalid = []
    checked = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = REQUIREMENT_RE.match(line)
        if not match:
            invalid.append(line)
            continue
        name, operator, required = match.groups()
        checked.append(name)
        installed = installed_versions.get(name)
        if installed is None:
            missing.append(name)
        elif not _satisfies(installed, operator, required):
            incompatible.append(
                {"package": name, "installed": installed, "required": f"{operator}{required}"}
            )
    return {
        "passed": not missing and not incompatible and not invalid,
        "checked": checked,
        "missing": missing,
        "incompatible": incompatible,
        "invalid": invalid,
    }


def installed_versions(requirements_path):
    versions = {}
    for raw_line in Path(requirements_path).read_text(encoding="utf-8").splitlines():
        match = REQUIREMENT_RE.match(raw_line.strip())
        if not match:
            continue
        name = match.group(1)
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def main():
    parser = argparse.ArgumentParser(description="检查 Python 依赖版本")
    parser.add_argument("requirements", nargs="?", default="requirements.txt")
    args = parser.parse_args()
    path = Path(args.requirements)
    result = check_requirements(
        path.read_text(encoding="utf-8").splitlines(), installed_versions(path)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
