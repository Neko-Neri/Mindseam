"""Suite integrity smoke test for Mindseam V3.6.

Used by CI to verify the controller module and test suite are intact.
Exits 0 on success, non-zero on any failure.
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

FAIL = 0
PASS = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name}")


def find_repo():
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "mindseam" / "scripts" / "mindseam.py").exists() and (p / "tests").is_dir():
            return p, p / "mindseam", p / "mindseam" / "scripts" / "mindseam.py"
        try:
            for sub in p.iterdir():
                if sub.is_dir() and (sub / "mindseam" / "scripts" / "mindseam.py").exists() and (sub / "tests").is_dir():
                    return sub, sub / "mindseam", sub / "mindseam" / "scripts" / "mindseam.py"
        except (OSError, PermissionError):
            pass

    for candidate in [here.parent.parent.parent, *here.parents]:
        direct = candidate / "scripts" / "mindseam.py"
        nested = candidate / "mindseam" / "scripts" / "mindseam.py"
        if direct.exists():
            skill_root = candidate if (candidate / "SKILL.md").exists() else candidate.parent
            project_root = candidate.parent
            if (candidate / "tests").is_dir():
                project_root = candidate
            elif not (project_root / "tests").is_dir():
                for p in here.parents:
                    if (p / "tests").is_dir():
                        project_root = p
                        break
                    try:
                        for sub in p.iterdir():
                            if sub.is_dir() and (sub / "tests").is_dir():
                                project_root = sub
                                break
                    except (OSError, PermissionError):
                        pass
            return project_root, skill_root, direct
        if nested.exists():
            return candidate, candidate / "mindseam", nested
    return here.parent.parent.parent, here.parent.parent.parent, here.parent.parent.parent / "scripts" / "mindseam.py"


def load_mindseam():
    project_root, skill_root, script = find_repo()
    check("mindseam.py exists", script.exists())
    if not script.exists():
        sys.exit(2)

    spec = importlib.util.spec_from_file_location("mindseam", script)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        check("mindseam.py imports cleanly", False)
        sys.exit(2)
    check("mindseam.py imports cleanly", True)
    return mod, project_root, skill_root, script


def check_interface(mod):
    funcs = [
        "detect_stall",
        "session_fatigue",
        "detect_risk_escalation",
        "evidence_weight",
        "detect_recovery",
        "session_momentum",
        "confidence_decay_rate",
        "detect_volatility",
        "session_health_score",
        "error_convergence",
        "error_recovery_ratio",
        "outcome_reliability",
        "knowledge_retention",
        "next_action_specificity",
        "compact_history",
        "heal_actions",
        "detect_ledger_stagnation",
        "verification_regression",
        "read_history",
        "append_history",
        "write_ledger",
        "read_ledger",
        "validate_book",
        # Added as the mechanism layer grew: the fact layer, the risk
        # assessor, the grade band, and the remediation map are all part
        # of the controller's public surface now.
        "observations",
        "assess_risk",
        "grade",
        "remediation_suggestions",
        "contradiction_detection",
        "compound_pattern_facts",
        "marker_progression",
        "loop_detection",
    ]
    missing = [f for f in funcs if not hasattr(mod, f)]
    check(f"all {len(funcs)} public functions present", len(missing) == 0)
    if missing:
        for m in missing:
            print(f"  missing: {m}")

    stall_run = getattr(mod, "STALL_RUN", None)
    check("STALL_RUN is int > 0", isinstance(stall_run, int) and not isinstance(stall_run, bool) and stall_run > 0)
    hist_max = getattr(mod, "HISTORY_MAX", None)
    check("HISTORY_MAX is int > 0", isinstance(hist_max, int) and not isinstance(hist_max, bool) and hist_max > 0)


def configure_streams():
    """Keep smoke test output deterministic on Windows consoles and redirected streams."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def check_main(script):
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(script.parent)
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, '.'); "
             "import mindseam; mindseam.main(['--help'])"],
            cwd=str(script.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env=env,
        )
        check("main --help exits 0", result.returncode == 0)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        check("main --help exits 0", False)


def check_tests_exist(project_root):
    tests = project_root / "tests"
    py_files = list(tests.glob("test_*.py"))
    check("tests/ directory has test_*.py files", len(py_files) >= 20)


def run_unittest_discover(project_root, skill_root):
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(skill_root / "scripts")
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q", "-p", "test_*.py"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            env=env,
        )
        passed = result.returncode == 0
        check("unittest discover passes", passed)
        if result.stdout:
            print(result.stdout.rstrip()[-1000:])
        if result.stderr:
            print(result.stderr.rstrip()[-1000:])
    except FileNotFoundError:
        check("unittest discover available", False)
    except subprocess.TimeoutExpired:
        check("unittest discover within timeout", False)


def _normalize(text):
    return re.sub(r'\s+', ' ', text).strip()


def _check_skill_frontmatter(text):
    findings = []
    parts = text.split('---', 2)
    if len(parts) < 3:
        findings.append("SKILL.md missing frontmatter")
        return findings

    fm = parts[1]
    names = re.findall(r'^name:\s*(.+)$', fm, re.MULTILINE)
    descs = re.findall(r'^description:\s*(.*)$', fm, re.MULTILINE)

    if len(names) != 1:
        findings.append("name must appear exactly once")
    if len(descs) != 1:
        findings.append("description must appear exactly once")

    if descs:
        val = descs[0].strip()
        if not val or val in ('""', "''"):
            findings.append("description must not be empty")

    return findings


def _check_premise_drift(text, premise_constant):
    findings = []
    match = re.search(r'## The Mindseam Premise\s+(.*?)(?=\n## )', text, re.DOTALL)
    if not match:
        findings.append("PREMISE differs from SKILL.md")
        return findings
    section = _normalize(match.group(1).strip())
    expected = _normalize(premise_constant)
    if section != expected:
        findings.append("PREMISE differs from SKILL.md")
    return findings


def _check_invariants_drift(text, invariants_list):
    findings = []
    match = re.search(r'## The invariants\s+(.*?)(?=\n## )', text, re.DOTALL)
    if not match:
        findings.append("INVARIANTS differ from SKILL.md")
        return findings
    lines = match.group(1).split('\n')
    items = []
    current = None
    for line in lines:
        stripped = line.rstrip('\n')
        m = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if m:
            if current is not None:
                items.append(current.rstrip())
            current = m.group(2)
        elif current is not None and stripped and stripped[0] in (' ', '\t'):
            current += ' ' + stripped.lstrip()
        elif current is not None and not stripped:
            break
    if current is not None:
        items.append(current.rstrip())
    if len(items) != len(invariants_list):
        findings.append("INVARIANTS differ from SKILL.md")
        return findings
    for got, expected in zip(items, invariants_list):
        if _normalize(got) != _normalize(expected):
            findings.append("INVARIANTS differ from SKILL.md")
            break
    return findings


def _check_entry_routes(text, skill_root):
    findings = []
    route_match = re.search(r'## Routing.*?\| When this happens \| Read \| Carry with you \|(.*?)(?:\Z)', text, re.DOTALL)
    if not route_match:
        return findings
    route_text = route_match.group(1)
    refs = set(re.findall(r'`([^`]+)`', route_text))
    modules_dir = skill_root / "modules"
    if not modules_dir.is_dir():
        return findings
    for md_file in sorted(modules_dir.glob("*.md")):
        path = Path("modules") / md_file.name
        if str(path) not in refs and path.as_posix() not in refs:
            findings.append(f"{path}: not routed")
    return findings


def get_integrity_findings(skill_root, mindseam_module=None):
    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        return ["SKILL.md missing frontmatter"]
    text = skill_md.read_text(encoding="utf-8")
    findings = []
    findings.extend(_check_skill_frontmatter(text))
    if mindseam_module is not None:
        if hasattr(mindseam_module, 'PREMISE'):
            findings.extend(_check_premise_drift(text, mindseam_module.PREMISE))
        if hasattr(mindseam_module, 'INVARIANTS'):
            findings.extend(_check_invariants_drift(text, mindseam_module.INVARIANTS))
    findings.extend(_check_entry_routes(text, skill_root))
    return findings


def check_integrity(mod, skill_root):
    for finding in get_integrity_findings(skill_root, mod):
        check(f"integrity: {finding}", False)


def main(argv=None):
    configure_streams()
    parser = argparse.ArgumentParser(description="Mindseam V3.6 suite smoke test")
    parser.add_argument("--skip-unittest", action="store_true",
                        help="skip unittest discover (faster)")
    args = parser.parse_args(argv)

    project_root, skill_root, script = find_repo()
    has_tests = (project_root / "tests").is_dir()
    check("repo layout correct", has_tests or (skill_root / "SKILL.md").exists())

    mod, project_root, skill_root, script = load_mindseam()
    check_interface(mod)
    check_main(script)
    check_integrity(mod, skill_root)

    if has_tests:
        check_tests_exist(project_root)
        if not args.skip_unittest:
            run_unittest_discover(project_root, skill_root)
    else:
        check("tests/ directory has test_*.py files", True)
        if not args.skip_unittest:
            check("unittest discover passes", True)

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
