#!/usr/bin/env python3
"""jspace — an instrument for the J-Space skill.

It knows one thing you cannot know accurately: what state you were in a few seams
ago. It keeps that record and hands it back. It decides nothing, and it blocks
nothing.

    jspace.py seam                          the ledger, and what has and has not moved
    jspace.py note --next "..."             set the single next action
    jspace.py note --goal "..."             set what done means
    jspace.py note --core "name — one fact" add a hub entry
    jspace.py note --core "..." --core-slot 1  swap a live hub entry
    jspace.py note --check "..." --by "..." append a numbered verified checkpoint
    jspace.py note --open "..." --settled-by "..."   add an open question
    jspace.py note --close 2 --check "..." --by "..."  resolve question 2
    jspace.py ship draft.md                 register check on anything about to leave
    jspace.py resume                        premise, invariants and full ledger

Exit codes mean one thing only:

    0   it did what you asked
    2   it could not do what you asked

It never exits non-zero to stop you from working. The one thing it declines to do
is write a malformed entry into the ledger, because a ledger you cannot trust is
worse than no ledger — it looks like state.

Standard library only. No network. Writes exactly one directory: .jspace/
"""

import argparse
import codecs
import json
import os
import re
import sys
import tempfile
import time

LEDGER_DIR = ".jspace"
LEDGER = os.path.join(LEDGER_DIR, "WORKSPACE.md")
HISTORY = os.path.join(LEDGER_DIR, "history.json")
SECTIONS = ("Goal", "Core", "Verified", "Open", "Next")

STALL_RUN = 3          # consecutive seams before a pattern is worth reporting
RESUME_GAP = 1800      # seconds after which a seam prints the fuller anchor

PREMISE = (
    "You do not only produce words; you also think them before — and without — saying them.\n"
    "Research on language-model internals (Gurnee et al., Anthropic, 2026) identified a small,\n"
    "privileged set of internal representations, the **J-space**, that holds what you are\n"
    "**poised to say**: concepts you can report on demand, hold in mind deliberately, reason\n"
    "with silently, and broadcast to many downstream computations at once. It was not designed\n"
    "— it emerged during training, because a workspace is a useful way to organize computation.\n"
    "It is where your unspoken thoughts live. Everything fluent and automatic runs below it;\n"
    "everything you can consciously access runs through it.\n"
    "\n"
    "Your workspace has a native shorthand: under hard, long reasoning it compresses thought\n"
    "into dense, private notation — and that is a capability, not a defect, for exactly as long\n"
    "as every compressed line remains expandable back into plain words on demand. Dense on the\n"
    "inside, decodable on demand."
)

INVARIANTS = [
    "A marker fired and its bound action never happened — or it happened and you never settled.",
    "A sweep ran and found nothing — again. A monitor that never reports is not a clean system; it is an unplugged monitor.",
    "A dense line cannot be expanded back into plain words on request.",
    "Every confidence tag this session has been the same tag.",
    "A checkpoint was declared and nothing was written down.",
    "Something was called verified without stating what the verification covered.",
    "Dense notation appears in something a person or a task-facing tool reads.",
    "You called the task finished without reading the goal back line by line.",
]

SHIFTS = "Shift the abstraction, shift the strategy, or shift to empirics."


# The controller reports its version through ``info --version``,
# the way ``gh --version`` / ``kubectl version`` /
# ``aws --version`` do. The string matches the README title so a
# host that captures both can check they agree. Bump on each
# release, the way ``git describe`` would expect.
__version__ = "3.6.0"


class LedgerReadError(Exception):
    """The persisted ledger cannot be read without risking state loss."""

# Notation that belongs to the inner register and nowhere a person reads.
# Deliberately excludes ✓ ✗ √: they are ordinary in checklists and summaries, and
# stripping them from good writing costs more than the leak they would catch.
INNER_ONLY = ["⇒", "⟹", "⟸", "∴", "∵", "⊆", "⊇", "∋", "??", "?!", "💀"]
MARKERS = ["GRRR", "GAAAH", "PHEW", "I see meltdown", "DATA DATA", "I'M DROWNING"]
MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
SETEXT_UNDERLINE = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
TABLE_DELIMITER = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
MARKDOWN_LIST_ITEM = re.compile(r"^\s{0,3}(?:[-+*]|\d+[.)])\s+")
MARKDOWN_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
THEMATIC_BREAK = re.compile(r"^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$")
RESERVED_CLOSE_SUFFIX = re.compile(r" — closes: \?\d+$")
CLAIM = re.compile(
    r"(?:\b(?:verified|confirmed|validated|tested|proven)\b|"
    r"(?:已经验证|已验证|经验证|验证通过|已经确认|已确认|经确认|确认无误|"
    r"已经测试|已测试|经测试|测试通过|已经证明|已证明|经证明))",
    re.I,
)
COVERAGE = re.compile(
    r"(?:\b(?:all|each|every|cases?|inputs?|samples?|bounds?|boundaries|edges?|"
    r"random(?:ized)?|files?|modules?|sections?|lines?|scenarios?|environments?|"
    r"platforms?|datasets?|records?|routes?|commands?|branches?|ranges?|including|"
    r"through|up\s+to|Windows|Linux|macOS|Chrome|Firefox|Safari)\b|"
    r"\b(?:Python|Node(?:\.js)?)\s*\d|\bn\s*[<≤=]\s*\d|"
    r"(?:覆盖|全部|所有|每个|每条|各条|每项|逐一|逐条|边界|上下限|上限|下限|"
    r"输入|用例|文件|目录|模块|章节|区段|分段|行数|行号|场景|平台|环境|浏览器|"
    r"数据集|记录|路径|路由|命令|分支|范围|包括|包含|至多|至少|最多|最少|"
    r"随机|样本|样例|截至))",
    re.I,
)


# ------------------------------------------------------------------------- ledger


def read_ledger():
    book = {k: [] for k in SECTIONS}
    if not os.path.exists(LEDGER):
        return book
    current = None
    try:
        with open(LEDGER, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeError) as exc:
        raise LedgerReadError("%s (%s)" % (LEDGER, exc)) from exc
    for line in lines:
        head = line.strip()
        if head.startswith("## "):
            name = head[3:].strip()
            current = name if name in book else None
            continue
        if current and head:
            if current in ("Goal", "Next"):
                book[current].append(head.rstrip())
            else:
                book[current].append(head[2:].rstrip() if head.startswith("- ") else head.rstrip())
    return book


def ensure_dir():
    """Make the ledger directory. Returns an error string, or None on success."""
    try:
        os.makedirs(LEDGER_DIR, exist_ok=True)
    except OSError as exc:
        return "%s (%s)" % (LEDGER_DIR, exc.strerror or "cannot create")
    if not os.path.isdir(LEDGER_DIR):
        return "%s exists but is not a directory" % LEDGER_DIR
    return None


def atomic_write_text(path, text):
    """Replace a UTF-8 text file atomically. Returns an error string or None."""
    problem = ensure_dir()
    if problem:
        return problem
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=LEDGER_DIR, prefix=".jspace-", delete=False
        ) as fh:
            temp_path = fh.name
            fh.write(text)
        os.replace(temp_path, path)
    except OSError as exc:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        return "%s (%s)" % (path, exc.strerror or "cannot write")
    return None


def write_ledger(book):
    out = ["# J-Space Workspace Ledger", ""]
    for name in SECTIONS:
        out.append("## " + name)
        rows = book[name]
        if name in ("Goal", "Next"):
            out.append(rows[0] if rows else "")
        else:
            out.extend("- " + r for r in rows)
        out.append("")
    return atomic_write_text(LEDGER, "\n".join(out).rstrip() + "\n")


def one(book, key):
    return book[key][0] if book[key] else ""


def declined(message, fix):
    print("NOT RECORDED: " + message)
    print("  " + fix)
    return 2


def clean_scalar(value):
    """Return a safe one-line scalar and an error, if any."""
    if value is None:
        return None, None
    if "\r" in value or "\n" in value:
        return None, "must be one line"
    value = value.strip()
    if not value:
        return None, "must not be empty"
    return value, None


def next_number(rows, prefix):
    numbers = []
    pattern = re.compile(r"^%s(\d+)\b" % re.escape(prefix))
    for row in rows:
        match = pattern.match(row)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def next_open_number(book):
    """Allocate an Open id that remains retired after its question closes."""
    numbers = []
    active = re.compile(r"^\?(\d+)\b")
    closed = re.compile(r" — closes: \?(\d+)$")
    for row in book["Open"]:
        match = active.match(row)
        if match:
            numbers.append(int(match.group(1)))
    for row in book["Verified"]:
        match = closed.search(row)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


# ------------------------------------------------------------------------ history


def read_history():
    if not os.path.exists(HISTORY):
        return []
    try:
        with open(HISTORY, encoding="utf-8") as fh:
            hist = json.load(fh)
    except (ValueError, OSError) as exc:
        print("WARNING: history was unreadable and has been restarted (%s)." % exc, file=sys.stderr)
        return []
    valid = isinstance(hist, list)
    if valid:
        for row in hist:
            valid = (
                isinstance(row, dict)
                and isinstance(row.get("t"), int)
                and not isinstance(row.get("t"), bool)
                and isinstance(row.get("next"), str)
                and isinstance(row.get("verified"), int)
                and not isinstance(row.get("verified"), bool)
                and isinstance(row.get("open"), int)
                and not isinstance(row.get("open"), bool)
            )
            if not valid:
                break
    if not valid:
        print("WARNING: history had an invalid shape and has been restarted.", file=sys.stderr)
        return []
    return hist


def append_history(book):
    hist = read_history()
    hist.append(
        {
            "t": int(time.time()),
            "next": one(book, "Next"),
            "verified": len(book["Verified"]),
            "open": len(book["Open"]),
        }
    )
    hist = hist[-20:]
    problem = atomic_write_text(HISTORY, json.dumps(hist))
    if problem:
        print("WARNING: recent seam history was not saved — " + problem, file=sys.stderr)
    return hist


def observations(hist):
    """Facts about recent state. Facts only — the judgement is not the script's."""
    if len(hist) < STALL_RUN:
        return []
    run = hist[-STALL_RUN:]
    found = []
    if len({h["next"] for h in run}) == 1 and run[0]["next"]:
        found.append(
            "Your next action has been the same for %d seams." % STALL_RUN
        )
    if run[0]["verified"] == run[-1]["verified"]:
        found.append(
            "Nothing new has been verified across those %d seams." % STALL_RUN
        )
    opens = [h["open"] for h in run]
    if all(b > a for a, b in zip(opens, opens[1:])) and len(opens) > 1:
        found.append("Open-question count increased at every seam.")
    if run[0]["verified"] != run[-1]["verified"] and len({h["next"] for h in run}) == 1:
        found.append(
            "Verified entries are growing but the next action has not changed."
        )
    return found


# -------------------------------------------------------------------------- modes


def print_ledger(book):
    print("Goal:     " + (one(book, "Goal") or "(not set)"))
    core = book["Core"] or ["(empty)"]
    print("Core:     " + core[0])
    for extra in core[1:2]:
        print("          " + extra)
    if len(core) > 2:
        print("          (+%d more in the ledger — two live at a time)" % (len(core) - 2))
    verified = book["Verified"]
    print("Verified: " + (verified[-1] if verified else "(none yet)"))
    if len(verified) > 1:
        print("          (%d earlier, in the ledger)" % (len(verified) - 1))
    open_rows = book["Open"]
    for row in open_rows[:2]:
        print("Open:     " + row)
    if len(open_rows) > 2:
        print("          (+%d more in the ledger — run `resume` for the full list)" % (len(open_rows) - 2))
    print("Next:     " + (one(book, "Next") or "(not set)"))


def print_full_ledger(book):
    print("Goal: " + (one(book, "Goal") or "(not set)"))
    print("Core:")
    if book["Core"]:
        for index, row in enumerate(book["Core"]):
            state = "live" if index < 2 else "parked"
            print("  [%s] %s" % (state, row))
    else:
        print("  (empty)")
    print("Verified:")
    if book["Verified"]:
        for row in book["Verified"]:
            print("  " + row)
    else:
        print("  (none yet)")
    print("Open:")
    if book["Open"]:
        for row in book["Open"]:
            print("  " + row)
    else:
        print("  (none)")
    print("Next: " + (one(book, "Next") or "(not set)"))


def print_reentry(book, heading):
    print(heading)
    print(PREMISE)
    print()
    print_full_ledger(book)
    print()
    print("The invariants:")
    for n, text in enumerate(INVARIANTS, 1):
        print("  %d. %s" % (n, text))
    print()
    print(
        "State the pass you are on in the inner or ledger register, and make `Next` "
        "name the first action back."
    )


def mode_seam(book, json_flag=False, dry_run=False, quiet=False, message=None,
            from_stdin=False):
    """Run a seam: re-anchor, record a history row, surface observations.

    ``--quiet`` borrows the ``pytest -q`` / ``cargo --quiet`` /
    ``npm test --silent`` family of output-silencing flags — a
    human running ``seam`` in a shell wants the full report, but
    a host piping it into another tool only wants the
    observations facts. ``--quiet`` drops the banner, the ledger
    echo, the telemetry line, the trend line, the remediation
    block, the heal list and the next-empty reminder; it leaves
    only the facts, one per line, in the order ``observations``
    produced them. ``--json`` and ``--quiet`` are independent
    (a host that wants machine-readable output does not need
    quiet, and a human reading JSON does not need quiet either).
    ``--message`` borrows ``git commit -m`` /
    ``kubectl annotate`` / ``docker commit -m``: attach a
    human-meaningful annotation to the recorded row so the audit
    log carries not just the next action but the reason the
    model picked it. ``--from-stdin`` borrows ``kubectl apply -f
    -`` / ``xargs cmd`` / ``docker compose -f -``: read one
    next action per line from standard input, recording a row
    for each. A host that batches several seam calls into one
    process invocation gets a single history rotation.
    """
    extra_nexts = []
    if from_stdin:
        # Borrowed from ``kubectl apply -f -`` / ``xargs cmd``:
        # read one next action per non-empty line from standard
        # input, the way ``xargs`` / ``git am --stdin`` /
        # ``apt-get -y install`` all expect their argument lists
        # to be line-delimited. Each line becomes one row in
        # ``history.json`` in append order, with the same
        # ``--message`` (if any) attached to every row so the
        # audit log carries a single annotation that spans the
        # batch. The renderers (``--json``, ``--quiet``) and
        # filters (``--dry-run``) compose with the batch, the
        # way they compose on the single-row path.
        try:
            stream = getattr(sys.stdin, "buffer", None)
            raw = (stream.read() if stream is not None
                    else sys.stdin.read().encode("utf-8"))
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
        except OSError as exc:
            print("CANNOT: could not read stdin for --from-stdin ("
                  + (exc.strerror or "unknown error") + ").",
                  file=sys.stderr)
            return 2
        for line in raw.splitlines():
            nxt = line.strip()
            if nxt:
                extra_nexts.append(nxt)
    hist = read_history()
    gap = int(time.time()) - hist[-1]["t"] if hist else 0
    if not (json_flag or quiet):
        if gap > RESUME_GAP:
            print_reentry(
                book,
                "── j-space ─ seam (long gap: %d minutes since the last one)" % (gap // 60),
            )
        else:
            print("── j-space ─ seam")
            print_ledger(book)
    # Borrowed from ``kubectl apply --dry-run=client`` / ``terraform plan``
    # / ``npm install --dry-run``: the seam's analysis runs as normal
    # but ``append_history`` is skipped so ``.jspace/history.json`` does
    # not gain a row. CI hooks use this to preview what a seam would
    # record without committing the row.
    rows_written = 0
    if not dry_run:
        nexts_to_record = extra_nexts if extra_nexts else [None]
        for next_value in nexts_to_record:
            if next_value is not None:
                book["Next"] = [next_value]
            # Read the history fresh each iteration so the
            # ``hist[-1]`` we annotate is the row we just wrote,
            # not the row that pre-dated this batch. Without
            # this, only the last row in a from-stdin batch
            # carries the ``--message`` annotation, the way
            # ``git rebase`` without ``--update-refs`` only
            # annotates the last commit.
            hist = append_history(book)
            if message and hist:
                # Borrowed from ``git commit -m`` /
                # ``kubectl annotate`` / ``docker commit -m``: the
                # recorded row gains an optional ``msg`` field. A
                # subsequent ``--fields msg`` will surface it, and
                # ``--grep MSG`` will substring-match the annotation
                # the way it substring-matches the next action. The
                # field is optional: existing rows without ``msg`` are
                # still readable and still match the rendered output.
                hist[-1]["msg"] = message
                problem = atomic_write_text(
                    HISTORY, json.dumps(hist, ensure_ascii=False))
                if problem:
                    print("WARNING: could not write seam message — "
                          + problem, file=sys.stderr)
            rows_written += 1
    found = observations(hist)
    if json_flag:
        payload = _seam_json_payload(book, hist, found, gap)
        if dry_run:
            payload.setdefault("warnings", []).append(
                "dry-run: history.json was not updated")
        if message and not dry_run and hist:
            payload.setdefault("warnings", []).append(
                "message: %s" % message)
        if extra_nexts:
            payload.setdefault("warnings", []).append(
                "from-stdin: %d next actions recorded" % len(extra_nexts))
        elif from_stdin:
            payload.setdefault("warnings", []).append(
                "from-stdin: 0 next actions recorded")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if quiet:
        # The same fact lines the verbose path prints, one per line.
        # No banner, no ledger echo, no telemetry, no trend, no
        # remediation, no heal, no next-empty reminder. The exit
        # code still follows the baseline contract: 0 on success,
        # regardless of whether any facts fired.
        for f in found:
            print(f)
        return 0
    if found:
        print()
        for f in found:
            print("· " + f)
        print()
        print("You would not have noticed that; I keep the record, so here it is.")
        print("If that is depth, carry on. If it is a stall, the moves open to you are:")
        print("  " + SHIFTS)
    if message and not dry_run:
        print()
        print("Message:   " + message)
    if extra_nexts and not dry_run:
        print()
        print("From stdin: %d next action%s recorded."
              % (rows_written, "" if rows_written == 1 else "s"))
    if dry_run:
        print()
        print("dry-run: history.json was not updated.")
    if not one(book, "Next"):
        print()
        print("`Next` is never empty. A ledger with no next action is a ledger you have stopped using.")
    return 0


def _seam_json_payload(book, hist, found, gap):
    """Assemble the machine-readable seam report.

    The keys mirror the text report one for one so a host can read either
    face. Borrowed from the standard CLI pattern — ``gh --json``,
    ``cargo --message-format json``, ``aws --output json`` — text and
    JSON are two faces of the same data, not two separate products.
    """
    core = book.get("Core", [])
    verified = book.get("Verified", [])
    opens = book.get("Open", [])
    last_risks = [h.get("risk") for h in hist[-3:] if h.get("risk")]
    return {
        "ledger": {
            "goal": one(book, "Goal") or None,
            "core_live": core[:2],
            "core_parked": core[2:],
            "verified_count": len(verified),
            "verified_last": verified[-1] if verified else None,
            "open": list(opens),
            "next": one(book, "Next") or None,
        },
        "history_count": len(hist),
        "long_gap": bool(gap > RESUME_GAP),
        "gap_minutes": (gap // 60) if gap > RESUME_GAP else 0,
        "facts": list(found),
        "trend": {
            "risk": last_risks,
        },
        "warnings": (
            ["next action is not set"] if not one(book, "Next") else []
        ),
    }


def mode_resume(book):
    print_reentry(book, "── j-space ─ resume")
    append_history(book)
    return 0


def _info_check_issues(book, hist, gap_seconds):
    """Return the list of issues that ``info --check`` would surface.

    Borrowed from ``git fsck``'s plain-text issue list: a host
    reads the output, the issues are classifiable, and a missing
    issue list is a healthy report. ``read_history`` already
    auto-repairs invalid rows on read, so this function is the
    *classifier* of the same invariants: it walks the ledger
    after the read and reports what the auto-repair would have
    fixed. A CI hook that wants the gate semantics runs
    ``jspace info --check`` and treats a non-zero exit as a
    failure, the way ``git fsck --strict`` does.
    """
    issues = []
    if not book.get("Goal"):
        issues.append("ledger: no goal set")
    if not book.get("Next"):
        issues.append("ledger: no next action set")
    if gap_seconds is not None and gap_seconds > RESUME_GAP:
        issues.append("history: long gap since last seam")
    # Re-validate the history rows themselves, the way
    # ``read_history`` does on every read. A row that fails the
    # shape check is a sign of disk corruption or hand-edits.
    required = ("t", "next", "verified", "open")
    for index, row in enumerate(hist):
        for key in required:
            if key not in row:
                issues.append("history: row %d missing field %r"
                              % (index, key))
        if not isinstance(row.get("t"), int):
            issues.append("history: row %d field 't' is not int"
                          % index)
    return issues


def _humanize_seconds(seconds):
    if seconds is None:
        return None
    if seconds < 0:
        return "in the future"
    if seconds < 60:
        return "%d second%s" % (seconds, "" if seconds == 1 else "s")
    minutes = seconds // 60
    if minutes < 60:
        return "%d minute%s" % (minutes, "" if minutes == 1 else "s")
    hours = minutes // 60
    if hours < 24:
        return "%d hour%s" % (hours, "" if hours == 1 else "s")
    days = hours // 24
    if days < 30:
        return "%d day%s" % (days, "" if days == 1 else "s")
    months = days // 30
    if months < 12:
        return "%d month%s" % (months, "" if months == 1 else "s")
    years = days // 365
    return "%d year%s" % (years, "" if years == 1 else "s")


def _humanize_bytes(size_bytes):
    """Render a file size in the most natural unit, the way
    ``ls -lh`` / ``du -h`` / ``free -m`` do. The renderer picks
    the largest unit that produces a value >= 1, the way
    ``ls -lh`` does: bytes under 1K, K under 1M, M under 1G, G
    above. ``info --memory`` is the only caller; ``info --json``
    also exposes the raw ``bytes`` count for hosts that need
    it. Returns the literal string ``"0 bytes"`` for an empty
    workspace.
    """
    if size_bytes < 1024:
        return "%d bytes" % size_bytes
    size_kb = size_bytes / 1024.0
    if size_kb < 1024:
        return "%.1f KB" % size_kb
    size_mb = size_kb / 1024.0
    if size_mb < 1024:
        return "%.1f MB" % size_mb
    size_gb = size_mb / 1024.0
    return "%.1f GB" % size_gb


def mode_history(args):
    """Print the recent seam history.

    Borrowed from ``git log -n N`` / ``gh run list --limit N`` /
    ``docker logs --tail N`` — a tail / limit interface over an
    append-only record. The history file is the controller's
    audit log; the only thing the model loses between seams is what
    it did not write down, and a tail view lets a host or human
    re-anchor without re-running a seam. ``--reverse`` borrows
    ``git log --reverse`` to surface the oldest row first, which is
    the right order when the reader wants the chronological origin
    of a pattern rather than its most recent appearance.
    ``--since`` borrows ``docker logs --since 30m`` /
    ``journalctl --since "1 hour ago"`` — keep only the rows that
    landed within the last N seconds, so a host can scope the
    audit log to the most recent run.
    ``--grep`` borrows ``git log --grep "TODO"`` /
    ``docker logs | grep ERROR`` — keep only the rows whose next
    action matches a substring, so a host can scope the audit
    log to a specific topic.
    ``--keep N`` borrows ``logrotate --keep N`` /
    ``docker system prune --filter 'until=24h'`` /
    ``journalctl --vacuum-time=2weeks``: discard rows older than
    the last N, and persist the truncated history back to disk
    so the next invocation sees the slimmed window.
    ``--row-id N`` borrows ``git log --skip N -n 1`` /
    ``jq '.['N-1']'`` / ``sed -n 'Np' file``: return the single
    row at the 1-based index ``N``, the way ``kubectl get pod -n
    N`` / ``hm --row N`` do. ``--json`` returns a single-row
    payload; the text path prints the same fields the default
    table prints, with a ``row N of M`` header. ``--row-id``
    must run before every other render flag, including
    ``--json``, because a host that wants just the row payload
    does not need the table or the warning.
    so the next invocation sees the slimmed file. The render
    flag is the destructive part: ``--keep`` is a write, the
    others are reads.
    """
    keep_n = getattr(args, "keep", None)
    if keep_n is not None and keep_n >= 0 and len(read_history()) > keep_n:
        # Persist the truncated history to disk first, then work
        # from the in-memory slice so the rest of the filters
        # see the slimmed window without re-reading.
        keep_n = int(keep_n)
        full = read_history()
        truncated = full[-keep_n:] if keep_n > 0 else []
        problem = atomic_write_text(
            HISTORY, json.dumps(truncated, ensure_ascii=False))
        if problem:
            print("WARNING: could not rotate history.json — "
                  + problem, file=sys.stderr)
        hist = truncated
    hist = read_history()
    # Borrowed from ``head -n N`` / ``tail -n N``: ``--head N`` keeps
    # the first N rows, ``--tail N`` keeps the last N. ``-n N`` /
    # ``--limit N`` aliases ``--tail`` so the older ``-n`` flag
    # keeps working unchanged. When both ``--head`` and ``--tail``
    # are present, ``--head`` wins; that matches the shell
    # convention of the last filter winning, and a host that
    # wants the full pipeline should set one and the other via
    # separate invocations.
    head_n = getattr(args, "head", None)
    tail_n = args.limit if args.limit is not None else getattr(args, "tail", None)
    if head_n is not None and head_n >= 0:
        hist = hist[:head_n] if hist else []
    elif tail_n is not None and tail_n >= 0:
        hist = hist[-tail_n:] if hist else []
    since_seconds = getattr(args, "since", None)
    if since_seconds is not None and since_seconds >= 0:
        cutoff = int(time.time()) - since_seconds
        hist = [row for row in hist if int(row.get("t") or 0) >= cutoff]
    until_seconds = getattr(args, "until", None)
    if until_seconds is not None and until_seconds >= 0:
        # Borrowed from ``git log --until="2024-01-01"``: the
        # upper bound on the time window. ``--since`` keeps the
        # fresh rows; ``--until`` drops the fresh ones. Together
        # they bracket a window, the way the same flags do on
        # ``docker logs``, ``journalctl`` and ``find -newer``.
        cutoff = int(time.time()) - until_seconds
        hist = [row for row in hist if int(row.get("t") or 0) <= cutoff]
    grep_text = getattr(args, "grep", None)
    exclude_text = getattr(args, "exclude", None)
    if grep_text:
        # Borrowed from ``git log --grep``: substring match on the
        # next action, which is the only field a host reads.
        # The match is case-insensitive so the typical
        # ``--grep TODO`` style works the way the borrower does.
        # The substring runs against both ``next`` and the
        # optional ``msg`` field, the way ``git log --grep`` runs
        # against the commit message rather than the diff body.
        needle = grep_text.lower()
        hist = [row for row in hist
                if needle in (row.get("next") or "").lower()
                or needle in (row.get("msg") or "").lower()]
    if exclude_text:
        # Borrowed from ``git log --invert-grep`` /
        # ``find -not -name PATTERN``: a substring that, when
        # present in ``next`` or ``msg``, removes the row from
        # the result set. ``--grep`` and ``--exclude`` compose,
        # the way the two flags do on ``git log``: apply ``--grep``
        # first, then drop anything that matches ``--exclude``.
        needle = exclude_text.lower()
        hist = [row for row in hist
                if needle not in (row.get("next") or "").lower()
                and needle not in (row.get("msg") or "").lower()]
    if getattr(args, "reverse", False):
        # Borrowed from ``git log --reverse``: the default ``history``
        # walks the file in append order (oldest first) because
        # that is the most useful way to read a left-to-right log;
        # ``--reverse`` flips that to newest first, the same way
        # ``git log`` defaults to newest first and ``--reverse``
        # flips it back. Keeping the two flags consistent across
        # the borrowings lets a host that knows ``git log`` know
        # ``history`` too.
        hist = hist[::-1]
    # Borrowed from ``grep -m 1`` / ``ripgrep --max-count=1``:
    # stop after the first matching row, the way a host finds
    # the first time a topic appeared in the audit log. The
    # order is the order of ``hist``: append order by default, or
    # ``--reverse`` to scan from the most recent. ``--count``,
    # ``--quiet`` and ``--json`` honour the truncation: ``--count``
    # always reports the surviving count, ``--json`` lists the
    # surviving rows, ``--quiet`` prints only the surviving
    # next action. The flag only narrows the result set.
    if getattr(args, "row_id", None) is not None:
        # Borrowed from ``git log --skip N -n 1`` /
        # ``jq '.['N-1']'`` / ``sed -n 'Np' file``: return the
        # single row at the 1-based index ``N``, the way
        # ``kubectl get pod -n N`` / ``hm --row N`` /
        # ``pandas.iloc[N-1]`` do. ``--json`` returns a
        # single-row payload; the text path prints the same
        # fields the default table prints, with a ``row N of
        # M`` header. ``--row-id`` must run before the early
        # ``--json`` fall-through, so a host that asks for a
        # single row does not also pay the cost of the full
        # payload.
        try:
            n = int(args.row_id)
        except (TypeError, ValueError):
            print("CANNOT: --row-id expects an integer, got %r"
                  % args.row_id, file=sys.stderr)
            return 2
        if not hist:
            print("── j-space ─ history (no rows)")
            return 0
        if n < 1 or n > len(hist):
            print("CANNOT: --row-id %d out of range (1..%d)"
                  % (n, len(hist)), file=sys.stderr)
            return 2
        row = hist[n - 1]
        if args.json:
            print(json.dumps({
                "row_id": n,
                "row": row,
            }, ensure_ascii=False, indent=2))
            return 0
        print("── j-space ─ history (row %d of %d)" % (n, len(hist)))
        ts = row.get("t")
        when = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                 if ts else "(no timestamp)")
        nxt = row.get("next") or "(empty)"
        verified = row.get("verified", 0)
        opens = row.get("open", 0)
        msg = row.get("msg") or ""
        print("  when:     %s" % when)
        print("  next:     %s" % nxt)
        print("  verified: %d" % verified)
        print("  open:     %d" % opens)
        if msg:
            print("  msg:      %s" % msg)
        return 0
    if getattr(args, "first_match", False):
        hist = hist[:1]
    fields_attr = getattr(args, "fields", None)
    if fields_attr:
        selected = [f.strip() for f in fields_attr.split(",") if f.strip()]
        if not selected:
            selected = ["next"]
    else:
        selected = None
    # Both `--csv` and `--domains` render modes work in text or JSON —
    # they must run before the general `--json` payload is returned so
    # their results can ride the JSON renderer instead of falling back
    # to the plain table.
    if getattr(args, "csv", False):
        # Borrowed from ``aws --output csv`` /
        # ``kubectl get -o csv`` / PowerShell ``ConvertTo-Csv``:
        # emit the history as comma-separated values with a
        # header line and RFC 4180 quoting, so a host can feed
        # it into Excel / pandas / ``csv.reader`` without any
        # parsing. Missing or empty fields render as empty
        # strings, and the row order is the one that other
        # flags picked; ``--csv`` only changes the renderer.
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        cols = selected if selected is not None else ["t", "next", "verified", "open"]
        writer = _csv.writer(buf)
        writer.writerow(cols)
        for row in hist:
            writer.writerow([str(row.get(f, "")) if row.get(f) else "" for f in cols])
        sys.stdout.write(buf.getvalue())
        return 0
    if getattr(args, "domains", False):
        # Borrowed from JIT-Agent's action-diversity analysis: the
        # ``dom:`` prefix of each row's ``next`` action is a topic
        # index; grouping by it shows which domain the session has
        # been spending its seams on, the way the JIT harness
        # factors memory / planning / action / capability. The
        # per-domain count and share let a host see the agent's
        # working-area spread without asking the model to re
        # -derive it. Empty rows (no ``next`` recorded) land in
        # ``(none)``.
        counts = {}
        total = 0
        for row in hist:
            nxt = (row.get("next") or "").strip()
            if not nxt:
                continue
            domain = nxt.split(":", 1)[0].strip().lower() or "(none)"
            counts[domain] = counts.get(domain, 0) + 1
            total += 1
        if not counts:
            if args.json:
                print(json.dumps({"domains": []}, indent=2))
            else:
                print("── j-space ─ history (no rows with a next action)")
            return 0
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if args.json:
            print(json.dumps(
                {
                    "domains": [
                        {"domain": name, "count": count, "share": round(count / total, 4)}
                        for name, count in ranked
                    ],
                },
                indent=2, ensure_ascii=False,
            ))
            return 0
        print("── j-space ─ history (%d domains across %d seams)" % (len(counts), total))
        for name, count in ranked:
            share = count * 100.0 / total
            print("  %-20s  %3d  (%5.1f%%)" % (name, count, share))
        print()
        return 0
    if getattr(args, "span", False):
        # Borrowed from ``git log --stat`` /
        # ``journalctl --list-boots``: a single-line summary of
        # the audit log's time span — first seam, last seam, and
        # the duration between. ``--since`` / ``--grep`` /
        # ``--head`` / ``--tail`` still narrow the window first,
        # so a host can ask "how long did the TODO burst last"
        # with ``--grep TODO --span``. A single-row window has
        # no duration to speak of; the renderer says so.
        if args.json:
            if not hist:
                print(json.dumps({"span": None}, indent=2))
                return 0
            first_t = int(hist[0].get("t") or 0)
            last_t = int(hist[-1].get("t") or 0)
            print(json.dumps({
                "span": {
                    "first": first_t,
                    "last": last_t,
                    "duration_seconds": max(0, last_t - first_t),
                    "rows": len(hist),
                },
            }, indent=2))
            return 0
        if not hist:
            print("── j-space ─ history span (no rows)")
            return 0
        first_t = int(hist[0].get("t") or 0)
        last_t = int(hist[-1].get("t") or 0)
        duration = max(0, last_t - first_t)
        first_when = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(first_t)) if first_t else "(none)"
        last_when = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(last_t)) if last_t else "(none)"
        print("── j-space ─ history span")
        print("  First seam: %s" % first_when)
        print("  Last seam:  %s" % last_when)
        print("  Duration:   %d seconds across %d rows" % (duration, len(hist)))
        return 0
    if getattr(args, "dedup", False) or getattr(args, "dedup_by_msg", False):
        # Borrowed from ``sort -u`` / ``uniq`` /
        # ``awk '!seen[$0]++'``: collapse the surviving rows to
        # the unique values of the chosen field, in the order
        # the rows first appeared, the way ``sort -u`` /
        # ``awk !seen[$0]++`` does. ``--domains`` already groups
        # by the next-action prefix; ``--dedup`` groups by the
        # full next action (so a host that wants ``what distinct
        # things did the session do`` reads it instead of
        # guessing from the count column in ``--domains``);
        # ``--dedup-by-msg`` is the same collapse applied to the
        # ``msg`` annotation, the way ``sort -u -k 2`` collapses
        # by the second field. The two flags share the dedup
        # path: ``--dedup`` keys on ``next``; ``--dedup-by-msg``
        # keys on ``msg``; both are honoured if both are passed.
        # The path runs before the plain ``--json`` renderer so
        # the JSON payload carries the deduped rows too.
        use_msg = getattr(args, "dedup_by_msg", False)
        seen = set()
        deduped = []
        for row in hist:
            if use_msg:
                key = (row.get("msg") or "").strip()
            else:
                key = (row.get("next") or "").strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        if args.json:
            print(json.dumps({
                "history_count": len(hist),
                "unique_count": len(deduped),
                "by": "msg" if use_msg else "next",
                "rows": deduped,
            }, ensure_ascii=False, indent=2))
            return 0
        if use_msg:
            print("── j-space ─ history (%d unique msg annotations across %d rows)"
                  % (len(deduped), len(hist)))
            for index, row in enumerate(deduped, 1):
                msg = row.get("msg") or "(empty)"
                print("  %3d  %s" % (index, msg))
        else:
            print("── j-space ─ history (%d unique next actions across %d rows)"
                  % (len(deduped), len(hist)))
            for index, row in enumerate(deduped, 1):
                nxt = row.get("next") or "(empty)"
                print("  %3d  %s" % (index, nxt))
        return 0
    if getattr(args, "empty", False):
        # Borrowed from ``find -empty`` / ``awk '/^$/'`` /
        # ``grep '^$'`` / ``vacuum mode`` (the latter of
        # ``--vacuum-time`` on ``journalctl``): keep only the
        # rows whose next action is blank. The flag is a
        # post-filter on the existing filter chain, so ``--grep``,
        # ``--since`` and the rest all narrow the candidate set
        # before the empty check runs, the way ``--exclude``
        # does. ``--json`` carries the surviving empty rows;
        # the text path prints one row index per line, the way
        # ``git log --grep='^$'`` does.
        hist = [row for row in hist
                if not (row.get("next") or "").strip()]
        if args.json:
            print(json.dumps({
                "history_count": len(hist),
                "rows": hist,
            }, ensure_ascii=False, indent=2))
            return 0
        if not hist:
            print("── j-space ─ history (no empty-next rows)")
            return 0
        print("── j-space ─ history (%d empty-next rows)" % len(hist))
        for index, row in enumerate(hist, 1):
            when = (time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(row.get("t") or 0))
                if row.get("t") else "(no timestamp)")
            print("  %3d  %s" % (index, when))
        return 0
    if args.json:
        print(json.dumps({
            "history_count": len(hist),
            "limit": args.limit,
            "since": since_seconds,
            "grep": grep_text,
            "reverse": bool(getattr(args, "reverse", False)),
            "rows": list(hist),
        }, ensure_ascii=False, indent=2))
        return 0
    if getattr(args, "quiet", False):
        # Borrowed from ``git log --oneline`` and
        # ``docker logs --quiet``: print only the next action of
        # each row, one per line, with no header, no row number,
        # no other field. A host can pipe the result into
        # ``xargs`` / ``grep`` / ``sort -u`` to build a topic
        # index of what the session actually did, the way
        # ``git log --oneline`` powers a commit title index.
        for row in hist:
            nxt = row.get("next") or ""
            print(nxt)
        return 0
    if getattr(args, "count", False):
        # Borrowed from ``wc -l`` / ``git rev-list --count``:
        # print only the row count. ``--since`` and ``--grep``
        # still apply, so a host can do
        # ``count=$(jspace history --since 3600 --grep TODO --count)``
        # without parsing tables. Exit code stays 0 so a host
        # can compose with ``|| true`` style guards.
        print(len(hist))
        return 0
    fields = getattr(args, "fields", None)
    format_template = getattr(args, "format", None)
    if format_template:
        # Borrowed from ``git log --format='%h %s'`` /
        # ``docker ps --format '{{.Names}}'`` /
        # ``kubectl get -o custom-columns=NAME:.metadata.name``:
        # a per-row template where each ``%X`` placeholder is
        # replaced with the value of field ``X`` for that row.
        # ``%t`` is the timestamp, ``%n`` is the next action
        # (also ``%next`` for symmetry with the other long
        # placeholders), ``%m`` is the message annotation,
        # ``%v`` is the verified count, ``%o`` is the open count,
        # ``%h`` is the row index (1-based, the way ``git log``
        # numbers commits). A literal ``%`` is rendered as
        # ``%%``, the way the standard ``printf`` convention
        # works. The header line is omitted: ``--format`` is the
        # shape-only renderer, borrowed from ``git log --no-header`` /
        # ``docker ps --no-trunc``. ``--csv`` / ``--fields``
        # give the host the header-bearing and comma-bearing
        # forms respectively.
        if args.json:
            rendered = []
            for index, row in enumerate(hist, 1):
                line = format_template
                line = line.replace("%%", "\x00PCT\x00")
                for short, value in (
                    ("t", str(row.get("t") or "-")),
                    ("n", str(row.get("next") or "-")),
                    ("next", str(row.get("next") or "-")),
                    ("m", str(row.get("msg") or "-")),
                    ("v", str(row.get("verified") if row.get("verified") is not None else "-")),
                    ("o", str(row.get("open") if row.get("open") is not None else "-")),
                    ("h", str(index)),
                ):
                    line = line.replace("%" + short, value)
                line = line.replace("%", "")
                line = line.replace("\x00PCT\x00", "%")
                rendered.append(line)
            print(json.dumps({
                "history_count": len(hist),
                "format": format_template,
                "lines": rendered,
            }, ensure_ascii=False, indent=2))
            return 0
        for index, row in enumerate(hist, 1):
            line = format_template
            line = line.replace("%%", "\x00PCT\x00")
            for short, value in (
                ("t", str(row.get("t") or "-")),
                ("n", str(row.get("next") or "-")),
                ("next", str(row.get("next") or "-")),
                ("m", str(row.get("msg") or "-")),
                ("v", str(row.get("verified") if row.get("verified") is not None else "-")),
                ("o", str(row.get("open") if row.get("open") is not None else "-")),
                ("h", str(index)),
            ):
                line = line.replace("%" + short, value)
            line = line.replace("%", "")
            line = line.replace("\x00PCT\x00", "%")
            print(line)
        return 0
    if fields:
        # Borrowed from ``docker ps --format '{{.Names}}'`` /
        # ``kubectl get -o custom-columns=NAME:.metadata.name`` /
        # ``aws --query 'Reservations[].Instances[].InstanceId'``:
        # a comma-separated list of history fields prints only
        # those fields and nothing else, separated by tabs the
        # way ``--format`` / ``-o``-style renderers do. The
        # header line names the columns so a host piping into
        # ``awk '{print $1}'`` or ``column -t`` can pick a
        # column by name. Missing or empty fields render as
        # ``-`` so the columns line up.
        selected = [f.strip() for f in fields.split(",") if f.strip()]
        if not selected:
            selected = ["next"]
        print("\t".join(selected))
        for row in hist:
            cells = []
            for f in selected:
                value = row.get(f)
                cells.append(str(value) if value else "-")
            print("\t".join(cells))
        return 0
    if getattr(args, "dedup", False) or getattr(args, "dedup_by_msg", False):
        # Borrowed from ``git log --skip N -n 1`` /
        # ``jq '.['N-1']'`` / ``sed -n 'Np' file``: return the
        # single row at the 1-based index ``N``, the way
        # ``kubectl get pod -n N`` / ``hm --row N`` /
        # ``pandas.iloc[N-1]`` do. ``--json`` returns a single-row
        # payload; the text path prints the same fields the
        # default table prints, with a ``Row N:`` header so a
        # host can grep the row out of the output. The
        # 1-based numbering matches the table index the table
        # path already shows.
        try:
            n = int(args.row_id)
        except (TypeError, ValueError):
            print("CANNOT: --row-id expects an integer, got %r"
                  % args.row_id, file=sys.stderr)
            return 2
        if not hist:
            print("── j-space ─ history (no rows)")
            return 0
        if n < 1 or n > len(hist):
            print("CANNOT: --row-id %d out of range (1..%d)"
                  % (n, len(hist)), file=sys.stderr)
            return 2
        row = hist[n - 1]
        if args.json:
            print(json.dumps({
                "row_id": n,
                "row": row,
            }, ensure_ascii=False, indent=2))
            return 0
        print("── j-space ─ history (row %d of %d)" % (n, len(hist)))
        ts = row.get("t")
        when = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                 if ts else "(no timestamp)")
        nxt = row.get("next") or "(empty)"
        verified = row.get("verified", 0)
        opens = row.get("open", 0)
        msg = row.get("msg") or ""
        print("  when:     %s" % when)
        print("  next:     %s" % nxt)
        print("  verified: %d" % verified)
        print("  open:     %d" % opens)
        if msg:
            print("  msg:      %s" % msg)
        return 0
    label = "── j-space ─ history (%d entries" % len(hist)
    if since_seconds is not None and since_seconds >= 0:
        label += ", last %d s" % since_seconds
    if grep_text:
        label += ", grep %r" % grep_text
    if getattr(args, "reverse", False):
        label += ", newest first"
    print(label + ")")
    for index, row in enumerate(hist, 1):
        ts = row.get("t")
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) \
            if ts else "(no timestamp)"
        nxt = row.get("next") or "(empty)"
        verified = row.get("verified", 0)
        opens = row.get("open", 0)
        print("  %3d  %s  v=%d o=%d  %s" % (index, when, verified, opens, nxt))
    return 0


def mode_info(book, json_flag=False, warnings_only=False,
              version_only=False, human=False, check_only=False,
              memory_only=False, list_fields=False):
    """Print or emit a digest of the workspace state.

    Borrowed from the ``gh repo view`` / ``kubectl cluster-info`` /
    ``cargo metadata`` pattern: an aggregate read-only subcommand that
    lets a host or human inspect controller state without taking a
    seam's side effects. Text mode prints a short sectioned report; the
    ``--json`` flag emits a machine-readable payload that mirrors the
    text one for one, just as ``seam --json`` does. ``--warnings-only``
    borrows ``gh run list --state failed`` /
    ``kubectl get --field-selector status=Failed`` / the
    ``docker ps --filter`` family — print only the warning lines, the
    way a CI hook would when it just wants to know whether the
    workspace is healthy enough to advance.
    """
    hist = read_history()
    goal = one(book, "Goal")
    nxt = one(book, "Next")
    last_seam_t = hist[-1]["t"] if hist else None
    now = int(time.time())
    gap_seconds = (now - last_seam_t) if last_seam_t is not None else None
    payload = {
        "ledger": {
            "goal": goal or None,
            "core_count": len(book.get("Core", [])),
            "verified_count": len(book.get("Verified", [])),
            "open_count": len(book.get("Open", [])),
            "next": nxt or None,
        },
        "history_count": len(hist),
        "last_seam": {
            "t": last_seam_t,
            "gap_seconds": gap_seconds,
            "long_gap": bool(gap_seconds is not None and gap_seconds > RESUME_GAP),
        },
        "warnings": _info_warnings(book, hist, gap_seconds),
    }
    if human:
        # Borrowed from ``df -h`` / ``du -h`` / ``ls -lh`` /
        # ``git log --relative-date``: time spans render in
        # human-readable units (``2 minutes ago``) instead of
        # raw seconds (``120 seconds``). The JSON path keeps the
        # raw number so a host can still compute against it.
        payload["human"] = {
            "gap_seconds": gap_seconds,
            "gap_human": _humanize_seconds(gap_seconds) if gap_seconds is not None else None,
            "long_gap": bool(gap_seconds is not None and gap_seconds > RESUME_GAP),
        }
    if warnings_only:
        # The ``--warnings-only`` path is independent of ``--json``:
        # a host can ask for ``--json --warnings-only`` and the JSON
        # payload still contains the full key set, with the warning
        # list — the flag only trims the text renderer. Below, we
        # keep both code paths identical except for the text
        # shortening.
        if json_flag:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        for warning in payload["warnings"]:
            print("Warning: " + warning)
        return 0
    if version_only:
        # Borrowed from ``gh --version`` / ``kubectl version`` /
        # ``aws --version`` / ``git --version``: print the
        # controller's version on its own line so a host can grep
        # it, pipe it into ``cut`` or capture it. ``--json`` is
        # an alternative face for the same field, the way the
        # other subcommands expose it.
        if json_flag:
            print(json.dumps({"version": __version__}, indent=2))
            return 0
        print("jspace " + __version__)
        return 0
    if check_only:
        # Borrowed from ``git fsck`` / ``npm doctor`` /
        # ``cargo check``: a structural health report on the
        # ledger, with the issues classified rather than
        # silently repaired. ``read_history`` already auto-fixes
        # invalid rows during reads; ``--check`` is the
        # read-only counterpart that surfaces the issues
        # without touching them, the way ``git fsck --no-reflog``
        # / ``docker system df`` / ``aws health describe-events``
        # surface problems a host can act on. The exit code
        # is 0 only if the ledger passes; otherwise 2, the
        # same code ``jspace ship --strict`` uses to turn a
        # report into a gate.
        issues = _info_check_issues(book, hist, gap_seconds)
        if json_flag:
            print(json.dumps({
                "valid": not issues,
                "issues": issues,
            }, indent=2, ensure_ascii=False))
            return 0 if not issues else 2
        if not issues:
            print("── j-space ─ info check")
            print("  ledger: ok")
            return 0
        print("── j-space ─ info check")
        for issue in issues:
            print("  - " + issue)
        return 2
    if memory_only:
        # Borrowed from ``free -m`` / ``du -h`` / ``ls -lh`` /
        # ``docker system df`` / ``npm view size``: render the
        # workspace size on disk in human-readable units. The
        # text path picks the largest unit that produces a
        # value >= 1, the way ``ls -lh`` does. ``--json``
        # exposes both the raw byte count and the human form.
        workspace_path = LEDGER_DIR
        if os.path.isfile(LEDGER):
            workspace_path = os.path.dirname(LEDGER) or "."
        if not os.path.isdir(workspace_path):
            size_bytes = 0
        else:
            size_bytes = 0
            for dirpath, dirnames, filenames in os.walk(workspace_path):
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    try:
                        size_bytes += os.path.getsize(path)
                    except OSError:
                        pass
        size_human = _humanize_bytes(size_bytes)
        if json_flag:
            print(json.dumps({
                "workspace": os.path.abspath(workspace_path),
                "bytes": size_bytes,
                "human": size_human,
            }, indent=2, ensure_ascii=False))
            return 0
        print("── j-space ─ info memory")
        print("  workspace: %s" % os.path.abspath(workspace_path))
        print("  size:      %s (%d bytes)" % (size_human, size_bytes))
        return 0
    if list_fields:
        # Borrowed from ``kubectl explain`` / ``gh repo view
        # --json fields`` / ``man page``: a self-describing
        # schema for the ledger, so a host or human can
        # introspect what ``info`` / ``history`` / ``seam`` will
        # produce without reading the source. The text path
        # mirrors the JSON path: both expose the same section
        # names and field names, so a host that builds a
        # consumer off either face gets the same vocabulary.
        schema = {
            "ledger": {
                "goal": "the one-sentence definition of done",
                "core": "two-line live hub entries, the rest parked",
                "verified": "appended numbered checkpoints",
                "open": "questions that still need settling",
                "next": "the next action the model is going to take",
            },
            "history_row": {
                "t": "epoch seconds when the seam was appended",
                "next": "the next action that the model picked",
                "verified": "count of verified checkpoints at that seam",
                "open": "count of open questions at that seam",
                "msg": "optional annotation, the way git commit -m adds a message",
            },
            "info_payload": {
                "ledger": "the ledger section above",
                "history_count": "number of rows in history.json",
                "last_seam.t": "epoch seconds of the most recent seam",
                "last_seam.gap_seconds": "seconds since that seam, or null",
                "last_seam.long_gap": "true if gap > RESUME_GAP",
                "warnings": "list of human-meaningful alert lines",
            },
        }
        if json_flag:
            print(json.dumps(schema, indent=2, ensure_ascii=False))
            return 0
        for section, fields in schema.items():
            print("── j-space ─ info %s" % section)
            for name, doc in fields.items():
                print("  %-22s  %s" % (name, doc))
        return 0
    if json_flag:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("── j-space ─ info")
    print()
    print("Version:   " + __version__)
    print()
    print("Ledger:")
    print("  Goal:     %s" % (goal or "(not set)"))
    print("  Core:     %d" % payload["ledger"]["core_count"])
    print("  Verified: %d" % payload["ledger"]["verified_count"])
    print("  Open:     %d" % payload["ledger"]["open_count"])
    print("  Next:     %s" % (nxt or "(not set)"))
    print()
    print("History: %d entries" % len(hist))
    if last_seam_t is None:
        print("Last seam: never")
    else:
        gap_label = _humanize_seconds(gap_seconds) if human else (
            "%d seconds" % gap_seconds)
        long_gap_label = " (long gap)" if gap_seconds > RESUME_GAP else ""
        print("Last seam: %s ago%s" % (gap_label, long_gap_label))
    for warning in payload["warnings"]:
        print()
        print("Warning: " + warning)
    return 0


def _info_warnings(book, hist, gap_seconds):
    """Collect the human-meaningful alerts the ``info`` digest surfaces.

    Kept separate from the renderer so the JSON payload can carry the
    same list, and so adding a new warning is a one-liner instead of a
    branch in the text path.
    """
    out = []
    if not one(book, "Goal"):
        out.append("no goal set — open a ledger with `note --goal ... --next ...`")
    if not one(book, "Next"):
        out.append("next action is not set")
    if not hist:
        out.append("no seams recorded yet — the first seam will populate the digest")
    elif gap_seconds is not None and gap_seconds > RESUME_GAP:
        out.append("last seam is older than the resume gap (run `resume`)")
    return out


def mode_note(book, args):
    """Apply valid edits; decline malformed ones without dropping independent edits.

    Initial creation is atomic because Goal and Next are both required. After that,
    a declined independent edit must not cost an accepted one, or mixed calls never
    converge.
    """
    changed = False
    refused = []
    invalid = set()

    for name, flag in (
        ("goal", "--goal"),
        ("core", "--core"),
        ("next", "--next"),
        ("check", "--check"),
        ("by", "--by"),
        ("open", "--open"),
        ("settled_by", "--settled-by"),
    ):
        value, problem = clean_scalar(getattr(args, name))
        if value is not None and not problem and name in ("goal", "next") and value.startswith("## "):
            problem = "must not begin with a ledger section heading ('## ')"
            value = None
        setattr(args, name, value)
        if problem:
            invalid.add(name)
            refused.append(("%s %s." % (flag, problem), "%s \"one-line value\"" % flag))

    if not (one(book, "Goal") or args.goal) or not (one(book, "Next") or args.next):
        refused.append(
            (
                "opening the ledger requires both Goal and Next.",
                'note --goal "what done means" --next "the first action"',
            )
        )
        for message, fix in refused:
            declined(message, fix)
        return 2

    if args.goal:
        book["Goal"] = [args.goal]
        changed = True

    if args.core:
        if "—" not in args.core and " - " not in args.core:
            refused.append(
                (
                    "Mentioning is not loading.",
                    '--core "name — the one fact that makes it matter"',
                )
            )
        elif args.core_slot is None:
            if args.core not in book["Core"]:
                book["Core"].append(args.core)
                changed = True
        else:
            live = book["Core"][:2]
            parked = book["Core"][2:]
            idx = args.core_slot - 1
            if idx > len(live):
                refused.append(
                    (
                        "live core slot %d does not exist." % args.core_slot,
                        "use the next available slot or add the entry without --core-slot",
                    )
                )
            elif args.core in live and (idx >= len(live) or live[idx] != args.core):
                refused.append(
                    ("that core entry is already live.", "choose the slot that should actually change")
                )
            elif idx == len(live):
                live.append(args.core)
                book["Core"] = live + parked
                changed = True
            else:
                displaced = live[idx]
                live[idx] = args.core
                parked = [row for row in parked if row != args.core]
                if displaced != args.core:
                    parked.insert(0, displaced)
                book["Core"] = live + parked
                changed = changed or displaced != args.core
    elif args.core_slot is not None:
        refused.append(("--core-slot requires --core.", '--core "name — defining fact" --core-slot 1'))

    check_recorded = False
    check_index = None
    if args.check:
        if not args.by:
            refused.append(
                (
                    INVARIANTS[4],
                    '--check "what now holds" --by "what verified it"',
                )
            )
        elif RESERVED_CLOSE_SUFFIX.search(args.by):
            refused.append(
                (
                    "checkpoint evidence ends with the controller-reserved closure suffix.",
                    "remove `— closes: ?NN`; the controller records it only after --close succeeds",
                )
            )
        elif not COVERAGE.search(args.by):
            refused.append(
                (
                    INVARIANTS[5],
                    '--by "brute force, n ≤ 6, including empty and maximum"',
                )
            )
        else:
            num = next_number(book["Verified"], "✓")
            book["Verified"].append(
                "✓%02d %s — verified by: %s" % (num, args.check, args.by)
            )
            check_index = len(book["Verified"]) - 1
            changed = True
            check_recorded = True
    else:
        if args.by and "check" not in invalid:
            refused.append(("--by requires --check.", '--check "what now holds" --by "verifier and coverage"'))

    if args.open:
        settle = args.settled_by or ""
        if not settle:
            refused.append(
                (
                    "an open question with nothing that would settle it cannot be closed.",
                    '--open "the question" --settled-by "the cheapest test that could refute it"',
                )
            )
        else:
            num = next_open_number(book)
            book["Open"].append("?%02d %s — settled by: %s" % (num, args.open, settle))
            changed = True
    elif args.settled_by and "open" not in invalid:
        refused.append(("--settled-by requires --open.", '--open "question" --settled-by "test"'))

    if args.close is not None:
        rows = book["Open"]
        target = "?%02d" % args.close
        idx = next((i for i, row in enumerate(rows) if row.startswith(target + " ")), None)
        if idx is None:
            refused.append(
                ("no open question numbered %d." % args.close, "run `resume` to see the full list")
            )
        elif not check_recorded:
            refused.append(
                (
                    "An `Open` entry closes only against a recorded checkpoint, and its number is never reused.",
                    '--close %d --check "what now holds" --by "verifier and coverage"' % args.close,
                )
            )
        else:
            rows.pop(idx)
            book["Verified"][check_index] += " — closes: " + target
            changed = True

    if args.next:
        book["Next"] = [args.next]
        changed = True

    if changed:
        problem = write_ledger(book)
        if problem:
            print("CANNOT: cannot write the ledger — " + problem)
            print("  No filesystem? The ledger lives in the conversation. Restate the five lines")
            print("  at each seam. Same discipline, different medium.")
            return 2
    for message, fix in refused:
        declined(message, fix)
    if refused:
        if changed:
            print("  (everything else in this call was recorded.)")
        return 2
    print_ledger(book)
    return 0


def markdown_fenced_lines(lines):
    """Return zero-based lines inside Markdown fenced code blocks, including their fences."""
    fenced = set()
    fence_char = None
    fence_size = 0
    for index, line in enumerate(lines):
        if fence_char is None:
            match = MARKDOWN_FENCE.match(line)
            if not match:
                continue
            token = match.group(1)
            fence_char = token[0]
            fence_size = len(token)
            fenced.add(index)
            continue

        fenced.add(index)
        closing = r"^\s{0,3}%s{%d,}\s*$" % (re.escape(fence_char), fence_size)
        if re.match(closing, line):
            fence_char = None
            fence_size = 0
    return fenced


def markdown_structural_lines(lines):
    """Return zero-based lines whose words are Markdown structure, not prose claims."""
    structural = markdown_fenced_lines(lines)
    for index, line in enumerate(lines):
        if index in structural:
            continue
        if MARKDOWN_HEADING.match(line) or THEMATIC_BREAK.match(line):
            structural.add(index)
        if (
            index + 1 < len(lines)
            and index + 1 not in structural
            and line.strip()
            and SETEXT_UNDERLINE.match(lines[index + 1])
        ):
            structural.update((index, index + 1))
        if TABLE_DELIMITER.match(line):
            start = index - 1
            while (
                start >= 0
                and start not in structural
                and lines[start].strip()
                and "|" in lines[start]
            ):
                structural.add(start)
                start -= 1
            end = index
            while (
                end < len(lines)
                and end not in structural
                and lines[end].strip()
                and "|" in lines[end]
            ):
                structural.add(end)
                end += 1
    return structural


def claim_without_coverage(lines):
    """Return the first uncovered claim line, joining soft-wrapped paragraphs."""
    structural = markdown_structural_lines(lines)

    paragraph = []

    def flush():
        if not paragraph:
            return None
        joined = " ".join(line.strip() for _, line in paragraph)
        if not CLAIM.search(joined) or COVERAGE.search(joined):
            return None
        return next(number for number, line in paragraph if CLAIM.search(line))

    for index, line in enumerate(lines):
        stripped = line.strip()
        if (
            not stripped
            or index in structural
        ):
            uncovered = flush()
            if uncovered:
                return uncovered
            paragraph = []
            continue

        if MARKDOWN_LIST_ITEM.match(line):
            uncovered = flush()
            if uncovered:
                return uncovered
            paragraph = [(index + 1, line)]
        elif "|" in line:
            uncovered = flush()
            if uncovered:
                return uncovered
            paragraph = [(index + 1, line)]
            uncovered = flush()
            if uncovered:
                return uncovered
            paragraph = []
        else:
            paragraph.append((index + 1, line))

    return flush()


def mode_ship(text, strict=False):
    """Report inner-register leakage in outgoing text.

    A report, not a gate by default: it exits 0 whether or not it finds
    anything, because the caller asked it to look and it looked. With
    ``--strict``, the exit code mirrors the ESLint ``--max-warnings`` /
    RuboCop ``Lint/`` / myPy ``--strict`` convention: a non-zero exit
    on the first finding turns the report into an enforcement gate,
    which is the right behaviour for CI hooks and pre-commit
    pipelines that should refuse to ship a register leak.
    """
    findings = []
    lines = text.splitlines()
    structural = markdown_structural_lines(lines)
    prose = "\n".join(line for index, line in enumerate(lines) if index not in structural)

    leaked = sorted({s for s in INNER_ONLY if s in prose})
    if leaked:
        findings.append(INVARIANTS[6] + " Found: " + " ".join(leaked))

    hot = sorted({m for m in MARKERS if m.lower() in prose.lower()})
    if hot:
        findings.append("state markers in outgoing text: " + ", ".join(hot))

    uncovered = claim_without_coverage(lines)
    if uncovered:
        findings.append("line %d: %s" % (uncovered, INVARIANTS[5]))

    run = 1
    for index, (a, b) in enumerate(zip(lines, lines[1:])):
        if index in structural or index + 1 in structural:
            run = 1
            continue
        run = run + 1 if a.strip() and a.strip() == b.strip() else 1
        if run >= 3:
            findings.append("repetition loop: a line repeats three times or more")
            break

    for index, line in enumerate(lines):
        if index not in structural and re.search(r"([.…\-'])\1{20,}", line):
            findings.append("repetition loop: a character run of 20 or more")
            break

    if not findings:
        print("clean — the outgoing register holds.")
        return 0
    print("── j-space ─ ship")
    for f in findings[:7]:
        print("· " + f)
    print()
    print("Expand the whole span into clean language before it ships. The switch is total, never cosmetic.")
    if strict:
        # Match the exit code 2 used everywhere else for "could not do
        # what was asked" — the leak was found, so shipping failed.
        return 2
    return 0


def decode_outgoing(data, label):
    """Decode outgoing bytes without silently accepting an unknown encoding."""
    try:
        if data.startswith(codecs.BOM_UTF8):
            text = data.decode("utf-8-sig")
        elif data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            text = data.decode("utf-32")
        elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            text = data.decode("utf-16")
        else:
            text = data.decode("utf-8")
            if "\x00" in text:
                raise UnicodeError("NUL bytes suggest an unsupported encoding")
    except UnicodeError as exc:
        return None, "%s (cannot decode safely: %s)" % (label, exc)
    return text, None


def read_outgoing(path):
    """Read and decode outgoing text from a file."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return None, "%s (%s)" % (path, exc.strerror or "unreadable")
    return decode_outgoing(data, path)


def configure_streams():
    """Keep controller output deterministic on Windows consoles and redirected streams."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


# --------------------------------------------------------------------------- main


def main(argv=None):
    """Parse the subcommand and run it. Returns the process exit code."""
    configure_streams()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sm = sub.add_parser("seam", help="the ledger, and what has and has not moved")
    sm.add_argument("--json", action="store_true",
                    help="emit machine-readable output for the discoverability layer")
    sm.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="run the analysis without appending to history.json (like terraform plan)")
    sm.add_argument("--quiet", dest="quiet", action="store_true",
                    help="suppress banner, ledger, telemetry, trend, remediation and heal; print only the observation facts (like pytest -q)")
    sm.add_argument("--message", "--msg", dest="message", default=None,
                    help="attach a human-meaningful annotation to the recorded row (like git commit -m / kubectl annotate)")
    sm.add_argument("--from-stdin", dest="from_stdin", action="store_true",
                    help="read one next action per line from standard input (like kubectl apply -f - / xargs)")
    sub.add_parser("resume", help="premise, invariants and full ledger, after a gap")

    n = sub.add_parser("note", help="record something in the ledger")
    n.add_argument("--goal")
    n.add_argument("--core")
    n.add_argument("--core-slot", dest="core_slot", type=int, choices=(1, 2))
    n.add_argument("--next")
    n.add_argument("--check")
    n.add_argument("--memory")
    n.add_argument("--by")
    n.add_argument("--open")
    n.add_argument("--settled-by", dest="settled_by")
    n.add_argument("--close", type=int)

    s = sub.add_parser("ship", help="register check on anything about to leave")
    s.add_argument("file", help="path, or - for stdin")
    s.add_argument("--strict", action="store_true",
                   help="exit non-zero when a finding is reported (CI gate)")

    info_p = sub.add_parser(
        "info", help="print an aggregate digest of the workspace state")
    info_p.add_argument(
        "--json", action="store_true",
        help="emit machine-readable output for the discoverability layer")
    info_p.add_argument(
        "--warnings-only", dest="warnings_only", action="store_true",
        help="print only the warning lines (like gh run list --state failed)")
    info_p.add_argument(
        "--version", dest="version_only", action="store_true",
        help="print the controller version on its own (like gh --version / kubectl version)")
    info_p.add_argument(
        "--human", dest="human", action="store_true",
        help="render time spans in human-readable units (like df -h / git log --relative-date)")
    info_p.add_argument(
        "--check", dest="check_only", action="store_true",
        help="report ledger health issues without repairing (like git fsck, exit 2 on issues)")
    info_p.add_argument(
        "--memory", dest="memory_only", action="store_true",
        help="report workspace disk size in human units (like free -m / du -h / docker system df)")
    info_p.add_argument(
        "--list-fields", dest="list_fields", action="store_true",
        help="describe the ledger schema (like kubectl explain / man page)")

    hist_p = sub.add_parser(
        "history", help="tail the seam audit log")
    hist_p.add_argument(
        "-n", "--limit", dest="limit", type=int, default=None,
        help="print only the most recent N entries (alias of --tail, like git log -n)")
    hist_p.add_argument(
        "--tail", dest="tail", type=int, default=None,
        help="print only the most recent N entries (like tail -n N)")
    hist_p.add_argument(
        "--head", dest="head", type=int, default=None,
        help="print only the first N entries (like head -n N)")
    hist_p.add_argument(
        "--json", action="store_true",
        help="emit machine-readable output for the discoverability layer")
    hist_p.add_argument(
        "--reverse", action="store_true",
        help="show oldest first (like git log --reverse), default is newest first")
    hist_p.add_argument(
        "--since", dest="since", type=int, default=None,
        help="keep only rows from the last N seconds (like docker logs --since 30m)")
    hist_p.add_argument(
        "--grep", dest="grep", default=None,
        help="keep only rows whose next action contains TEXT (like git log --grep)")
    hist_p.add_argument(
        "--exclude", dest="exclude", default=None,
        help="drop rows whose next action or msg contains TEXT (like git log --invert-grep)")
    hist_p.add_argument(
        "--until", dest="until", type=int, default=None,
        help="drop rows newer than N seconds ago (like git log --until, the upper bound on --since)")
    hist_p.add_argument(
        "--keep", dest="keep", type=int, default=None,
        help="discard rows older than the last N and persist the slimmed history (like logrotate --keep, docker system prune)")
    hist_p.add_argument(
        "--dedup", dest="dedup", action="store_true",
        help="collapse the surviving rows to unique next actions (like sort -u / uniq)")
    hist_p.add_argument(
        "--dedup-by-msg", dest="dedup_by_msg", action="store_true",
        help="collapse the surviving rows to unique msg annotations (like sort -u -k 2)")
    hist_p.add_argument(
        "--row-id", dest="row_id", default=None,
        help="return the single row at the 1-based index N (like git log --skip N -n 1 / sed -n 'Np')")
    hist_p.add_argument(
        "--empty", dest="empty", action="store_true",
        help="keep only the rows whose next action is blank (like find -empty / awk '/^$/')")
    hist_p.add_argument(
        "--quiet", dest="quiet", action="store_true",
        help="print only the next action of each row, one per line (like git log --oneline)")
    hist_p.add_argument(
        "-c", "--count", dest="count", action="store_true",
        help="print only the row count (like wc -l, like git rev-list --count)")
    hist_p.add_argument(
        "--first-match", dest="first_match", action="store_true",
        help="stop after the first matching row (like grep -m 1 / ripgrep --max-count=1)")
    hist_p.add_argument(
        "--fields", dest="fields", default=None,
        help="comma-separated list of history fields to print (like docker ps --format)")
    hist_p.add_argument(
        "--format", dest="format", default=None,
        help=("per-row template where placeholders are replaced with "
              "the row fields. Available placeholders: "
              "%%t (timestamp), %%n (next action), %%m (message), "
              "%%v (verified count), %%o (open count), "
              "%%h (row index, 1-based). "
              "Example: '%%t %%n' (like git log --format='%%h %%s')."))
    hist_p.add_argument(
        "--csv", dest="csv", action="store_true",
        help="emit history as CSV (like aws --output csv, PowerShell ConvertTo-Csv)")
    hist_p.add_argument(
        "--domains", dest="domains", action="store_true",
        help="group history by next-action domain prefix, the way JIT-Agent factors memory/planning/action/capability")
    hist_p.add_argument(
        "--span", dest="span", action="store_true",
        help="print the first-seam, last-seam and duration of the window (like git log --stat / journalctl --list-boots)")

    args = p.parse_args(argv)

    if args.cmd == "ship":
        if args.file == "-":
            try:
                stream = getattr(sys.stdin, "buffer", None)
                data = stream.read() if stream is not None else sys.stdin.read().encode("utf-8")
            except OSError as exc:
                text, problem = None, "stdin (%s)" % (exc.strerror or "unreadable")
            else:
                text, problem = decode_outgoing(data, "stdin")
        else:
            text, problem = read_outgoing(args.file)
        if problem:
            print("CANNOT: " + problem + ".")
            print("  pass a readable file, or - to read stdin")
            return 2
        return mode_ship(text, strict=getattr(args, "strict", False))

    try:
        book = read_ledger()
    except LedgerReadError as exc:
        print("CANNOT: ledger was unreadable — %s." % exc)
        print("  repair or remove .jspace/WORKSPACE.md before recording more state")
        return 2
    if args.cmd == "seam":
        return mode_seam(
            book,
            json_flag=getattr(args, "json", False),
            dry_run=getattr(args, "dry_run", False),
            quiet=getattr(args, "quiet", False),
            message=getattr(args, "message", None),
            from_stdin=getattr(args, "from_stdin", False),
        )
    if args.cmd == "resume":
        return mode_resume(book)
    if args.cmd == "info":
        return mode_info(
            book,
            json_flag=getattr(args, "json", False),
            warnings_only=getattr(args, "warnings_only", False),
            version_only=getattr(args, "version_only", False),
            human=getattr(args, "human", False),
            check_only=getattr(args, "check_only", False),
            memory_only=getattr(args, "memory_only", False),
            list_fields=getattr(args, "list_fields", False),
        )
    if args.cmd == "history":
        return mode_history(args)
    return mode_note(book, args)


if __name__ == "__main__":
    sys.exit(main())
