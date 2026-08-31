import io
import os
import shutil
import sys
import importlib.util
import verify_suite
from pathlib import Path


def _clear_mindseam(workspace):
    mindseam_dir = os.path.join(workspace, ".mindseam")
    if os.path.isdir(mindseam_dir):
        for name in os.listdir(mindseam_dir):
            p = os.path.join(mindseam_dir, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)


def run_controller(workspace, *args, stdin=None):
    return _RunControllerResult.call(workspace, *args, stdin=stdin)


def _run_verify_suite(repo_path):
    repo_path = Path(repo_path)
    verify_suite.find_repo()
    old_pass, old_fail = verify_suite.PASS, verify_suite.FAIL
    verify_suite.PASS = 0
    verify_suite.FAIL = 0

    script_path = repo_path / "scripts" / "mindseam.py"
    spec = importlib.util.spec_from_file_location("mindseam_copied", str(script_path))
    mindseam_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mindseam_mod)

    old_out, old_err = sys.stdout, sys.stderr
    out_buf, err_buf = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = out_buf, err_buf
    rc = 0
    try:
        verify_suite.check_integrity(mindseam_mod, repo_path)
        if verify_suite.FAIL:
            rc = 1
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else (2 if exc.code else 0)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        verify_suite.PASS, verify_suite.FAIL = old_pass, old_fail

    return rc, out_buf.getvalue(), err_buf.getvalue()


class _RunControllerResult:
    @staticmethod
    def call(workspace, *args, stdin=None):
        original = os.getcwd()
        prev_stdin = sys.stdin
        prev_out, prev_err = sys.stdout, sys.stderr
        out_buf, err_buf = [], []
        try:
            os.chdir(workspace)
            if stdin is not None:
                sys.stdin = io.StringIO(stdin)
            sys.stdout = _Tee(out_buf)
            sys.stderr = _Tee(err_buf)
            import mindseam
            try:
                rc = mindseam.main([*args])
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else (2 if exc.code else 0)
        finally:
            sys.stdout, sys.stderr = prev_out, prev_err
            sys.stdin = prev_stdin
            os.chdir(original)
        return _ControllerNamespace(rc, "".join(out_buf), "".join(err_buf))

    @staticmethod
    def call_bytes(workspace, *args, stdin=None):
        original = os.getcwd()
        prev_stdin = sys.stdin.buffer if hasattr(sys.stdin, "buffer") else sys.stdin
        prev_out, prev_err = sys.stdout, sys.stderr
        out_buf, err_buf = [], []
        try:
            os.chdir(workspace)
            if isinstance(stdin, bytes):
                sys.stdin = io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
            sys.stdout = _Tee(out_buf)
            sys.stderr = _Tee(err_buf)
            import mindseam
            rc = mindseam.main([*args])
        finally:
            sys.stdout, sys.stderr = prev_out, prev_err
            sys.stdin = prev_stdin
            os.chdir(original)
        return _ControllerBytesNamespace(rc, "".join(out_buf).encode(), "".join(err_buf).encode())


class _Tee:
    def __init__(self, buf):
        self._buf = buf
        self._buf.append("")

    def write(self, data):
        self._buf[0] += data

    def flush(self):
        pass


class _ControllerNamespace:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _ControllerBytesNamespace:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
