"""提交前只读审计：测试、语法、核心验收、采集状态和 Git 状态。"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from .check_environment import check_requirements, installed_versions
    from .validate_collection import inspect_collection
except ImportError:  # 支持直接执行脚本
    from check_environment import check_requirements, installed_versions
    from validate_collection import inspect_collection


def summarize_audit(
    tests_ok,
    compile_ok,
    acceptance_ok,
    collection_ready,
    git_clean,
    collection_errors,
    test_count=None,
    environment_ok=True,
    android_contract_ok=True,
):
    checks = {
        "tests": bool(tests_ok),
        "syntax": bool(compile_ok),
        "acceptance": bool(acceptance_ok),
        "environment": bool(environment_ok),
        "collection_ready": bool(collection_ready),
        "git_clean": bool(git_clean),
        "android_contract": bool(android_contract_ok),
    }
    blocker_names = {
        "tests": "tests_failed",
        "syntax": "syntax_failed",
        "acceptance": "acceptance_failed",
        "environment": "environment_mismatch",
        "collection_ready": "collection_not_ready",
        "git_clean": "git_dirty",
        "android_contract": "android_contract_failed",
    }
    blocking_items = [
        blocker_names[name] for name, passed in checks.items() if not passed
    ]
    return {
        "passed": not blocking_items,
        "checks": checks,
        "test_count": test_count,
        "collection_errors": list(collection_errors),
        "blocking_items": blocking_items,
    }


def _run(command, root):
    return subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )


def audit_project(root="."):
    root = Path(root).resolve()
    test_run = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], root)
    test_match = re.search(r"Ran (\d+) tests?", test_run.stdout + test_run.stderr)
    test_count = int(test_match.group(1)) if test_match else None

    python_files = sorted(
        [*root.glob("scripts/*.py"), *root.glob("tests/*.py")]
    )
    compile_run = _run(
        [sys.executable, "-m", "py_compile", *[str(path) for path in python_files]],
        root,
    )
    acceptance_run = _run([sys.executable, "scripts/acceptance_check.py"], root)
    android_contract_run = _run(
        [sys.executable, "scripts/check_android_contract.py"], root
    )
    requirements_path = root / "requirements.txt"
    environment = check_requirements(
        requirements_path.read_text(encoding="utf-8").splitlines(),
        installed_versions(requirements_path),
    )
    collection = inspect_collection(
        root / "data/collection_manifest.csv", root / "data/raw"
    )
    git_run = _run(["git", "status", "--porcelain"], root)
    collection_errors = list(collection["errors"])
    collection_errors.extend(f"missing_video:{item}" for item in collection["missing"])
    collection_errors.extend(
        f"metadata_incomplete:{item}" for item in collection["metadata_incomplete"]
    )
    result = summarize_audit(
        tests_ok=test_run.returncode == 0,
        compile_ok=compile_run.returncode == 0,
        acceptance_ok=acceptance_run.returncode == 0,
        environment_ok=environment["passed"],
        collection_ready=collection["ready"],
        git_clean=git_run.returncode == 0 and not git_run.stdout.strip(),
        android_contract_ok=android_contract_run.returncode == 0,
        collection_errors=sorted(set(collection_errors)),
        test_count=test_count,
    )
    result["collection"] = collection
    result["environment"] = environment
    result["commands"] = {
        "tests_returncode": test_run.returncode,
        "compile_returncode": compile_run.returncode,
        "acceptance_returncode": acceptance_run.returncode,
        "android_contract_returncode": android_contract_run.returncode,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="运行提交前只读审计")
    parser.add_argument("--root", default=".", help="项目根目录")
    args = parser.parse_args()
    result = audit_project(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
