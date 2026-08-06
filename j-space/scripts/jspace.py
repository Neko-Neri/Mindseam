#!/usr/bin/env python3
"""jspace — an instrument for the J-Space skill.

It knows one thing you cannot know accurately: what state you were in a few seams
ago. It keeps that record and hands it back. It decides nothing, and it blocks
nothing.

    jspace.py seam                          the ledger, and what has and has not moved
    jspace.py note --next "..."             set the single next action
    jspace.py note --goal "..."             set what done means
    jspace.py note --core "name — one fact" add a hub entry
    jspace.py note --check "..." --by "..." append a numbered verified checkpoint
    jspace.py note --open "..." --settled-by "..."   add an open question
    jspace.py note --close 2                resolve open question 2
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
import json
import os
import re
import sys
import time

LEDGER_DIR = ".jspace"
LEDGER = os.path.join(LEDGER_DIR, "WORKSPACE.md")
HISTORY = os.path.join(LEDGER_DIR, "history.json")
SECTIONS = ("Goal", "Core", "Verified", "Open", "Next")

STALL_RUN = 3          # consecutive seams before a pattern is worth reporting
RESUME_GAP = 1800      # seconds after which a seam prints the fuller anchor

PREMISE = (
    "You do not only produce words; you also think them before — and without —\n"
    "saying them. The J-space holds what you are poised to say: concepts you can\n"
    "report on demand, hold in mind deliberately, reason with silently, and\n"
    "broadcast to many downstream computations at once. Dense on the inside,\n"
    "decodable on demand."
)

INVARIANTS = [
    "A marker fired and its move never happened — or it happened and you never settled.",
    "A sweep ran and found nothing — again.",
    "A dense line cannot be expanded back into plain words on request.",
    "Every confidence tag this session has been the same tag.",
    "A checkpoint was declared and nothing was written down.",
    "Something was called verified without stating what it covered.",
    "Dense notation appears in something a person or a tool reads.",
    "You called the task finished without reading the goal back line by line.",
]

SHIFTS = "shift the abstraction, shift the strategy, or go and measure"

# Notation that belongs to the inner register and nowhere a person reads.
# Deliberately excludes ✓ ✗ √: they are ordinary in checklists and summaries, and
# stripping them from good writing costs more than the leak they would catch.
INNER_ONLY = ["⇒", "⟹", "⟸", "∴", "∵", "⊆", "⊇", "∋", "??", "?!", "💀"]
MARKERS = ["GRRR", "GAAAH", "PHEW", "I see meltdown", "DATA DATA", "I'M DROWNING"]
CLAIM = re.compile(r"\b(verified|confirmed|validated|tested|proven)\b", re.I)
COVERAGE = re.compile(
    r"\b(on|for|across|over|covering|cases?|sample|inputs?|n\s*[<≤=]|up to|edge|random)\b",
    re.I,
)


# ------------------------------------------------------------------------- ledger


def read_ledger():
    book = {k: [] for k in SECTIONS}
    if not os.path.exists(LEDGER):
        return book
    current = None
    for line in open(LEDGER, encoding="utf-8").read().splitlines():
        head = line.strip()
        if head.startswith("## "):
            name = head[3:].strip()
            current = name if name in book else None
            continue
        if current and head:
            book[current].append(head.lstrip("- ").rstrip())
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


def write_ledger(book):
    problem = ensure_dir()
    if problem:
        return problem
    out = ["# J-Space Workspace Ledger", ""]
    for name in SECTIONS:
        out.append("## " + name)
        rows = book[name]
        if name in ("Goal", "Next"):
            out.append(rows[0] if rows else "")
        else:
            out.extend("- " + r for r in rows)
        out.append("")
    try:
        with open(LEDGER, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out).rstrip() + "\n")
    except OSError as exc:
        return "%s (%s)" % (LEDGER, exc.strerror or "cannot write")
    return None


def one(book, key):
    return book[key][0] if book[key] else ""


def declined(message, fix):
    print("NOT RECORDED: " + message)
    print("  " + fix)
    return 2


# ------------------------------------------------------------------------ history


def read_history():
    if not os.path.exists(HISTORY):
        return []
    try:
        return json.load(open(HISTORY, encoding="utf-8"))
    except (ValueError, OSError):
        return []


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
    if ensure_dir() is None:
        try:
            with open(HISTORY, "w", encoding="utf-8") as fh:
                json.dump(hist, fh)
        except OSError:
            pass  # the record is a convenience; losing it must not stop the work
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
        found.append("Open questions have grown at every seam and none has closed.")
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
    for row in book["Open"][:2]:
        print("Open:     " + row)
    print("Next:     " + (one(book, "Next") or "(not set)"))


def mode_seam(book):
    hist = read_history()
    gap = int(time.time()) - hist[-1]["t"] if hist else 0
    if gap > RESUME_GAP:
        print("── j-space ─ seam (long gap: %d minutes since the last one)" % (gap // 60))
        print(PREMISE)
        print()
    else:
        print("── j-space ─ seam")
    print_ledger(book)
    hist = append_history(book)
    found = observations(hist)
    if found:
        print()
        for f in found:
            print("· " + f)
        print()
        print("You would not have noticed that; I keep the record, so here it is.")
        print("If that is depth, carry on. If it is a stall, the moves open to you are:")
        print("  " + SHIFTS + ".")
    if not one(book, "Next"):
        print()
        print("There is no next action recorded. The ledger stops being state at that point.")
    return 0


def mode_resume(book):
    print("── j-space ─ resume")
    print(PREMISE)
    print()
    print_ledger(book)
    if len(book["Verified"]) > 1:
        print()
        print("Full verified record:")
        for row in book["Verified"]:
            print("  " + row)
    if book["Open"]:
        print()
        print("Still open:")
        for row in book["Open"]:
            print("  " + row)
    print()
    print("Not working if:")
    for n, text in enumerate(INVARIANTS, 1):
        print("  %d. %s" % (n, text))
    append_history(book)
    return 0


def mode_note(book, args):
    """Apply every valid edit; decline the malformed ones without dropping the rest.

    No early return. A declined edit must never cost you an accepted one, or the
    same call gets retried forever and never converges.
    """
    changed = False
    refused = []

    if args.goal:
        book["Goal"] = [args.goal.strip()]
        changed = True

    if args.core:
        if "—" not in args.core and " - " not in args.core:
            refused.append(
                (
                    "a core entry without its defining fact is a mention, not a load.",
                    '--core "name — the one fact that makes it matter"',
                )
            )
        else:
            book["Core"].append(args.core.strip())
            changed = True

    if args.check:
        if not args.by:
            refused.append(
                (
                    "a checkpoint with no record is not a checkpoint.",
                    '--check "what now holds" --by "what verified it"',
                )
            )
        elif CLAIM.search(args.check) and not COVERAGE.search(args.by):
            refused.append(
                (
                    "verified without stated coverage is a mood, not a result.",
                    '--by "brute force, n ≤ 6, including empty and maximum"',
                )
            )
        else:
            num = len(book["Verified"]) + 1
            book["Verified"].append(
                "✓%02d %s — verified by: %s" % (num, args.check.strip(), args.by.strip())
            )
            changed = True

    if args.open:
        settle = args.settled_by.strip() if args.settled_by else ""
        if not settle:
            refused.append(
                (
                    "an open question with nothing that would settle it cannot be closed.",
                    '--open "the question" --settled-by "the cheapest test that could refute it"',
                )
            )
        else:
            num = len(book["Open"]) + 1
            book["Open"].append("?%02d %s — settled by: %s" % (num, args.open.strip(), settle))
            changed = True

    if args.close is not None:
        rows = book["Open"]
        idx = args.close - 1
        if idx < 0 or idx >= len(rows):
            refused.append(
                ("no open question numbered %d." % args.close, "run `seam` to see the list")
            )
        else:
            rows.pop(idx)
            book["Open"] = [
                re.sub(r"^\?\d\d", "?%02d" % (n + 1), r) for n, r in enumerate(rows)
            ]
            changed = True

    if args.next:
        book["Next"] = [args.next.strip()]
        changed = True

    if changed:
        problem = write_ledger(book)
        if problem:
            print("CANNOT: cannot write the ledger — " + problem)
            print("  free the path, or work without the file: keep the five lines in the")
            print("  conversation and restate them at each seam.")
            return 2
    for message, fix in refused:
        declined(message, fix)
    if refused:
        if changed:
            print("  (everything else in this call was recorded.)")
        return 2
    print_ledger(book)
    return 0


def mode_ship(text):
    """Report inner-register leakage in outgoing text.

    A report, not a gate: it exits 0 whether or not it finds anything, because
    the caller asked it to look and it looked.
    """
    findings = []
    lines = text.splitlines()

    leaked = sorted({s for s in INNER_ONLY if s in text})
    if leaked:
        findings.append("inner-register notation in outgoing text: " + " ".join(leaked))

    hot = sorted({m for m in MARKERS if m.lower() in text.lower()})
    if hot:
        findings.append("state markers in outgoing text: " + ", ".join(hot))

    for n, line in enumerate(lines, 1):
        if CLAIM.search(line) and not COVERAGE.search(line):
            findings.append('line %d: "verified" with no stated coverage' % n)
            break

    run = 1
    for a, b in zip(lines, lines[1:]):
        run = run + 1 if a.strip() and a.strip() == b.strip() else 1
        if run >= 3:
            findings.append("repetition loop: a line repeats three times or more")
            break

    if re.search(r"([.…\-'\s])\1{20,}", text):
        findings.append("repetition loop: a character run of 20 or more")

    if not findings:
        print("clean — the outgoing register holds.")
        return 0
    print("── j-space ─ ship")
    for f in findings[:7]:
        print("· " + f)
    print()
    print("The switch is total: expand the span into clean language before it goes.")
    return 0


# --------------------------------------------------------------------------- main


def main(argv=None):
    """Parse the subcommand and run it. Returns the process exit code."""
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seam", help="the ledger, and what has and has not moved")
    sub.add_parser("resume", help="premise, invariants and full ledger, after a gap")

    n = sub.add_parser("note", help="record something in the ledger")
    n.add_argument("--goal")
    n.add_argument("--core")
    n.add_argument("--next")
    n.add_argument("--check")
    n.add_argument("--by")
    n.add_argument("--open")
    n.add_argument("--settled-by", dest="settled_by")
    n.add_argument("--close", type=int)

    s = sub.add_parser("ship", help="register check on anything about to leave")
    s.add_argument("file", help="path, or - for stdin")

    args = p.parse_args(argv)

    if args.cmd == "ship":
        if args.file == "-":
            return mode_ship(sys.stdin.read())
        try:
            text = open(args.file, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            print("CANNOT: %s (%s)." % (args.file, exc.strerror or "unreadable"))
            print("  pass a readable file, or - to read stdin")
            return 2
        return mode_ship(text)

    book = read_ledger()
    if args.cmd == "seam":
        return mode_seam(book)
    if args.cmd == "resume":
        return mode_resume(book)
    return mode_note(book, args)


if __name__ == "__main__":
    sys.exit(main())
