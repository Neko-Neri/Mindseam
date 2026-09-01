#!/usr/bin/env python3
"""mindseam — an instrument for the Mindseam skill.

It knows one thing you cannot know accurately: what state you were in a few seams
ago. It keeps that record and hands it back. It decides nothing, and it blocks
nothing.

    mindseam.py seam                          the ledger, and what has and has not moved
    mindseam.py note --next "..."             set the single next action
    mindseam.py note --goal "..."             set what done means
    mindseam.py note --core "name — one fact" add a hub entry
    mindseam.py note --core "..." --core-slot 1  swap a live hub entry
    mindseam.py note --check "..." --by "..." append a numbered verified checkpoint
    mindseam.py note --open "..." --settled-by "..."   add an open question
    mindseam.py note --close 2 --check "..." --by "..."  resolve question 2
    mindseam.py ship draft.md                 register check on anything about to leave
    mindseam.py resume                        premise, invariants and full ledger

Exit codes mean one thing only:

    0   it did what you asked
    2   it could not do what you asked

It never exits non-zero to stop you from working. The one thing it declines to do
is write a malformed entry into the ledger, because a ledger you cannot trust is
worse than no ledger — it looks like state.

Standard library only. No network. Writes exactly one directory: .mindseam/
"""

import argparse
import codecs
import collections
import json
import math
import os
import re
import sys
import tempfile
import time

LEDGER_DIR = ".mindseam"
LEDGER = os.path.join(LEDGER_DIR, "WORKSPACE.md")
HISTORY = os.path.join(LEDGER_DIR, "history.json")
SECTIONS = ("Goal", "Core", "Verified", "Open", "Next")

STALL_RUN = 3          # consecutive seams before a pattern is worth reporting
RESUME_GAP = 1800      # seconds after which a seam prints the fuller anchor
METACOGNITION_SCHEMA_VERSION = 1
METACOGNITION_KEYS = {
    "marker", "confidence", "verifier", "trend", "risk",
    "error", "outcome", "extra_steps",
}
# Event keys are consumed by the next seam and cleared; state keys persist.
METACOGNITION_EVENT_KEYS = ("error", "outcome", "extra_steps")
HISTORY_MAX = 500
HISTORY_ARCHIVE = os.path.join(LEDGER_DIR, "history.archive.json")
# The row schema ``--filter`` accepts, in the order the append path
# writes them. ``msg`` is optional, the rest are always present.
HISTORY_ROW_FIELDS = (
    "t", "next", "verified", "open", "msg",
    "marker", "confidence", "verifier", "risk",
    "error", "outcome", "extra_steps",
)
HEAL_REPORT_MAX = 5    # heal lines printed at a seam before the rest are summarised
HEAL_HEALTH_FLOOR = 45      # health scores below this earn a heal line
HEAL_SEVERITY_CEILING = 100 - HEAL_HEALTH_FLOOR   # severity scores above this do
# Most heal_actions entries carry a 0-100 HEALTH score: higher is better, so the
# gate fires below HEAL_HEALTH_FLOOR.  A few are scaled the other way round —
# higher means worse — and are named here so the gate compares them in the right
# direction instead of firing on exactly the sessions that are fine.
HEAL_SEVERITY_DETECTORS = frozenset(("stall_score",))
LEDGER_SCHEMA = {"Goal": list, "Core": list, "Verified": list, "Open": list, "Next": list}

PREMISE = (
    "You do not only produce words; you also think them before — and without — saying them.\n"
    "Research on language-model internals (Gurnee et al., Anthropic, 2026) identified a small,\n"
    "privileged set of internal representations, the **Mindseam**, that holds what you are\n"
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

# The controller reports its version through ``info --version``,
# the way ``gh --version`` / ``kubectl version`` do.
__version__ = "3.6.0"


SHIFTS = "Shift the abstraction, shift the strategy, or shift to empirics."


class LedgerReadError(Exception):
    """The persisted ledger cannot be read without risking state loss."""

# Notation that belongs to the inner register and nowhere a person reads.
# Deliberately excludes ✓ ✗ √: they are ordinary in checklists and summaries, and
# stripping them from good writing costs more than the leak they would catch.
INNER_ONLY = ["⇒", "⟹", "⟸", "∴", "∵", "⊆", "⊇", "∋", "??", "?!", "💀"]
MARKERS = ["GRRR", "GAAAH", "PHEW", "I see meltdown", "DATA DATA",
           "I'M DROWNING", "blocked?!"]
MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
SETEXT_UNDERLINE = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
TABLE_DELIMITER = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
MARKDOWN_LIST_ITEM = re.compile(r"^\s{0,3}(?:[-+*]|\d+[.)])\s+")
MARKDOWN_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
THEMATIC_BREAK = re.compile(r"^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$")
RESERVED_CLOSE_SUFFIX = re.compile(r" — closes: \?\d+$")
OPEN_ID_RE = re.compile(r"^\?(\d+)\b")
CLOSED_OPEN_ID_RE = re.compile(r" — closes: \?(\d+)$")
CHECKPOINT_ID_RE = re.compile(r"^✓(\d+)\b")
REPETITION_CHAR_RUN = re.compile(r"([.…\-'])\1{19,}")
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
        with open(LEDGER, encoding="utf-8-sig") as fh:
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
                book[current].append(head)
            else:
                book[current].append(head[2:].strip() if head.startswith("- ") else head)
    return book


def atomic_write_text(path, text):
    """Replace a UTF-8 text file atomically. Returns an error string or None.

    The temp file is created next to the target, the same-filesystem
    requirement os.replace is built on: it used to live in LEDGER_DIR,
    so any target on another volume than the process cwd — a patched
    test path on another drive, a relocated .mindseam — failed with a
    cross-device move instead of writing.
    """
    target_dir = os.path.dirname(os.path.abspath(path)) or os.curdir
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as exc:
        return "%s (%s)" % (path, exc.strerror or "cannot create")
    if not os.path.isdir(target_dir):
        return "%s exists but is not a directory" % path
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target_dir,
            prefix=os.path.basename(path) + ".", delete=False
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
    book, _ = validate_book(book)
    out = ["# Mindseam Workspace Ledger", ""]
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
    # Tolerates a partial book: read_ledger always returns every section,
    # but the public scoring helpers accept any mapping, and a KeyError
    # on a missing section is a crash, not a measurement.
    rows = book.get(key)
    return rows[0] if rows else ""


def validate_book(book):
    """Return a book tightened to the ledger schema, plus a list of schema findings."""
    findings = []
    if not isinstance(book, dict):
        return {key: [] for key in LEDGER_SCHEMA}, ["ledger is not a mapping"]
    out = {}
    for key, want_type in LEDGER_SCHEMA.items():
        value = book.get(key)
        if not isinstance(value, want_type):
            findings.append("%s is not a %s" % (key, want_type.__name__))
            out[key] = []
        elif want_type is list:
            out[key] = [item for item in value if isinstance(item, str)]
        else:
            out[key] = value
    return out, findings


def _meta_value_ok(key, value):
    """Meta values are typed like the entries they become; anything else is absence.

    ``risk`` and ``trend`` are state dicts ({"level", "reasons"} / lists of
    labels), ``extra_steps`` a non-negative int, every other known key a
    one-line string.  A value of another type cannot become a history
    entry without crashing the detectors that read it, so it reads as
    never recorded rather than as a corrupted record.
    """
    if key in ("risk", "trend"):
        return isinstance(value, dict)
    if key == "extra_steps":
        return (isinstance(value, int) and not isinstance(value, bool)
                and value >= 0)
    return isinstance(value, str)


def validate_meta_schema(payload):
    """Filter unknown keys and re-sign with the current schema version."""
    if not isinstance(payload, dict):
        payload = {}
    legacy_version = payload.pop("schema_version", None)
    cleaned = {key: payload[key] for key in METACOGNITION_KEYS
               if key in payload and _meta_value_ok(key, payload[key])}
    if payload.get("trend") and not isinstance(payload["trend"], dict):
        cleaned.pop("trend", None)
    if isinstance(payload.get("markers"), str) and payload["markers"]:
        cleaned["marker"] = payload.pop("markers")
    if legacy_version is not None and legacy_version != METACOGNITION_SCHEMA_VERSION:
        cleaned.setdefault("schema_upgraded", True)
    cleaned["schema_version"] = METACOGNITION_SCHEMA_VERSION
    return cleaned


def read_meta():
    path = os.path.join(os.getcwd(), LEDGER_DIR, "metacognition.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("schema_version") != METACOGNITION_SCHEMA_VERSION:
        # Migrate instead of dropping: returning {} here made
        # validate_meta_schema's upgrade path unreachable and silently
        # wiped the persisted trend on any version mismatch.
        data = validate_meta_schema(data)
    # The same-version fast path skips the migrator, so the value check
    # runs here too: a hand-edited file with a current signature must
    # not smuggle mistyped values past validation.
    return {k: v for k, v in data.items()
            if k in METACOGNITION_KEYS and _meta_value_ok(k, v)}


def write_meta(meta):
    path = os.path.join(os.getcwd(), LEDGER_DIR, "metacognition.json")
    payload = validate_meta_schema(meta)
    return atomic_write_text(path, json.dumps(payload))


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
    pattern = CHECKPOINT_ID_RE if prefix == "✓" else re.compile(r"^%s(\d+)\b" % re.escape(prefix))
    numbers = []
    for row in rows:
        match = pattern.match(row)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def next_open_number(book):
    """Allocate an Open id that remains retired after its question closes."""
    numbers = []
    for row in book.get("Open", []):
        match = OPEN_ID_RE.match(row)
        if match:
            numbers.append(int(match.group(1)))
    for row in book.get("Verified", []):
        match = CLOSED_OPEN_ID_RE.search(row)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


# ------------------------------------------------------------------------ history


def read_history():
    repaired = []
    changed = False
    repair_reasons = []
    if not os.path.exists(HISTORY):
        return repaired, changed, repair_reasons
    try:
        with open(HISTORY, encoding="utf-8-sig") as fh:
            hist = json.load(fh)
    except (ValueError, OSError) as exc:
        repair_reasons.append("history was unreadable and has been restarted (%s)" % exc)
        return repaired, changed, repair_reasons
    if not isinstance(hist, list):
        repair_reasons.append("history root was not a list and has been restarted")
        return repaired, changed, repair_reasons
    for index, row in enumerate(hist):
        if not isinstance(row, dict):
            repair_reasons.append("history[%d] was not an object and has been dropped" % index)
            changed = True
            continue
        fixed = dict(row)
        if not isinstance(fixed.get("t"), int) or isinstance(fixed.get("t"), bool):
            fixed.pop("t", None)
        if not isinstance(fixed.get("next"), str):
            fixed["next"] = ""
            changed = True
        if not isinstance(fixed.get("verified"), int) or isinstance(fixed.get("verified"), bool):
            fixed["verified"] = 0
            changed = True
        if not isinstance(fixed.get("open"), int) or isinstance(fixed.get("open"), bool):
            fixed["open"] = 0
            changed = True
        for key in ("error", "outcome"):
            if key in fixed and not isinstance(fixed[key], str):
                fixed[key] = ""
                changed = True
        for key in ("marker", "confidence", "verifier", "risk"):
            # Detectors call .strip()/.lower() on these; a corrupted
            # non-string value would crash the seam instead of being
            # repaired like the numeric fields above.
            if key in fixed and not isinstance(fixed[key], str):
                fixed[key] = ""
                changed = True
        if "extra_steps" in fixed and (
            not isinstance(fixed["extra_steps"], int)
            or isinstance(fixed["extra_steps"], bool)
            or fixed["extra_steps"] < 0
        ):
            fixed["extra_steps"] = 0
            changed = True
        if "t" not in fixed:
            fixed["t"] = int(time.time())
            repair_reasons.append("history[%d] was missing 't' and has been repaired" % index)
            changed = True
        repaired.append(fixed)
    if changed:
        problem = atomic_write_text(HISTORY, json.dumps(repaired))
        if problem:
            repair_reasons.append("repaired history could not be saved (%s)" % problem)
        else:
            repair_reasons.append("repaired history has been saved")
    return repaired, changed, repair_reasons


def compact_history(hist):
    changed = False
    reasons = []
    if len(hist) <= HISTORY_MAX:
        return hist, changed, reasons
    archive = hist[:-HISTORY_MAX]
    kept = hist[-HISTORY_MAX:]
    if archive:
        existing = []
        if os.path.exists(HISTORY_ARCHIVE):
            try:
                with open(HISTORY_ARCHIVE, encoding="utf-8-sig") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    existing = [row for row in loaded if isinstance(row, dict)]
                else:
                    reasons.append(
                        "history archive root was not a list and has been replaced")
            except (ValueError, OSError) as exc:
                reasons.append(
                    "history archive was unreadable and has been replaced (%s)" % exc)
        # The archive is append-only across compactions: overwriting it
        # with only the newest slice would silently drop every earlier
        # archived entry each time the history crosses HISTORY_MAX again.
        problem = atomic_write_text(
            HISTORY_ARCHIVE, json.dumps(existing + archive))
        if problem:
            reasons.append("history archive could not be saved (%s)" % problem)
        else:
            reasons.append("archived %d history entries to %s" % (len(archive), HISTORY_ARCHIVE))
            changed = True
            problem = atomic_write_text(HISTORY, json.dumps(kept))
            if problem:
                reasons.append("compacted history could not be saved (%s)" % problem)
            else:
                reasons.append("history compacted to %d entries" % len(kept))
    return kept, changed, reasons


def last_verifier(book):
    last = book["Verified"][-1] if book["Verified"] else ""
    if " — verified by: " in last:
        name = last.split(" — verified by: ", 1)[1]
    elif " — " in last:
        name = last.split(" — ", 1)[1]
    else:
        return ""
    # The closure suffix is ledger bookkeeping, not part of the verifier
    # identity: keeping it made one closing verifier read as a new name
    # on every --close.
    return RESERVED_CLOSE_SUFFIX.sub("", name)


def append_history(book, meta=None):
    hist, _, _ = read_history()
    entry = {
        "t": int(time.time()),
        "next": one(book, "Next"),
        "verified": len(book["Verified"]),
        "open": len(book["Open"]),
        "marker": "",
        "confidence": "",
        "verifier": last_verifier(book),
        "risk": "",
        "error": "",
        "outcome": "",
        "extra_steps": 0,
    }
    if isinstance(meta, dict):
        # read_meta already drops mistyped values; this coercion covers
        # direct callers passing hand-built meta, so no type can reach
        # history.json that read_history's repair rules would reject.
        for k in ("marker", "confidence", "error", "outcome"):
            val = meta.get(k)
            if isinstance(val, str):
                entry[k] = val
        verifier = meta.get("verifier")
        if isinstance(verifier, str) and verifier:
            entry["verifier"] = verifier
        steps = meta.get("extra_steps")
        if isinstance(steps, int) and not isinstance(steps, bool) and steps > 0:
            entry["extra_steps"] = steps
    hist.append(entry)
    risk_level, _ = assess_risk(hist)
    entry["risk"] = risk_level
    hist, _, compact_reasons = compact_history(hist)
    problem = atomic_write_text(HISTORY, json.dumps(hist))
    if problem:
        print("WARNING: recent seam history was not saved — " + problem, file=sys.stderr)
    return hist, compact_reasons


def observations(hist, meta=None, book=None, run=None):
    """Facts about recent state. Facts only — the judgement is not the script's."""
    if isinstance(hist, dict):
        hist = [hist]
    if len(hist) < STALL_RUN:
        return []
    if run is None:
        run = hist[-STALL_RUN:]
    found = []
    trend = meta or {}
    nexts = []
    first_verified_val = None
    last_verified_val = None
    opens = []
    markers = []
    confidences = []
    verifiers = []
    shaky_confidences = []
    inaccessible = 0
    has_phew = False
    prev_open = None
    opens_mono = True
    marker_shaky_count = 0
    verifier_shaky_count = 0
    for h in run:
        nexts.append(h.get("next"))
        _vr = h.get("verified", 0)
        if _vr:
            if first_verified_val is None:
                first_verified_val = _vr
            last_verified_val = _vr
        o = h.get("open", 0)
        opens.append(o)
        if prev_open is not None and o <= prev_open:
            opens_mono = False
        prev_open = o
        _m = h.get("marker")
        if _m:
            markers.append(_m)
            has_phew = has_phew or _m == "PHEW"
            if h.get("confidence") == "shaky":
                marker_shaky_count += 1
        _c = h.get("confidence")
        if _c:
            confidences.append(_c)
        if _c == "shaky":
            shaky_confidences.append(_c)
        _v = h.get("verifier")
        if _v:
            verifiers.append(_v)
            if _c == "shaky":
                verifier_shaky_count += 1
        if _vr and not h.get("outcome"):
            inaccessible += 1
    if inaccessible >= STALL_RUN:
        found.append(
            "Verified outcomes are inaccessible (%d/%d entries); results cannot be audited."
            % (inaccessible, len(run))
        )
    found.extend(detect_stall(hist, run=run))
    if book is not None:
        cov = coverage_ratio(book)
        if cov >= 0.7:
            found.append("Ledger is 70%%+ open items (%d%% coverage)." % int(cov * 100))
        comp = completeness_score(book)
        if comp < 20 and (book.get("Core") or book.get("Open")):
            found.append("Ledger completeness is low (%d/100) — verify core items." % comp)
    if opens and opens_mono:
        found.append("Open-question count increased at every seam.")
    if first_verified_val is not None and first_verified_val != last_verified_val and len({n for n in nexts if n}) == 1:
        found.append(
            "Verified entries are growing but the next action has not changed."
        )
    if len(markers) >= STALL_RUN and len(set(markers)) == 1:
        found.append(
            "The same marker has been recorded for %d consecutive seams." % len(markers)
        )
        if marker_shaky_count >= STALL_RUN:
            found.append(
                "Marker '%s' co-occurs with 'shaky' confidence across %d seams." % (markers[0], len(run))
            )
    if len(confidences) >= STALL_RUN and len(set(confidences)) == 1:
        found.append(
            "Every confidence tag in the last %d seams has been '%s'." % (len(confidences), confidences[0])
        )
    if len(verifiers) >= STALL_RUN and len(set(verifiers)) == 1:
        found.append(
            "The same verifier has been used for %d consecutive seam checks." % len(verifiers)
        )
        if verifier_shaky_count >= STALL_RUN:
            found.append(
                "The same verifier has been used with 'shaky' confidence for %d consecutive seams." % verifier_shaky_count
            )
    if len(shaky_confidences) >= STALL_RUN and len(set(confidences)) > 1:
        # When every tag is shaky the all-identical fact above already
        # emitted the exact same line; this one only adds information for
        # a mixed window that is nonetheless saturated with shaky tags.
        found.append(
            "Every confidence tag in the last %d seams has been 'shaky'." % len(shaky_confidences)
        )
    confidence_trend = trend.get("trend", {}).get("confidence", [])
    if len(confidence_trend) >= 2:
        # Same ordered reading as assess_risk: a sustained trend is every
        # recent step worse than the previous one; a single-step collapse
        # of two levels is its own degradation signature. The prefix stays
        # fixed because remediation_suggestions keys on it.
        levels = [CONFIDENCE_LEVEL.get(c, -1) for c in confidence_trend]
        if (len(levels) >= 3 and all(lv >= 0 for lv in levels[-3:])
                and levels[-3] < levels[-2] < levels[-1]):
            found.append(
                "Confidence trend shows degradation: %s -> %s -> %s."
                % tuple(confidence_trend[-3:]))
        elif (levels[-2] >= 0 and levels[-1] >= 0
              and levels[-1] - levels[-2] >= 2):
            found.append(
                "Confidence trend shows degradation: %s -> %s."
                % tuple(confidence_trend[-2:]))
    marker_trend = trend.get("trend", {}).get("marker", [])
    if len(marker_trend) >= 3 and len(set(marker_trend[-3:])) == 1:
        found.append(
            "Marker trend shows repeated marker: %s." % marker_trend[-1]
        )
    if len(opens) >= 2 and opens[-1] > opens[0] and not has_phew:
        found.append(
            "Open questions grew and no settle marker was recorded across those %d seams." % len(run)
        )
    escalation = detect_risk_escalation(hist, run=run)
    found.extend(escalation)
    recovery = detect_recovery(hist, run=run)
    found.extend(recovery)
    vol = confidence_volatility(hist, run=run)
    found.extend(detect_volatility(hist, run=run))
    st_score = stall_score(hist, run=run)
    if st_score >= 60:
        found.append("Stall severity is high (%d/100); session has lost momentum." % st_score)
    elif st_score >= 30:
        found.append("Stall severity is elevated (%d/100); watch for degradation." % st_score)
    # The fusion layer penalises compound patterns; this fact is the
    # same measurement surfaced to the reader (the detector had existed
    # without any caller — an unplugged monitor).
    found.extend(compound_pattern_facts(
        hist, book=book, st_score=st_score, vol_changes=vol, run=run))
    found.extend(detect_ledger_stagnation(hist, book))
    age = fact_age_seconds(hist)
    if age > 0:
        dw = decay_weight(hist)
        if dw < 0.7:
            found.append("Facts are aging (age %d s, decay %.0f%%)." % (age, (1.0 - dw) * 100))
        rq = recovery_quality(hist, run=run)
        if rq >= 0.5:
            found.append("Recovery quality %.0f%%; risk gradient improving." % (rq * 100))
    mm = session_momentum(hist)
    if mm == "positive":
        found.append("Session momentum: positive — verification is progressing.")
    elif mm == "negative":
        found.append("Session momentum: negative — no verification growth detected.")
    ta = trend_acceleration(hist)
    if ta == "accelerating":
        found.append("Session trend is accelerating — pace of work is increasing.")
    elif ta == "decelerating":
        found.append("Session trend is decelerating — pace of work is slowing.")
    conv = convergence_index(hist)
    if conv < 30:
        found.append("Signals are strongly divergent (convergence %d/100)." % conv)
    elif conv >= 75:
        found.append("Signals are strongly aligned (convergence %d/100)." % conv)
    pp = pattern_persistence(hist)
    if pp == "chronic":
        found.append("Patterns are Chronic — these issues are persisting across the session.")
    elif pp == "transient":
        found.append("Patterns are Transient — current issues may be temporary noise.")
    sf = session_fatigue(hist)
    if sf >= 60:
        found.append("Session fatigue is high (%d/100) — consider a break or fresh ledger." % sf)
    elif sf >= 35:
        found.append("Session fatigue is moderate (%d/100)." % sf)
    er = entropy_reservoir(hist, run=run)
    if er < 0.3:
        found.append("Workspace entropy is low (%.0f%%); cognitive diversity is narrowing." % (er * 100))
    elif er > 0.75:
        found.append("Workspace entropy is high (%.0f%%); many threads are active." % (er * 100))
    cl = cognitive_load_index(hist, run=run, ent=er)
    if cl >= 60:
        found.append("Cognitive load is high (%d/100); consider offloading or pausing." % cl)
    dv = drift_velocity(hist, run=run)
    if dv >= 0.66:
        found.append("Action drift is high (%.0f%%); next-action intent is unstable." % (dv * 100))
    vd = verification_depth(hist)
    if vd <= 1 and first_verified_val is not None:
        found.append("Verification depth is shallow (%d unique verifier name(s)); confidence may be over-claimed." % vd)
    pc = premature_convergence(hist, book=book, run=run)
    found.extend(pc)
    rr = resolution_rate(hist, run=run)
    if rr < 0.4:
        found.append("Thread resolution is low (%.0f%%); many items remain open." % (rr * 100))
    loop = loop_detection(hist, run=run)
    found.extend(loop)
    ec = escalation_likelihood(hist, run=run)
    if ec >= 50:
        found.append("Risk escalation likelihood is high (%d/100)." % ec)
    cd = contradiction_detection(hist)
    found.extend(cd)
    ew = evidence_weight(hist)
    if ew < 30:
        found.append("Evidence weight is low (%d/100); findings are weakly supported." % ew)
    cal = confidence_calibration_error(hist)
    if cal >= 60:
        found.append("Confidence calibration error is high (%d/100); confidence may be over-claimed." % cal)
    ad = adaptability_score(hist)
    if ad >= 80:
        found.append("Adaptability is high (%d/100); the session is learning from issues." % ad)
    elif ad < 20:
        found.append("Adaptability is low (%d/100); the session is repeating patterns." % ad)
    lr = learning_rate(hist)
    if lr < 0.3:
        found.append("Learning rate is low (%.0f%%); little evidence is being produced." % (lr * 100))
    tr = tension_resolution(hist, run=run)
    if tr >= 70:
        found.append("Tension resolution is strong (%d/100); issues are being closed." % tr)
    elif tr < 30:
        found.append("Tension resolution is weak (%d/100); issues persist without closure." % tr)
    ers = error_recovery_speed(hist)
    if ers < 40:
        found.append("Error recovery is slow (%d/100); errors persist before resolution." % ers)
    erd = error_recovery_depth(hist)
    if erd < 30:
        found.append("Error recovery is shallow (%d/100); errors exit after one step without a recovery chain." % erd)
    oc = outcome_completeness(hist)
    if oc < 30:
        found.append("Outcome completeness is low (%d%%); results are rarely recorded." % oc)
    # verifier_independence is reported once, further down, as "Verifier
    # concentration".  A second emission here under a tighter threshold added no
    # new number and no new conclusion — the same score and the same trailing
    # clause were printed twice for any session below 30.
    ga = goal_alignment_score(hist, book=book, run=run)
    if ga < 30:
        found.append("Goal alignment is drifting (%d/100); next actions diverge from the stated goal." % ga)
    ce = cognitive_efficiency(hist)
    if ce < 30:
        found.append("Cognitive efficiency is low (%d/100); many entries without deliverable outputs." % ce)
    tm = thread_management(hist)
    if tm < 30:
        found.append("Thread management is poor (%d/100); open threads remain unresolved." % tm)
    roc = risk_outcome_correlation(hist)
    if roc < 30:
        found.append("Risk outcome correlation is weak (%d/100); risk predictions do not match outcomes." % roc)
    vtb = verification_temporal_bias(hist)
    if vtb < 100:
        found.append("Verification temporal bias (%d/100); verification is not evenly distributed." % vtb)
    cot = confidence_outcome_tracking(hist)
    if cot < 100:
        found.append("Confidence-outcome misalignment (%d/100); confidence labels do not match results." % cot)
    rer = risk_escalation_response(hist)
    if rer < 100:
        found.append("Risk escalation is not adapted (%d/100); risk changed but next action did not." % rer)
    vlt = verification_lead_time(hist)
    if vlt < 50:
        found.append("Verification follows action (%d/100); act-then-verify pattern detected." % vlt)
    va = verifier_agreement(hist)
    if va < 100:
        found.append("Verifier disagreement (%d/100); verifiers produce conflicting checks." % va)
    osr = output_stub_ratio(hist)
    if osr < 100:
        found.append("Output stub score is low (%d/100); next actions lack domain specifics." % osr)
    se = step_economy(hist)
    if se < 100:
        found.append("Step economy poor (%d/100); redundant sub-steps detected." % se)
    vi = verifier_independence(hist)
    if vi < 100:
        found.append("Verifier concentration (%d/100); checks concentrated in one name." % vi)
    nar = next_action_redundancy(hist)
    if nar < 100:
        found.append("Next-action redundancy detected (%d/100); the same action repeats." % nar)
    ec = error_convergence(hist)
    if ec < 100:
        found.append("Error convergence (%d/100); errors cluster in similar patterns." % ec)
    err_r = error_recovery_ratio(hist)
    if err_r < 100:
        found.append("Error recovery failure (%d/100); errors did not self-correct." % err_r)
    esr = error_silence_ratio(hist)
    if esr < 100:
        found.append("Error description score is low (%d/100); errors lack diagnostic detail." % esr)
    vsp = verifier_specificity(hist)
    if vsp < 100:
        found.append("Verifier specificity (%d/100); verifier text is generic." % vsp)
    nas = next_action_specificity(hist)
    if nas < 100:
        found.append("Next-action specificity low (%d/100); next action is vague." % nas)
    cp = confidence_presence(hist)
    if cp < 100:
        found.append("Confidence presence (%d/100); some steps carry no confidence tag." % cp)
    rdr = reasoning_depth_ratio(hist)
    if rdr < 100:
        found.append("Reasoning depth low (%d/100); reasoning is shallow." % rdr)
    ear = error_acknowledgment_ratio(hist)
    if ear < 100:
        found.append("Error not acknowledged (%d/100); errors ignored in next action." % ear)
    vcs = verification_coverage_score(hist)
    if vcs < 100:
        found.append("Verification coverage low (%d/100); verification is thin." % vcs)
    if any((h.get("confidence") or "").strip() for h in run):
        # Mirrors the round-14 score-layer gate: without labels the
        # detector collapses to one "unknown" bucket and 0 would punish
        # the absence that confidence_presence already reports.
        ad = assumption_diversity(hist, book=book, run=run)
        if ad < 30:
            found.append("Assumption diversity is low (%d/100); reasoning relies on narrow confidence pattern." % ad)
    ed = error_diversity(hist)
    if ed < 30:
        found.append("Error diversity is low (%d/100); the same error text is recurring." % ed)
    vs = verification_sincerity(hist)
    if vs < 30:
        found.append("Verification sincerity is low (%d/100); verifications are hollow." % vs)
    kr = knowledge_retention(hist)
    if kr < 30:
        found.append("Knowledge retention is low (%d/100); the same error recurs without being retained." % kr)
    ore = outcome_reliability(hist)
    if ore < 30:
        found.append("Outcome reliability is low (%d/100); claimed outcomes do not match the current state." % ore)
    er = evidence_recency(hist)
    if er < 30:
        found.append("Evidence recency is low (%d/100); the most recent verification was several steps ago." % er)
    tr = temporal_regularity(hist)
    if tr < 30:
        found.append("Temporal regularity is low (%d/100); step cadence is irregular." % tr)
    ms = meta_stability(hist)
    if ms < 30:
        found.append("Meta stability is low (%d/100); confidence tags are volatile." % ms)
    fa = feedback_amplification(hist)
    if fa < 30:
        found.append("Feedback amplification detected (%d/100); severity is escalating rather than resolving." % fa)
    re_eff = reset_efficacy(hist)
    if re_eff < 30:
        found.append("Reset efficacy is low (%d/100); resets are not closing underlying issues." % re_eff)
    om = output_momentum(hist, run=run)
    if om <= 33:
        found.append("Output momentum is low (%d/100); next actions are recurring without new progress." % om)
    cva = confidence_verification_alignment(hist, run=run)
    if cva < 30:
        found.append("Confidence-verification alignment is low (%d/100); high confidence lacks supporting verification." % cva)
    iv = incomplete_verification(hist, run=run)
    if iv < 30:
        found.append("Incomplete verification detected (%d/100); verified steps lack outcome records." % iv)
    ef = error_focus(hist)
    if ef < 30:
        found.append("Error focus is low (%d/100); errors are diversifying instead of converging." % ef)
    vr = verification_regression(hist)
    if vr < 30:
        found.append("Verification regression detected (%d/100); verification status has been lost." % vr)
    rr = step_retry_rate(hist)
    if rr < 30:
        found.append("Step retry score is low (%d/100); the same step is being retried repeatedly." % rr)
    sd = story_switch_detection(hist, book=book)
    if sd < 30:
        found.append("Story switch detected (%d/100); narrative stands have recently changed." % sd)
    cer = complexity_emission_ratio(hist)
    if cer < 30:
        found.append("Complexity-emission ratio is low (%d/100); reasoning complexity is not reflected in outcomes." % cer)
    nk = narrative_knot_detector(hist)
    if nk < 30:
        found.append("Narrative knot detected (%d/100); the session appears to revisit unresolved items repeatedly." % nk)
    ci = confidence_inflation(hist)
    if ci < 30:
        found.append("Confidence inflation detected (%d/100); strong claims lack verification." % ci)
    dcs = domain_coverage_score(hist)
    if dcs < 50:
        found.append("Domain coverage is narrow (%d/100); the session has not explored enough related items." % dcs)
    return found

def heal_actions(hist, book=None):
    actions = []
    if not hist:
        return actions
    if len(hist) < STALL_RUN:
        actions.insert(0, "HEAL: Collect at least %d seams before judging session health." % STALL_RUN)
        return actions
    detectors = [
        ("verification_regression", verification_regression(hist),
         "HEAL: Verification was lost downstream — preserve verified status when revising conclusions."),
        ("step_retry_rate", step_retry_rate(hist),
         "HEAL: High step retry — decompose the task into smaller steps before re-executing."),
        ("story_switch", story_switch_detection(hist, book=book),
         "HEAL: Narrative drift detected — restate the current goal before the next action."),
        ("complexity_emission", complexity_emission_ratio(hist),
         "HEAL: Complexity-emission gap — simplify reasoning output to match the task scope."),
        ("narrative_knot", narrative_knot_detector(hist),
         "HEAL: Narrative knot detected — revisit open threads sequentially instead of branching."),
        ("confidence_inflation", confidence_inflation(hist),
         "HEAL: Confidence may be inflated — lower confidence labels until verification supports them."),
        ("verification_temporal_bias", verification_temporal_bias(hist),
         "HEAL: Verification is clustered — spread checks across earlier steps rather than backlog."),
        ("risk_escalation_response", risk_escalation_response(hist),
         "HEAL: Risk is rising without a plan change — reassess risk assumptions and revise next action."),
        ("verifier_agreement", verifier_agreement(hist),
         "HEAL: Verifier disagreement — consolidate conflicting checks or introduce an independent verifier."),
        ("confidence_outcome_tracking", confidence_outcome_tracking(hist),
         "HEAL: Confidence and outcomes are misaligned — calibrate confidence labels against actual results."),
        ("thread_abandonment", thread_abandonment(hist),
         "HEAL: Error thread re-entry — complete the prior error domain before opening new threads."),
        ("step_economy", step_economy(hist),
         "HEAL: Step economy is poor — skip redundant sub-steps and consolidate the next action."),
        ("verifier_independence", verifier_independence(hist),
         "HEAL: Single-verifier concentration — use a different verifier name for the next check."),
        ("output_stub_ratio", output_stub_ratio(hist),
         "HEAL: Actions are generic — add domain specifics (targets, thresholds, owners) to next action."),
        ("next_action_redundancy", next_action_redundancy(hist),
         "HEAL: Next-action redundancy — introduce a genuinely different step instead of repeating."),
        ("error_convergence", error_convergence(hist),
         "HEAL: Errors cluster in one domain — investigate the root cause before retrying."),
        ("marker_progression", marker_progression(hist),
         "HEAL: Markers are stalled — advance the thread marker (OPEN→DONE→PHEW) on the next step."),
        ("verification_freshness", verification_freshness(hist),
         "HEAL: Verification is stale — run a fresh verification pass on recent steps."),
        ("temporal_continuity", temporal_continuity(hist),
         "HEAL: Timestamp discontinuity detected — ensure steps are recorded in monotonic order."),
        ("verification_completion_ratio", verification_completion_ratio(hist),
         "HEAL: Verifications left open — close pending verifications or mark them stale."),
        ("error_recovery_ratio", error_recovery_ratio(hist),
         "HEAL: Errors did not self-correct — add an explicit recovery step after each error."),
        ("error_silence_ratio", error_silence_ratio(hist),
         "HEAL: Error descriptions are too short — record at least one diagnostic keyword per error."),
        ("verifier_specificity", verifier_specificity(hist),
         "HEAL: Verifier text is generic — name the specific test method or evidence source."),
        ("next_action_specificity", next_action_specificity(hist),
         "HEAL: Next action is vague — include a concrete target, threshold, or artifact name."),
        ("confidence_presence", confidence_presence(hist),
         "HEAL: Confidence tags are missing on some steps — add strong/thin/shaky for self-assessment."),
        ("reasoning_depth_ratio", reasoning_depth_ratio(hist),
         "HEAL: Reasoning is shallow — add cause-effect chain or assumption analysis before acting."),
        ("error_acknowledgment_ratio", error_acknowledgment_ratio(hist),
         "HEAL: Errors ignored in next action — address each error explicitly in the following step."),
        ("verification_coverage_score", verification_coverage_score(hist),
         "HEAL: Verification is thin — add evidence beyond bare verified/unverified (method + source)."),
        ("marker_transition_diversity", marker_transition_diversity(hist),
         "HEAL: No marker transitions — progress through OPEN→DONE→PHEW on the next step."),
        ("premature_convergence", premature_convergence(hist, book=book, score=True),
         "HEAL: Progress claimed without verification — verify before marking DONE."),
        ("ledger_stasis", ledger_stasis_detector(hist, book),
         "HEAL: Next actions diverge from the ledger plan — re-read the ledger Next, or update it to name what is actually being done."),
    ]
    if book is not None:
        detectors.append(("book_thread_alignment", book_thread_alignment(hist, book),
                          "HEAL: Next action diverges from open ledger thread — re-align with the current Open item."))
    detectors.append(("stall_score", stall_score(hist),
                      "HEAL: Session is stalled — pivot the next action to a different task or approach."))
    for name, val, text in detectors:
        if not isinstance(val, (int, float)):
            continue
        if name in HEAL_SEVERITY_DETECTORS:
            # Severity scale: higher is worse, so the gate fires above the ceiling.
            if val > HEAL_SEVERITY_CEILING:
                actions.append(text)
        elif val < HEAL_HEALTH_FLOOR:
            actions.append(text)
    return actions


def fact_age_seconds(hist):
    """Seconds since the most recent recorded fact; 0 when just recorded.

    Staleness is measured from the freshest entry, not from the history's
    total span: an active session whose oldest seam is hours old still has
    current facts, and reporting those as aged would misdirect the reader.
    """
    if not hist:
        return 0
    youngest = max(int((h.get("t") if isinstance(h, dict) else 0) or 0) for h in hist)
    return max(0, int(time.time()) - youngest)


def decay_weight(hist, max_age=3600):
    age = fact_age_seconds(hist)
    if max_age <= 0:
        return 0.0
    ratio = min(1.0, age / float(max_age))
    return max(0.0, 1.0 - ratio)


def recovery_quality(hist, run=None):
    if run is None:
        run = hist[-STALL_RUN:]
    if not run:
        return 0.0
    if len(run) < STALL_RUN:
        return 0.0
    order = {"low": 0, "medium": 1, "high": 2}
    start = order.get(run[0].get("risk", "low"), 1)
    end = order.get(run[-1].get("risk", "low"), 1)
    if start == 0:
        return 0.0
    if end >= start:
        return 0.0
    return max(0.0, min(1.0, float(start - end) / float(start)))


def session_momentum(hist):
    if not hist or len(hist) < STALL_RUN:
        return "stable"
    first = hist[0].get("verified", 0)
    last = hist[-1].get("verified", 0)
    if last > first:
        return "positive"
    if last < first:
        return "negative"
    return "stable"


def momentum_velocity(hist, cap=10):
    if not hist or len(hist) < STALL_RUN:
        return 0.0
    first = hist[0].get("verified", 0)
    last = hist[-1].get("verified", 0)
    if cap <= 0:
        return 0.0
    velocity = (last - first) / float(cap)
    return max(0.0, min(1.0, velocity))


def trend_acceleration(hist, dims=None):
    """Return 'accelerating', 'decelerating', or 'stable'.

    Compares the rate of change across two adjacent windows to detect
    whether improvement is speeding up, slowing down, or unchanged.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return "stable"
    if dims is None:
        dims = ["verified"]
    half = len(hist) // 2
    first_slice = hist[:half]
    second_slice = hist[half:]
    if len(first_slice) < STALL_RUN or len(second_slice) < STALL_RUN:
        return "stable"
    results = []
    for dim in dims:
        rate1 = (first_slice[-1].get(dim, 0) - first_slice[0].get(dim, 0)) / float(len(first_slice))
        rate2 = (second_slice[-1].get(dim, 0) - second_slice[0].get(dim, 0)) / float(len(second_slice))
        if rate2 > rate1:
            results.append("accelerating")
        elif rate2 < rate1:
            results.append("decelerating")
        else:
            results.append("stable")
    if not results:
        return "stable"
    if all(r == "accelerating" for r in results):
        return "accelerating"
    if all(r == "decelerating" for r in results):
        return "decelerating"
    return "stable"


def convergence_index(hist, run=None):
    """Return a 0-100 measure of signal agreement across dimensions.

    The volatility signal counts only when the window carries confidence
    tags: zero volatility among recorded tags is measured stability, while
    zero volatility with nothing recorded is an absent signal, not an
    agreeing one. Without that read an unlabelled, risk-free window scored
    100 off silence alone.
    """
    if not hist or len(hist) < STALL_RUN:
        return 50
    signals = []
    risk_scores = {"low": 1, "medium": 0, "high": -1}
    conf_scores = {"strong": 1, "thin": 0, "shaky": -1}
    mm_scores = {"positive": 1, "stable": 0, "negative": -1}
    risk = hist[-1].get("risk", "low")
    signals.append(risk_scores.get(risk, 0))
    conf = hist[-1].get("confidence", "")
    signals.append(conf_scores.get(conf, 0))
    mm = session_momentum(hist)
    signals.append(mm_scores.get(mm, 0))
    tagged = any((h.get("confidence") or "").strip()
                 for h in hist[-STALL_RUN:])
    if tagged:
        vol = confidence_volatility(hist)
        signals.append(-1 if vol >= 2 else (0 if vol == 1 else 1))
    positives = sum(1 for s in signals if s > 0)
    negatives = sum(1 for s in signals if s < 0)
    total = positives + negatives
    if not total:
        return 50
    if positives > 0 and negatives > 0:
        return max(0, 50 - abs(positives - negatives) * 15)
    agreement = sum(signals) / total
    return int(50 + agreement * 50)


def pattern_persistence(hist, run=None):
    """Classify current firing patterns as chronic, transient, or none.

    Compares the current STALL_RUN window's issues against earlier non-
    overlapping windows.  Chronic = same issues repeated across the session.
    Transient = one-off noise.  None = no active patterns.
    """
    if not hist or len(hist) < STALL_RUN:
        return "none"
    if run is None:
        run = hist[-STALL_RUN:]
    def window_issues(seg):
        issues = set()
        unique_nexts = {h.get("next") for h in seg if h.get("next")}
        verifieds = {h.get("verified", 0) for h in seg}
        if len(unique_nexts) <= 1 and unique_nexts:
            issues.add("stall")
        if len(verifieds) == 1:
            issues.add("frozen")
        if any(h.get("risk") in ("medium", "high") for h in seg):
            issues.add("risk")
        if any(h.get("confidence") in ("thin", "shaky") for h in seg):
            issues.add("confidence")
        return frozenset(issues)
    current_issues = window_issues(run)
    if not current_issues:
        return "none"
    step = max(1, STALL_RUN // 2)
    earlier_segments = [hist[i:i + STALL_RUN] for i in range(0, len(hist) - STALL_RUN, step)]
    if not earlier_segments:
        return "transient"
    persistent_count = sum(1 for seg in earlier_segments if window_issues(seg) & current_issues)
    ratio = persistent_count / float(len(earlier_segments))
    return "chronic" if ratio >= 0.5 else "transient"


def session_fatigue(hist, run=None):
    """Return a 0-100 session fatigue score.

    Higher scores mean the session is exhausted: repeated stalls, confidence
    erosion, absent recovery, negative momentum, and risk stacking.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    score = 0
    has_phew = False
    v_set = set()
    c_first = None
    c_all_same = True
    c_has_weak = False
    r_high = False
    r_all_valid = True
    r_decreased = False
    r_increased = False
    prev_rv = None
    for h in run:
        v = h.get("verified", 0)
        v_set.add(v)
        c = h.get("confidence")
        if c_first is None:
            c_first = c
        elif c != c_first:
            c_all_same = False
        if c in ("thin", "shaky"):
            c_has_weak = True
        r = h.get("risk")
        if r == "high":
            r_high = True
        if r:
            rv = {"low": 0, "medium": 1, "high": 2}.get(r, -1)
            if rv >= 0:
                if prev_rv is not None:
                    if rv > prev_rv:
                        r_increased = True
                    elif rv < prev_rv:
                        r_decreased = True
                prev_rv = rv
            else:
                r_all_valid = False
        if h.get("marker") == "PHEW":
            has_phew = True
    if len(v_set) <= 1:
        score += 25
    if c_all_same and c_first in ("thin", "shaky"):
        score += 20
    elif c_has_weak:
        score += 10
    if r_high:
        score += 15
    if not has_phew:
        score += 10
    if hist[0].get("verified", 0) > hist[-1].get("verified", 0):
        score += 15
    if r_all_valid and prev_rv is not None:
        if r_decreased:
            score = max(0, score - 10)
        if r_increased:
            score = min(score + 10, 100)
    return max(0, min(100, score))


def drift_velocity(hist, run=None):
    """Return 0.0–1.0 rate of last-action text drift across the STALL_RUN window.

    Measures the fraction of seams where the recorded `next` action changed as
    a rough proxy for direction instability: high drift = the work plan keeps
    changing between seams.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0.0
    if run is None:
        run = hist[-STALL_RUN:]
    sep_count = 0
    sep_changes = 0
    prev_nxt = None
    for h in run:
        nxt = h.get("next") or ""
        has_nxt = bool(nxt)
        if has_nxt:
            sep_count += 1
            if prev_nxt is not None and nxt != prev_nxt:
                sep_changes += 1
        prev_nxt = nxt
    if sep_count == 0:
        return 0.0
    pairs = sep_count - 1
    return sep_changes / float(pairs) if pairs > 0 else 0.0


def verification_depth(hist, run=None):
    """Return the number of distinct verifiers seen in the STALL_RUN window.

    Higher depth = more independent verification coverage; lower depth means a
    single verifier carries most of the confidence.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    verifiers = {h.get("verifier") for h in run if h.get("verifier")}
    return len(verifiers)


def premature_convergence(hist, book=None, score=None, run=None):
    """Return list of premature-convergence facts, or a 0-100 scalar if score is True.

    Scalar mode does not require a book; it measures whether steps marked
    done remain consistently unverified, which signals a gap between
    claimed and evidenced progress.
    """
    if score:
        if not hist or len(hist) < STALL_RUN:
            return 100
        if run is None:
            run = hist[-STALL_RUN:]
        done_unverified = 0
        total = 0
        for h in run:
            total += 1
            if h.get("marker") == "DONE" and not h.get("verified"):
                done_unverified += 1
        if not done_unverified:
            return 100
        unverified_ratio = done_unverified / float(total)
        return max(0, int(100 - (unverified_ratio * 100)))

    if not hist or len(hist) < STALL_RUN:
        return []
    # Score mode short-circuits above, so passing book here cannot recurse.
    # Scoring blind here would contradict the seam banner, which is ledger-aware.
    result = session_health_score(hist, book=book)
    score = result.score
    if score < 75:
        return []
    if not (result.risk_esc or result.has_stall or result.compound):
        return []
    return ["Health score is high (%d/100) but active issues remain — possible premature convergence." % score]


def entropy_reservoir(hist, run=None, ent=None):
    if ent is not None:
        return ent
    if run is None:
        if not hist or len(hist) < STALL_RUN:
            return 0.0
        run = hist[-STALL_RUN:]
    fields = ("next", "reason", "error", "outcome", "verified", "confidence", "risk")
    max_possible = float(STALL_RUN * len(fields))
    values = set()
    for h in run:
        for f in fields:
            val = h.get(f)
            if val is not None and str(val).strip():
                values.add(str(val).strip())
    if max_possible <= 0:
        return 0.0
    return min(1.0, len(values) / max_possible)


def cognitive_load_index(hist, run=None, ent=None):
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    load = 0
    nexts = set()
    risk_high = False
    confidence_weak = False
    for h in run:
        n = h.get("next")
        if n:
            nexts.add(n)
        if h.get("risk") in ("medium", "high"):
            risk_high = True
        if h.get("confidence") in ("thin", "shaky"):
            confidence_weak = True
    load += min(len(nexts) * 10, 40)
    if risk_high and confidence_weak:
        load += 20
    if ent is None:
        ent = entropy_reservoir(hist, run=run)
    if ent < 0.3:
        load += 15
    elif ent < 0.5:
        load += 5
    conv = convergence_index(hist)
    if conv >= 75:
        load += 10
    mm = session_momentum(hist)
    if mm == "negative":
        load += 10
    dw = decay_weight(hist)
    if dw < 0.5:
        load += 10
    return min(load, 100)


def resolution_rate(hist, run=None):
    """Return 0.0–1.0 fraction of the STALL_RUN window that reached a resolved outcome.

    An entry counts as resolved when it has a truthy `outcome` or `verified > 0`.
    Low rate means more open threads without closure.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0.0
    if run is None:
        run = hist[-STALL_RUN:]
    if not run:
        return 0.0
    resolved = sum(1 for h in run if h.get("outcome") or h.get("verified", 0) > 0)
    return resolved / float(len(run))


def loop_detection(hist, run=None):
    """Return facts when next actions are cycling instead of progressing.

    Triggers when any adjacent pair in the `next` field repeats within the
    STALL_RUN window.  Detects ping-pong loops rather than forward motion.
    """
    if run is None:
        if not hist or len(hist) < STALL_RUN:
            return []
        window = hist[-(min(STALL_RUN + 2, len(hist))):]
    else:
        window = run
    seen = {}
    prev = None
    for h in window:
        nxt = h.get("next") or ""
        if prev and nxt:
            # Only real action pairs count: a run of empty next fields is
            # absence, not a ping-pong loop, and must not fire the loop
            # fact (or its fusion penalty).
            pair = (prev, nxt)
            seen[pair] = seen.get(pair, 0) + 1
            if seen[pair] >= 2:
                return ["Next-action loop detected (%s → %s repeated); break the cycle." % pair]
        prev = nxt
    return []


def escalation_likelihood(hist, run=None):
    """Return 0-100 estimated probability that risk will escalate next.

    Combines (a) fraction of recent entries at medium/high risk and (b)
    recent direction of risk transition.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    risk_scores = {"low": 0, "medium": 1, "high": 2}
    avg = 0.0
    total = 0
    increasing = 0
    prev = None
    for h in run:
        v = risk_scores.get(h.get("risk", "low"), 0)
        avg += v
        total += 1
        if prev is not None and v > prev:
            increasing += 1
        prev = v
    avg = avg / float(total)
    base = int(avg * 40) + increasing * 15
    return min(100, max(0, base))


def contradiction_detection(hist, run=None):
    """Return facts when risk and confidence disagree within recent decisions.

    A contradiction is an opposite-valence pair: ``strong`` confidence
    carried on ``high`` risk (overconfidence), or ``shaky`` confidence
    carried on ``low`` risk (a claimed doubt the risk record does not
    support). Coherent cautious pairs — thin or missing confidence on
    high risk — are risk awareness, not contradictions, and never fire.
    """
    if not hist or len(hist) < STALL_RUN:
        return []
    risk_rank = {"low": 0, "medium": 1, "high": 2}
    conf_rank = {"thin": 1, "shaky": 2, "strong": 3}
    if run is None:
        run = hist[-STALL_RUN:]
    count = 0
    for h in run:
        r = risk_rank.get(h.get("risk", "low"), 0)
        c = conf_rank.get(h.get("confidence", ""), 1)
        if (c >= 3 and r >= 2) or (c == 2 and r == 0):
            count += 1
    if count >= 2:
        return ["Risk-confidence contradiction detected in %d/%d recent entries; review assessment alignment." % (count, len(run))]
    return []


def evidence_weight(hist, run=None):
    """Return 0-100 composite strength of supporting evidence in the window.

    Combines: (a) verified count, (b) verifier diversity, (c) outcome
    presence, (d) low error rate.  High weight = findings are well-supported.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    verifier_set = {h.get("verifier") for h in run if h.get("verifier")}
    verified_count = sum(1 for h in run if h.get("verified", 0) > 0)
    outcome_count = sum(1 for h in run if h.get("outcome"))
    has_error = any(h.get("error") for h in run)
    weight = (
        min(len(verifier_set) * 10, 30)
        + min(verified_count * 8, 30)
        + min(outcome_count * 8, 25)
        + (15 if not has_error else 0)
    )
    return min(100, weight)


def confidence_calibration_error(hist, run=None):
    """Return 0-100 estimated misalignment between stated confidence and outcomes.

    When confidence is high but verified/outcome is poor or absent, the
    calibration error rises.  Low error means confidence tracks reality.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    error = 0
    for h in run:
        c = h.get("confidence", "")
        verified = h.get("verified", 0)
        outcome = h.get("outcome")
        if c == "strong" and not verified and not outcome:
            error += 20
        elif c == "strong" and (verified <= 1 or not outcome):
            error += 10
        elif c == "thin" and verified > 2 and outcome:
            error -= 5
    return max(0, min(100, error))


def adaptability_score(hist):
    """Return 0-100 measuring whether the session changes approach after problems.

    Combines: (a) risk descent (risk reduced from earlier), (b) stall breakout
    (flat next window followed by change), (c) verification growth (more than
    one unique count).  High score = session learns and adjusts.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    score = 0
    if len(hist) >= STALL_RUN * 2:
        order = {"low": 0, "medium": 1, "high": 2}
        recent_risk_sum = sum(order.get(h.get("risk", "low"), 1) for h in hist[-STALL_RUN:])
        earlier_risk_sum = sum(order.get(h.get("risk", "low"), 1) for h in hist[-STALL_RUN * 2 : -STALL_RUN])
        if earlier_risk_sum and recent_risk_sum < earlier_risk_sum:
            score += 40
    nexts = [h.get("next") or "" for h in hist]
    verifieds_set = {h.get("verified", 0) for h in hist}
    for i in range(STALL_RUN, len(nexts)):
        window = nexts[i - STALL_RUN : i]
        after = nexts[i]
        if len(set(window)) == 1 and window[0] and after and after != window[0]:
            score += 35
            break
    if len(verifieds_set) > 1:
        score += 25
    return min(100, score)


def learning_rate(hist, run=None):
    """Return 0.0-1.0 rate of evidence-producing entries per step.

    An entry counts as evidence-producing when it has verified>0, a recorded
    outcome, or a logged error.  Higher rate means the session is producing
    learnable signals at every step.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0.0
    if run is None:
        run = hist[-STALL_RUN:]
    if not run:
        return 0.0
    evidence = sum(1 for h in run if h.get("verified", 0) > 0 or h.get("outcome") or h.get("error"))
    return evidence / float(len(run))


def tension_resolution(hist, run=None):
    """Return 0-100 measuring how well session tension is being resolved.

    Tension signals include open questions, logged errors, high risk, and
    stalls.  A window carrying no tension has nothing to resolve and returns
    100 rather than reading as unresolved.  Resolution signals include
    open-count decrease, PHEW settle, risk recovery via
    :func:`detect_recovery`, and stall absence via :func:`detect_stall`.
    Higher = tension is actively easing.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    if not run:
        return 0
    has_phew = any(h.get("marker") == "PHEW" for h in run)
    has_tension = any(h.get("open", 0) > 0 or h.get("error") or h.get("risk") == "high" for h in run)
    opens_first = run[0].get("open", 0)
    opens_last = run[-1].get("open", 0)
    stall_free = not detect_stall(hist, run=run)
    is_recovering = bool(detect_recovery(hist, run=run))
    if not has_tension and stall_free:
        return 100
    score = (
        (35 if opens_last < opens_first else 0)
        + (25 if has_phew else 0)
        + (25 if is_recovering else 0)
        + (15 if stall_free else 0)
    )
    return min(100, score)


def error_recovery_speed(hist, run=None):
    """Return 0-100 measuring how quickly the session recovers after errors.

    For each error entry, count steps until the next entry with verified>0 or
    an outcome. Smaller delays yield higher scores. No errors in history returns
    100; errors with no subsequent verified entry returns low scores.
    """
    if not hist:
        return 100
    next_recovery = len(hist)
    total_delay = 0.0
    error_count = 0
    # A delay of 4 steps is the scale's zero point, so an error that was
    # never followed by any recovery scores 0 — the sentinel initialiser
    # used to score it the same as a one-step recovery.
    worst_delay = 4.0
    for i in range(len(hist) - 1, -1, -1):
        if hist[i].get("verified", 0) > 0 or hist[i].get("outcome"):
            next_recovery = i
        elif hist[i].get("error"):
            if next_recovery >= len(hist):
                total_delay += worst_delay
            else:
                total_delay += next_recovery - i
            error_count += 1
    if error_count == 0:
        return 100
    avg_delay = total_delay / float(error_count)
    return max(0, min(100, int(100 - avg_delay * 25)))


def outcome_completeness(hist, run=None):
    """Return 0-100 fraction of entries that have a recorded outcome.

    Strict outcome documentation shows closure discipline.  Each entry counts
    when it carries an explicit outcome string.
    """
    if not hist:
        return 100
    outcome_count = 0
    total = 0
    for h in hist:
        total += 1
        if h.get("outcome"):
            outcome_count += 1
    if total == 0:
        return 100
    return int(outcome_count * 100 / total)


def thread_management(hist, run=None):
    """Return 0-100 measuring closure of distinct next-thread lines.

    Counts unique next-action strings in the recent window versus how many
    of those strings appear alongside resolution (verified>0 or outcome).
    """
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    recent = hist[-(STALL_RUN + 1):]
    threads = set()
    resolved = set()
    for h in recent:
        n = h.get("next")
        if n:
            threads.add(n)
            if h.get("verified", 0) > 0 or h.get("outcome"):
                resolved.add(n)
    if not threads:
        return 100
    return int(len(resolved) * 100 / float(len(threads)))


def goal_alignment_score(hist, book=None, run=None):
    """Return 0-100 measuring whether next-thread strings still track the stated goal.

    Compares each recent `next` action to the current goal string.  Exact
    substring match (case-insensitive) counts as aligned.  Returns 100 when
    no goal is set (nothing to measure against).
    """
    if not hist:
        return 100
    goal = one(book, "Goal") if book else None
    if not goal:
        return 100
    goal_lower = goal.lower()
    if run is None:
        run = hist[-STALL_RUN:]
    window = run
    aligned = 0
    total = 0
    for h in window:
        total += 1
        nxt = h.get("next")
        if nxt and goal_lower in nxt.lower():
            aligned += 1
    return int(aligned * 100 / float(total)) if total else 100


def cognitive_efficiency(hist, run=None):
    """Return 0-100 measuring output-per-step efficiency.

    Ratio of entries that produce a deliverable (verified>=1 or outcome)
    to total entries in the recent window.  100 means every entry produced
    a deliverable.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    deliverables = 0
    total = 0
    for h in run:
        total += 1
        if h.get("verified", 0) > 0 or h.get("outcome"):
            deliverables += 1
    return int(deliverables * 100 / float(total)) if total else 100


def verification_sincerity(hist, run=None):
    """Return 0-100 measuring whether verifications carry substantive evidence.

    A verification is sincere when verified > 0 is paired with at least one
    supporting signal: verifier, outcome, or reason.  Hollow verifications
    claim progress without leaving a trace.  100 = every verification is
    meaningful; 0 = all verifications are hollow.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    checked = 0
    sincere = 0
    for h in run:
        if h.get("verified", 0) > 0:
            checked += 1
            if h.get("verifier") or h.get("outcome") or h.get("reason"):
                sincere += 1
    if checked == 0:
        return 100
    return int(sincere * 100 / float(checked))


def knowledge_retention(hist):
    """Return 0-100 measuring whether extracted errors recur in the session.

    Identical error patterns reappearing indicate the session failed to
    learn from earlier mistakes.  100 means every error was unique; the
    lower the score, the more the same errors repeat without being retained.
    """
    if not hist or len(hist) < 6:
        return 100
    error_sigs = [
        h.get("error", "").strip().lower() for h in hist if h.get("error")
    ]
    if not error_sigs:
        return 100
    total = len(error_sigs)
    unique = len(set(error_sigs))
    if unique == total:
        return 100
    dup_rate = 1.0 - (unique / float(total))
    return max(0, int((1.0 - dup_rate) * 100))


def outcome_reliability(hist, run=None):
    """Return 0-100 measuring whether claimed outcomes match actual state.

    A positive outcome (done, ok, pass, complete, success) that coexists
    with unresolved error, open items, or zero verification is paperwork
    closure, not real completion.  100 = every claimed outcome is backed
    by state; 0 = no claimed outcome matches the actual state.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    positive_keys = ("done", "ok", "pass", "complete", "success", "verified")
    negative_keys = ("fail", "error", "incomplete", "rejected", "blocked")
    claimed = 0
    reliable = 0
    for h in run:
        o = h.get("outcome")
        if not o:
            continue
        claimed += 1
        lo = o.lower()
        is_pos = is_neg = False
        for k in positive_keys:
            if k in lo:
                is_pos = True
                break
        for k in negative_keys:
            if k in lo:
                is_neg = True
                break
        if is_pos and not h.get("error") and h.get("open", 0) == 0 and h.get("verified", 0) > 0:
            reliable += 1
        elif is_neg:
            reliable += 1
    if claimed == 0:
        return 100
    return int(reliable * 100 / float(claimed))


def assumption_diversity(hist, book=None, run=None):
    """Return 0-100 measuring diversity of confidence and evidence levels.

    Entropy over confidence tags in the recent window reflects whether the
    session relies on a single assumption profile (low diversity) or tests
    multiple confidence levels.  100 = perfectly balanced spread.

    An unrecorded tag is absence, not a level: append_history writes the
    empty string when no tag was given, so blanks are dropped before the
    bucket count.  Counting them used to let one honest tag plus two blanks
    read as a rich spread (91/100) — praise for a measurement that never
    happened.  A window whose recorded tags collapse to one bucket scores
    0, the uniform profile invariant 4 names.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    window = run
    confidences = [c for h in window if (c := (h.get("confidence") or "").strip())]
    counts = {}
    for c in confidences:
        counts[c] = counts.get(c, 0) + 1
    if len(counts) <= 1:
        return 0
    total = sum(counts.values())
    entropy = 0.0
    for c in counts.values():
        p = c / float(total)
        entropy -= p * math.log(p, 2)
    max_ent = math.log(len(counts), 2)
    if max_ent <= 0:
        return 0
    return int((entropy / max_ent) * 100)


def error_diversity(hist):
    """Return 0-100 measuring how diverse error patterns are in recent entries.

    Uses the raw entry text as a proxy for error context.  When all error
    entries look identical it returns 0; when each error is contextually
    unique it approaches 100.
    """
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    window = hist[-(STALL_RUN + 1):]
    text_counts = {}
    total = 0
    for h in window:
        if h.get("error") or h.get("verified", 0) < 0:
            total += 1
            key = " ".join((h.get("pm", ""), h.get("error", ""), h.get("fact", ""))).strip()
            text_counts[key] = text_counts.get(key, 0) + 1
    if total == 0:
        return 100
    if not text_counts:
        return 0
    unique = len(text_counts)
    return int(unique * 100 / max(total, 1))


def risk_outcome_correlation(hist, run=None):
    """Return 0-100 measuring whether risk predictions match actual outcomes.

    Compares risk predictions to error frequencies across confidence bins.
    100 means risk predicted errors at the correct frequency;
    0 means risk predictions and errors are uncorrelated.
    """
    if not hist or len(hist) < 6:
        return 100
    if run is None:
        run = hist[-STALL_RUN * 2:]
    high_count = 0
    high_err = 0
    low_count = 0
    low_err = 0
    for h in run:
        r = (h.get("risk") or "").lower()
        if r == "high":
            high_count += 1
            if h.get("error") or h.get("verified", 0) < 0:
                high_err += 1
        elif r == "low":
            low_count += 1
            if h.get("error") or h.get("verified", 0) < 0:
                low_err += 1
    if not high_count or not low_count:
        return 100
    high_rate = high_err / float(high_count)
    low_rate = low_err / float(low_count)
    if high_rate <= low_rate:
        return 100
    spread = high_rate - low_rate
    if spread <= 0:
        return 100
    return min(100, int(spread * 100))


def temporal_regularity(hist, run=None):
    """Return 0-100 measuring how regularly the session proceeds.

    Consistency of step cadence prevents both stalls and rushed work.
    100 = perfectly regular intervals; 0 = bursty or stalled.
    The optional ``run`` argument is currently ignored; the window is
    always the trailing ``STALL_RUN + 1`` entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    run = hist[-(STALL_RUN + 1):]
    deltas = [run[i + 1].get("t", 0) - run[i].get("t", 0) for i in range(len(run) - 1)]
    if not deltas or all(d == 0 for d in deltas):
        return 0
    avg = sum(deltas) / float(len(deltas))
    if avg <= 0:
        return 0
    variance = sum((d - avg) ** 2 for d in deltas) / float(len(deltas))
    std = variance ** 0.5
    if std == 0:
        return 100
    cv = std / avg
    score = max(0, min(100, int((1.0 - min(cv, 1.0)) * 100)))
    return score


def evidence_recency(hist, run=None):
    """Return 0-100 measuring how fresh the most recent verification is.

    If no verification exists in the recent window, score is 0.
    If the latest verification is within one step, score is 100.
    """
    if not hist or len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    last_verified_idx = -1
    verified_count = 0
    for i, h in enumerate(run):
        if h.get("verified", 0) > 0:
            last_verified_idx = i
            verified_count += 1
    if verified_count == 0:
        return 0
    age = len(run) - 1 - last_verified_idx
    recency = max(0, (len(run) - 1 - age)) / float(len(run) - 1)
    return int(recency * 100)


def meta_stability(hist, run=None):
    """Return 0-100 measuring how stable session meta tags are over time.

    Flips between confidence levels every step indicate uncontrolled
    volatility.  Stability = monotone or near-monotone sequence.
    100 = no changes; 0 = alternating every step.
    """
    if not hist or len(hist) < 4:
        return 100
    non_empty = []
    prev = None
    flips = 0
    for h in hist[-6:]:
        c = h.get("confidence", "")
        if not c:
            continue
        non_empty.append(c)
        if prev is not None and c != prev:
            flips += 1
        prev = c
    if len(non_empty) < 4:
        return 100
    max_flips = len(non_empty) - 1
    if max_flips == 0:
        return 100
    stability = 1.0 - float(flips) / max_flips
    return int(stability * 100)


def feedback_amplification(hist, run=None):
    """Return 0-100 measuring whether severity oscillates instead of declining.

    100 = every step improved or stayed flat over the measurement window;
    low scores mean the session relapses after partial fixes. Severity is
    read from the ``risk`` field (low/medium/high mapped to 0/1/2), the
    same vocabulary as :func:`escalation_likelihood`. The optional
    ``run`` argument is currently ignored; the window is always the
    trailing 3 entries of ``hist``.
    """
    if not hist or len(hist) < 3:
        return 100
    run = hist[-3:]
    risk_scores = {"low": 0, "medium": 1, "high": 2}
    prev_sev = None
    improved = True
    worsened = True
    for h in run:
        sev = risk_scores.get((h.get("risk") or "").strip().lower(), 0)
        if prev_sev is not None:
            if sev > prev_sev:
                improved = False
            elif sev < prev_sev:
                worsened = False
        prev_sev = sev
    if improved:
        return 100
    if worsened:
        return 0
    return 50


def reset_efficacy(hist, run=None):
    """Return 0-100 measuring whether PHEW markers actually close underlying issues.

    A sincere PHEW is followed by no recurrence of the prior error.
    Fake relief scores 0.
    """
    if not hist or len(hist) < 2:
        return 100
    phew_idxs = [i for i, h in enumerate(hist) if h.get("marker") == "PHEW"]
    if not phew_idxs:
        return 100
    scores = []
    for idx in phew_idxs:
        if idx + 1 >= len(hist):
            scores.append(100)
            continue
        lookback = min(5, idx + 1)
        prior_errors = set()
        for j in range(idx - lookback, idx + 1):
            if j < 0:
                continue
            e = hist[j].get("error", "")
            if e:
                prior_errors.add(e.strip().lower())
        if not prior_errors:
            scores.append(100)
            continue
        later = hist[idx + 1]
        recurrence = any(
            later.get("error", "").strip().lower() == e
            for e in prior_errors
        )
        scores.append(0 if recurrence else 100)
    if not scores:
        return 100
    return sum(scores) / len(scores)


def output_momentum(hist, run=None):
    """Return 0-100 measuring whether each step brings new ground.

    First-order measure: fraction of steps whose `next` is new
    to the recent window.  Stuck sessions rehash the same next
    and score near 0.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    unique_nexts = set()
    total_nexts = 0
    for h in run:
        n = h.get("next")
        if n:
            unique_nexts.add(n)
            total_nexts += 1
    if total_nexts == 0:
        return 100
    unique = len(unique_nexts)
    if unique == total_nexts:
        return 100
    return int(unique * 100 / float(total_nexts))


def confidence_verification_alignment(hist, run=None):
    """Return 0-100 measuring how well high confidence matches verification evidence.

    Scores low when recent steps carry ``strong`` or ``shaky`` confidence
    without corresponding verification.  This complements
    :func:`verification_sincerity`, which inspects the *quality* of evidence
    within verified steps, by checking the *presence* of evidence where
    confidence is asserted.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    high = {"shaky", "strong"}
    total = 0
    backed = 0
    for h in run:
        if h.get("confidence", "") in high:
            total += 1
            if h.get("verified", 0) > 0:
                backed += 1
    if total == 0:
        return 100
    return int(backed * 100 / float(total))


def incomplete_verification(hist, run=None):
    """Return 0-100 measuring whether verified steps also record outcomes.

    When a step is marked ``verified`` it should also carry an ``outcome`` so
    downstream analysis can assess result quality.  This complements
    :func:`outcome_completeness` and :func:`verifier_independence` by
    specifically checking for the pair ``verified + outcome``.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    total = 0
    complete = 0
    for h in run:
        if h.get("verified", 0) > 0:
            total += 1
            if h.get("outcome"):
                complete += 1
    if total == 0:
        return 100
    return int(complete * 100 / float(total))


def error_focus(hist, run=None):
    """Return 0-100 measuring whether errors converge or fragment over time.

    Uses the long-range window to see whether the number of distinct error
    categories is shrinking (focused debugging) or growing (unfocused
    symptom chasing).  Different from :func:`error_diversity`, which
    measures raw string uniqueness; this detector sensitive to whether the
    error landscape is becoming more focused.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    prev = None
    stays = 0
    total_pairs = 0
    for h in run:
        e = h.get("error", "").strip().lower()
        if e:
            if prev is not None:
                total_pairs += 1
                if e == prev:
                    stays += 1
            prev = e
    if total_pairs == 0:
        return 100
    return int(stays * 100.0 / total_pairs)


def verification_regression(hist, run=None):
    """Return 0-100 measuring whether verification status is being lost.

    ``verified`` is the cumulative size of the ledger's Verified list, so it
    rises as the session confirms new ground.  Only a *decrease* means
    confirmed ground was lost; a rise is progress and a plateau is stillness,
    which :func:`detect_stall` and :func:`verification_freshness` already
    report.  Scores low on drops, and lower again when a drop is followed by
    a rise, because losing and re-earning verification is churn rather than
    recovery.  This complements :func:`verification_sincerity` and
    :func:`incomplete_verification` by checking temporal stability of
    verification rather than its presence or quality.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    pairs = len(run) - 1
    if pairs < 1:
        return 100
    prev_val = None
    dropped = False
    drops = 0
    churn = 0
    for h in run:
        v = h.get("verified", 0)
        if prev_val is not None:
            if v < prev_val:
                drops += 1
                dropped = True
            elif v > prev_val and dropped:
                churn += 1
        prev_val = v
    if not drops:
        return 100
    penalty = (drops + churn) * 100.0 / pairs
    return max(0, int(100 - penalty))


def step_retry_rate(hist, run=None):
    """Return 0-100 measuring how often the same step is retried.

    Scores low when the same `next` value appears multiple times within
    the long-range window.  This complements :func:`output_momentum`,
    which measures whether steps bring *new* ground, by specifically
    detecting retry cycles within the same step.  A window carrying
    fewer than two next-action strings returns 100; in the recorded
    history schema every entry carries a next string, so that branch is
    a defensive default rather than a reachable state.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    seen = set()
    total = 0
    for h in run:
        n = h.get("next")
        if n:
            total += 1
            seen.add(n)
    if total < 2:
        return 100
    repeats = total - len(seen)
    if repeats == 0:
        return 100
    return max(0, int(100 - (repeats * 100 / float(total))))


def story_switch_detection(hist, book=None, run=None):
    """Return 0-100 measuring whether narrative emphasis shifted without new evidence.

    It measures whether the narrative domain stays stable within the short
    window and does not collapse because a new domain suddenly dominates.
    """
    short, long = STALL_RUN, STALL_RUN * 2
    if not hist or (long >= 6 and len(hist) < long):
        return 100
    window = hist[-short:]
    dom_counts = {}
    first_dom = None
    all_same = True
    for h in window:
        dom = (h.get("next") or "").split(":", 1)[0].strip().lower()
        if not dom and book:
            dom = (one(book, "Next") or "default").split(":", 1)[0].strip().lower()
        dom = dom or "default"
        dom_counts[dom] = dom_counts.get(dom, 0) + 1
        if first_dom is None:
            first_dom = dom
        elif dom != first_dom:
            all_same = False
    if not dom_counts:
        return 100
    def _dominant(counts):
        # A narrative stand needs a repeated domain; with every entry on
        # a different domain there is no stand to switch from, and
        # comparing arbitrary max picks reported phantom switches.
        best, hits = max(counts.items(), key=lambda kv: kv[1])
        return best if hits >= 2 else None
    short_dom = _dominant(dom_counts)
    long_dom = None
    if len(hist) >= long:
        long_win = hist[-long:]
        ldom_counts = {}
        for h in long_win:
            ld = (h.get("next") or "").split(":", 1)[0].strip().lower()
            if not ld and book:
                ld = (one(book, "Next") or "default").split(":", 1)[0].strip().lower()
            ld = ld or "default"
            ldom_counts[ld] = ldom_counts.get(ld, 0) + 1
        if ldom_counts:
            long_dom = _dominant(ldom_counts)
    if long_dom and short_dom and short_dom != long_dom:
        return 25
    return max(0, int(all_same * 100))


def complexity_emission_ratio(hist, run=None):
    """Return 0-100 measuring whether reasoning effort is reflected in outcomes.

    It compares additional-step count to actual delivered outcomes.
    Low ratio = complex reasoning without commensurate deliverables; high ratio = lean and effective reasoning.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    extra = 0
    delivered = 0
    for h in run:
        if h.get("extra_steps", 0) > 0:
            extra += 1
        if h.get("verified", 0) > 0 or h.get("outcome"):
            delivered += 1
    if extra == 0:
        return 100
    if delivered == 0:
        return 0
    ratio = delivered / float(delivered + extra)
    return max(0, min(100, int(ratio * 100)))


def narrative_knot_detector(hist, run=None):
    """Return 0-100 measuring whether narrative becomes unresolved or retreads older threads.

    It measures whether the narrative becomes structured or unresolved.
    A low score indicates that the session is retreading older threads in the long-range window.
    """
    short, long = STALL_RUN, STALL_RUN * 2
    if not hist or len(hist) < long:
        return 100
    recent = hist[-short:]
    prior = hist[:-short]
    if not prior:
        return 100
    prior_nexts = {(r.get("next") or "").strip().lower() for r in prior if r.get("next")}
    short_retread = sum(1 for h in recent if (h.get("next") or "").strip().lower() in prior_nexts)
    if short_retread == 0:
        return 100
    return max(0, int(100 - (short_retread * 100 / float(len(recent)))))


def confidence_inflation(hist, run=None):
    """Return 0-100 measuring whether strong confidence is consistently unverified.

    Scores low when steps carry ``strong`` confidence but lack verification
    evidence.  This complements :func:`confidence_verification_alignment`
    by specifically detecting *unverified* high-confidence claims.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    total = 0
    inflated = 0
    for h in run:
        if h.get("confidence") == "strong":
            total += 1
            if not h.get("verified", 0):
                inflated += 1
    if total == 0:
        return 100
    ratio = inflated / float(total)
    return max(0, min(100, int((1.0 - ratio) * 100)))


def domain_coverage_score(hist, run=None):
    """Return 0-100 measuring whether reasoning spans multiple domains.

    Complements :func:`story_switch_detection` by checking domain *breadth*
    rather than stability.  A low score indicates the session is narrowing
    its focus to a single domain without exploring adjacent concerns.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    short = STALL_RUN * 2
    if not hist or len(hist) < short:
        return 100
    run = hist[-short:]
    domains = set()
    for h in run:
        dom = (h.get("next") or "").split(":", 1)[0].strip().lower()
        if dom:
            domains.add(dom)
    if not domains:
        return 100
    bonus = min(len(domains), 3)
    return max(0, min(100, int((bonus / 3.0) * 100)))


def verification_temporal_bias(hist, run=None):
    """Return 0-100 measuring whether verification is evenly distributed across the window.

    Scores low when verification occurs only at the start or only at the end
    of the window, indicating selective rather than thorough verification.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    long_run = hist[-(STALL_RUN * 2):]
    half = len(long_run) // 2
    fv = sum(1 for h in long_run[:half] if h.get("verified", 0) > 0)
    sv = sum(1 for h in long_run[half:] if h.get("verified", 0) > 0)
    total = fv + sv
    if total == 0:
        return 100
    ideal = total / 2.0
    deviation = abs(fv - ideal) / ideal if ideal > 0 else 0.0
    return max(0, min(100, int((1.0 - deviation) * 100)))


def ledger_stasis_detector(hist, book):
    """Return 0-100 measuring whether the Next action aligns with ledger plan.

    Scores low when planned execution diverges from the ledger Next, indicating
    the session has drifted from its stated plan.  Requires a ledger.
    """
    if not book or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    ledge_next = (one(book, "Next") or "").strip().lower()
    if not ledge_next:
        return 100
    matched = 0
    total = 0
    for h in run:
        n = (h.get("next") or "").strip().lower()
        total += 1
        if n == ledge_next:
            matched += 1
    ratio = matched / float(total) if total else 0.0
    return max(0, min(100, int(ratio * 100)))


def risk_escalation_response(hist, run=None):
    """Return 0-100 measuring whether risk escalation triggers adaptive action changes.

    Scores low when risk rises (low→high) but the next-action domain stays
    the same, suggesting risk is noted but not acted upon.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    esc_count = 0
    adapted = 0
    for i in range(len(run) - 1):
        r1 = (run[i].get("risk") or "").lower()
        r2 = (run[i + 1].get("risk") or "").lower()
        if r1 == "low" and r2 == "high":
            esc_count += 1
            d1 = (run[i].get("next") or "").split(":", 1)[0].strip().lower()
            d2 = (run[i + 1].get("next") or "").split(":", 1)[0].strip().lower()
            if d1 != d2:
                adapted += 1
    if esc_count == 0:
        return 100
    return max(0, min(100, int((adapted / float(esc_count)) * 100)))


def verification_lead_time(hist, run=None):
    """Return 0-100 measuring whether verification tends to precede or follow action.

    High scores mean verification tends to start before new next actions
    (verify-then-act); low scores mean action precedes verification
    (act-then-verify).
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    verify_then_act = 0
    act_then_verify = 0
    for i in range(1, len(run)):
        prev = run[i - 1]
        curr = run[i]
        prev_verified = prev.get("verified", 0) > 0
        curr_open = curr.get("marker") in ("OPEN", "") or not curr.get("verified", 0)
        curr_verified = curr.get("verified", 0) > 0
        prev_open = prev.get("marker") in ("OPEN", "")
        if prev_verified and curr_open:
            verify_then_act += 1
        elif curr_verified and prev_open:
            act_then_verify += 1
    total = verify_then_act + act_then_verify
    if total == 0:
        return 100
    return max(0, min(100, int((verify_then_act / float(total)) * 100)))


def verifier_agreement(hist, run=None):
    """Return 0-100 measuring whether the same verifier produces stable outcomes.

    ``verified`` is a cumulative count, so a rise means the verifier confirmed
    new ground and must not read as a flipped verdict.  Only a *drop* is a
    withdrawn verdict; a rise right after a drop counts again, because ground
    that is lost and re-earned is churn rather than stable agreement.  A
    verifier that never loses ground scores 100 whether it climbs or holds.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    verifier_data = {}
    for h in run:
        v = h.get("verifier")
        if not v:
            continue
        outcome = h.get("verified", 0)
        if v not in verifier_data:
            verifier_data[v] = {"count": 1, "drops": 0, "rebounds": 0,
                                "dropped": False, "prev": outcome}
        else:
            d = verifier_data[v]
            d["count"] += 1
            if outcome < d["prev"]:
                d["drops"] += 1
                d["dropped"] = True
            elif outcome > d["prev"] and d["dropped"]:
                d["rebounds"] += 1
            d["prev"] = outcome
    if not verifier_data:
        return 100
    scores = []
    for v, d in verifier_data.items():
        if d["count"] < 2:
            continue
        total_pairs = d["count"] - 1
        if not d["drops"] or total_pairs <= 0:
            scores.append(100)
            continue
        unstable = d["drops"] + d["rebounds"]
        scores.append(max(0, int(100 - unstable * 100.0 / total_pairs)))
    if not scores:
        return 100
    return int(sum(scores) / len(scores))


def confidence_outcome_tracking(hist, run=None):
    """Return 0-100 measuring how well confidence labels match actual outcomes.

    "strong" confidence should align with success; "shaky" should align
    with errors.  Persistent misalignment indicates miscalibrated confidence.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    pairs = []
    for h in run:
        c = h.get("confidence", "")
        if not c:
            continue
        has_err = bool(h.get("error"))
        verified = h.get("verified", 0) > 0
        pairs.append((c, verified, has_err))
    if not pairs:
        return 100
    aligned = 0
    for conf, verified, has_err in pairs:
        if conf == "strong" and verified and not has_err:
            aligned += 1
        elif conf in ("thin", "shaky") and has_err:
            aligned += 1
        elif conf == "thin" and not has_err and not verified:
            aligned += 1
    return max(0, min(100, int(aligned * 100 / float(len(pairs)))))


def thread_abandonment(hist, run=None):
    """Return 0-100 measuring whether error threads are abandoned cleanly or re-entered.

    Scores low when prev has error=1 and curr continues the same domain with high extra_steps,
    suggesting the session lingers instead of switching context after failure.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN + 1 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    run = hist[-(STALL_RUN + 1):]
    abandoned = 0
    reentered = 0
    for i in range(1, len(run)):
        prev = run[i - 1]
        curr = run[i]
        if prev.get("error") or prev.get("outcome") == "error":
            pd = (prev.get("next") or "").split(":", 1)[0].strip().lower()
            cd = (curr.get("next") or "").split(":", 1)[0].strip().lower()
            if pd == cd and (curr.get("extra_steps") or 0) > 0:
                reentered += 1
            elif pd != cd:
                abandoned += 1
    total = abandoned + reentered
    if total == 0:
        return 100
    return max(0, min(100, int(abandoned * 100 / float(total))))


def error_recovery_depth(hist, run=None):
    """Return 0-100 measuring whether errors trigger extended recovery chains or single-step exits.

    Scores low when consecutive errors end after the next step rather than continuing recovery.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN * 2 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN * 2:
        return 100
    run = hist[-(STALL_RUN * 2):]
    recoveries = []
    i = 0
    while i < len(run):
        if run[i].get("error"):
            depth = 0
            j = i + 1
            while j < len(run) and run[j].get("error"):
                depth += 1
                j += 1
            recoveries.append(depth)
            i = j
        else:
            i += 1
    if not recoveries:
        return 100
    avg = sum(recoveries) / float(len(recoveries))
    ideal = 1.5
    if avg >= ideal:
        return 100
    return max(0, min(100, int(avg * 100 / ideal)))


def step_economy(hist, step_sla=None, run=None):
    """Return 0-100 measuring whether refinement stays within the configured step SLA.

    Scores low when extra_steps exceed the SLA by too much, suggesting the session
    spends unbounded cycles on one item. step_sla defaults to STALL_RUN + 2.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN + 1 entries of ``hist``.
    """
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    run = hist[-(STALL_RUN + 1):]
    sla = step_sla if step_sla is not None else STALL_RUN + 2
    over = 0
    total = 0
    for h in run:
        total += 1
        if (h.get("extra_steps") or 0) > sla:
            over += 1
    ratio = over / float(total) if total else 0.0
    return max(0, min(100, int((1.0 - ratio) * 100)))


def book_thread_alignment(hist, book, run=None):
    """Return 0-100 measuring whether the latest action matches the most recent Open ledger thread.

    Requires a ledger. Tighter than the ledger-plan comparison: it compares
    the last hist entry specifically against the most recent Open ledger
    row, not the generic Next plan. Scores low when the live action
    diverges from the live thread.
    """
    if isinstance(hist, dict):
        hist = [hist]
    if not book or not hist or len(hist) < 1:
        return 100
    opens = book.get("Open", [])
    if not opens:
        return 100
    live_thread = opens[-1].strip().lower()
    if not live_thread:
        return 100
    live_domain = live_thread.split(":", 1)[0].strip().lower()
    last = hist[-1]
    hd = (last.get("next") or "").split(":", 1)[0].strip().lower()
    return 100 if hd == live_domain else 0


def verifier_independence(hist, run=None):
    """Return 0-100 measuring whether verifier diversity is maintained.

    Scores low when a single verifier handles all verification in the window,
    indicating lack of independent cross-check.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    counts = {}
    unique_count = 0
    total = 0
    for h in run:
        v = h.get("verifier")
        if v:
            counts[v] = counts.get(v, 0) + 1
            total += 1
            unique_count = len(counts)
    if total == 0:
        return 100
    max_entropy = math.log(unique_count) if unique_count > 1 else 1.0
    entropy = 0.0
    for c in counts.values():
        if c > 0:
            entropy -= (c / total) * math.log(c / total)
    return max(0, min(100, int((entropy / max_entropy) * 100))) if max_entropy else 100


def output_stub_ratio(hist, run=None):
    """Return 0-100 measuring whether next-actions remain substantive across the window.

    Scores low when next-actions are too short, sparse, or too generic, suggesting
    the session is producing plan stubs instead of real actions.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    stub_count = 0
    generic = ("todo", "next", "continue", "check", "review")
    for h in run:
        nxt = (h.get("next") or "").strip()
        if not nxt or nxt.lower().startswith(generic) or len(nxt) <= 3:
            stub_count += 1
    ratio = 1.0 - stub_count / float(len(run))
    return max(0, min(100, int(ratio * 100)))


def next_action_redundancy(hist, run=None):
    """Return 0-100 measuring consecutive identical next-actions in the window.

    Scores low when the same next-action repeats more than once in a row,
    suggesting the session is stuck repeating the same planned action
    without actually progressing to a new one.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    redundant_pairs = 0
    for i in range(1, len(run)):
        prev = (run[i - 1].get("next") or "").strip().lower()
        curr = (run[i].get("next") or "").strip().lower()
        if prev and curr and prev == curr:
            redundant_pairs += 1
    if not redundant_pairs:
        return 100
    ratio = 1.0 - redundant_pairs / float(STALL_RUN - 1)
    return max(0, min(100, int(ratio * 100)))





def temporal_continuity(hist, run=None):
    """Return 0-100 measuring whether step timestamps progress monotonically.

    Scores low when ``t`` values go backwards, indicating temporal breaks
    in the causal chain. Returns 0 when any backward step is detected so
    the observations() layer can surface a ``temporal discontinuity`` fact.
    Falls back to index order with generous spacing when no monotone
    counter exists.
    The optional ``run`` argument is currently ignored; the window is always the trailing STALL_RUN + 1 entries of ``hist``.
    """
    if isinstance(hist, dict):
        return 100
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    run = hist[-(STALL_RUN + 1):]
    prev_t = int(run[0].get("t", run[0].get("_t", 0)))
    for h in run[1:]:
        curr_t = int(h.get("t", h.get("_t", prev_t + 1)))
        if curr_t < prev_t:
            return 0
        prev_t = curr_t
    return 100


def ledger_volatility(hist, book, run=None):
    """Return 0-100 measuring how often the seam marker flips OPEN/CLOSED.

    Scores low when ``marker`` flips rapidly between OPEN and CLOSED
    across the trailing window, indicating thread churn. The optional
    ``run`` argument is currently ignored; the window is always the
    trailing STALL_RUN + 1 entries of ``hist``.
    """
    if isinstance(hist, dict):
        hist = [hist]
    if not hist or len(hist) < STALL_RUN + 1:
        return 100
    if not book or not book.get("Open"):
        return 100
    run = hist[-(STALL_RUN + 1):]
    opens = book.get("Open", [])
    open_count = len(opens) if opens else 0
    if open_count == 0:
        return 100
    changes = 0
    for i in range(1, len(run)):
        prev_d = run[i - 1].get("marker", "")
        curr_d = run[i].get("marker", "")
        if (prev_d == "OPEN") != (curr_d == "OPEN") or (prev_d == "CLOSED") != (curr_d == "CLOSED"):
            changes += 1
    ratio = 1.0 - changes / float(len(run) - 1)
    return max(0, min(100, int(ratio * 100)))


def verification_completion_ratio(hist, run=None):
    """Return 0-100 measuring whether verification attempts actually complete.

    Scores low when ``verifier`` is populated but ``verified`` is 0,
    indicating verification was started but never concluded.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    attempts = 0
    completions = 0
    for h in run:
        v = h.get("verifier")
        if v:
            attempts += 1
            if h.get("verified", 0):
                completions += 1
    if attempts == 0:
        return 100
    ratio = completions / float(attempts)
    return max(0, min(100, int(ratio * 100)))


def error_recovery_ratio(hist, run=None):
    """Return 0-100 measuring whether errors recover in the following step.

    Scores low when an error step is immediately followed by another
    error step, indicating failure to recover. Complements
    `error_convergence` which looks at domain concentration.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    error_indices = [i for i, h in enumerate(run) if h.get("error")]
    if not error_indices:
        return 100
    recovered = 0
    recoverable = 0
    for i in error_indices:
        if i + 1 < len(run):
            recoverable += 1
            if not run[i + 1].get("error"):
                recovered += 1
    if not recoverable:
        return 100
    ratio = recovered / float(recoverable)
    return max(0, min(100, int(ratio * 100)))


def error_silence_ratio(hist, run=None):
    """Return 0-100 measuring whether error fields contain substantive text.

    Scores low when errors are populated but are short stubs, suggesting
    the session records an error marker without capturing useful diagnostic
    content.  A substantive error description is >= 8 characters.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    total = 0
    substantive = 0
    for h in run:
        err = (h.get("error") or "").strip()
        if err:
            total += 1
            if len(err) >= 8:
                substantive += 1
    if total == 0:
        return 100
    ratio = substantive / float(total)
    return max(0, min(100, int(ratio * 100)))


def verifier_specificity(hist, run=None):
    """Return 0-100 measuring how substantive the verifier text is.

    Scores low when verifier fields contain generic or near-empty stubs,
    suggesting hollow verification coverage rather than meaningful checks.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    total = 0
    specific = 0
    for h in run:
        v = (h.get("verifier") or "").strip()
        if v:
            total += 1
            if len(v) >= 8:
                specific += 1
    if total == 0:
        return 100
    ratio = specific / float(total)
    return max(0, min(100, int(ratio * 100)))


def next_action_specificity(hist, run=None):
    """Return 0-100 measuring whether next-actions carry substantive content.

    Scores low when next-actions are short, generic, or dominated by
    meta-verbs like "think", "check", "continue" that lack actionable
    specificity. A substantive next-action is >= 12 chars and does not
    start with a vague meta-verb.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    vague_starts = ("think", "try", "continue", "retry", "check", "review",
                    "proceed", "move on", "go on", "keep going")
    specific = 0
    for h in run:
        nxt = (h.get("next") or "").strip()
        if len(nxt) >= 12 and not nxt.lower().startswith(vague_starts):
            specific += 1
    ratio = specific / float(len(run))
    return max(0, min(100, int(ratio * 100)))


def reasoning_depth_ratio(hist, run=None):
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    depth_signals = (
        "because", "requires", "needs", "therefore", "however",
        "implement", "refactor", "design", "validate", "test",
        "analyze", "debug", "configure", "deploy", "integrate",
        "resolve", "evidence", "verify", "compare", "assess",
    )
    scored = 0
    for h in run:
        nxt = (h.get("next") or "").strip().lower()
        if not nxt:
            continue
        words = nxt.split()
        word_score = min(len(words) / 4.0, 1.0)
        signal_score = 1.0 if any(sig in nxt for sig in depth_signals) else 0.0
        step_score = (word_score + signal_score) / 2.0
        scored += step_score
    ratio = scored / float(len(run))
    return max(0, min(100, int(ratio * 100)))


def error_acknowledgment_ratio(hist, run=None):
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    accountable = 0
    error_count = 0
    stopwords = {"that", "with", "from"}
    for h in run:
        if h.get("error"):
            error_count += 1
            nxt_text = (h.get("next") or "").lower()
            err_words = set((h.get("error") or "").lower().split())
            meaningful = {w for w in err_words if len(w) > 3 and w not in stopwords}
            if meaningful and any(w in nxt_text for w in meaningful):
                accountable += 1
    if error_count == 0:
        return 100
    ratio = accountable / float(error_count)
    return max(0, min(100, int(ratio * 100)))


def verification_coverage_score(hist, run=None):
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    covered = 0
    total = 0
    for h in run:
        if not h.get("verified"):
            continue
        total += 1
        evidence = (1 if h.get("outcome") else 0) + (1 if h.get("reason") else 0) + (1 if h.get("verifier") else 0)
        if evidence >= 2:
            covered += 1
    if not total:
        return 100
    ratio = covered / float(total)
    return max(0, min(100, int(ratio * 100)))


def marker_transition_diversity(hist, run=None):
    """Return 0-100 measuring whether recorded markers change across the window.

    Reads only the markers actually written: a blank marker is absence,
    not a level, so a blank-to-marked pair is not a transition and a
    fully unmarked window is an unmeasured sequence.  Fewer than two
    recorded markers return the same neutral 100 as a short window —
    the sequence cannot be judged stagnant when it was never written.
    Two or more recorded markers that never change are a stagnant
    sequence (0); any real change among them is progression (100).
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    recorded = [(h.get("marker") or "").strip() for h in run]
    recorded = [m for m in recorded if m]
    if len(recorded) < 2:
        return 100
    return 0 if len(set(recorded)) == 1 else 100


def confidence_presence(hist, run=None):
    """Return 0-100 measuring whether confidence tags appear across steps.

    Scores low when many steps lack a confidence tag, indicating the
    session is operating in auto-pilot without metacognitive assessment.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    present = 0
    for h in run:
        if h.get("confidence"):
            present += 1
    ratio = present / float(len(run))
    return max(0, min(100, int(ratio * 100)))


def error_convergence(hist, run=None):
    """Return 0-100 measuring whether errors converge on one domain or spread out.

    Scores low when the same error domain appears in multiple consecutive
    steps, indicating a persistent unresolved issue rather than a series
    of independent errors.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    dom_counts = {}
    total = 0
    for h in run:
        err = (h.get("error") or "").strip().lower()
        if not err:
            continue
        dom = err.split(":")[0].strip().lower()
        dom_counts[dom] = dom_counts.get(dom, 0) + 1
        total += 1
    if total < 2:
        return 100
    max_count = max(dom_counts.values())
    redundancy = (max_count - 1.0) / (total - 1.0)
    score = int((1.0 - redundancy) * 100)
    return max(0, min(100, score))


def marker_progression(hist, run=None):
    """Return 0-100 measuring whether markers show forward progression.

    Scores low when markers oscillate randomly without moving toward
    terminal states. A healthy sequence advances from OPEN toward DONE.
    Terminal markers (DONE, PHEW, CLOSED) count as progression only
    when following a non-terminal marker. Consecutive identical terminal
    markers indicate a stall.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    terminal = {"DONE", "PHEW", "CLOSED", "SETTLED", "RESOLVED", "CLOSED"}
    prev_marker = None
    marker_count = 0
    advancement = 0.0
    for h in run:
        m = h.get("marker", "").strip().upper()
        if not m:
            continue
        if prev_marker is not None:
            if m in terminal and prev_marker not in terminal:
                advancement += 1
            elif m != prev_marker:
                advancement += 0.5
        marker_count += 1
        prev_marker = m
    if marker_count < 2:
        return 100
    max_advancement = float(marker_count - 1)
    ratio = advancement / max_advancement if max_advancement else 1.0
    return max(0, min(100, int(ratio * 100)))


def verification_freshness(hist, run=None):
    """Return 0-100 measuring how recent the last verification is.

    Scores low when verified is 0 in recent steps and the session has
    been running for many steps without any verifier field populated.
    """
    if not hist or len(hist) < STALL_RUN:
        return 100
    if run is None:
        run = hist[-STALL_RUN:]
    stale = 0
    for h in run:
        if not h.get("verifier") and not h.get("verified"):
            stale += 1
    if not stale:
        return 100
    ratio = 1.0 - stale / float(STALL_RUN)
    return max(0, min(100, int(ratio * 100)))


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


def _info_check_issues(book, hist, gap_seconds):
    """Return the list of issues that ``info --check`` would surface.

    Borrowed from ``git fsck``'s plain-text issue list: a host
    reads the output, the issues are classifiable, and a missing
    issue list is a healthy report. ``read_history`` already
    auto-repairs invalid rows on read, so this function is the
    *classifier* of the same invariants: it walks the ledger
    after the read and reports what the auto-repair would have
    fixed. A CI hook that wants the gate semantics runs
    ``mindseam info --check`` and treats a non-zero exit as a
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


def ensure_dir():
    """Make the ledger directory. Returns an error string, or None on success."""
    try:
        os.makedirs(LEDGER_DIR, exist_ok=True)
    except OSError as exc:
        return "%s (%s)" % (LEDGER_DIR, exc.strerror or "cannot create")
    if not os.path.isdir(LEDGER_DIR):
        return "%s exists but is not a directory" % LEDGER_DIR
    return None


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


def assess_risk(hist):
    """Return risk level and reasons based on recent history patterns.

    Confidence degrade detection reads the ordered confidence levels
    (strong < thin < shaky): a sustained trend — every recent step worse
    than the one before — rates high, and so does a single-step collapse
    of two levels (strong -> shaky), which the old exact-triple pattern
    match silently missed.
    """
    risk_level = "low"
    risk_reasons = []
    if hist:
        confidence_values = []
        marker_values = []
        has_next_flag = False
        for row in hist[-4:]:
            _c = row.get("confidence")
            if _c:
                confidence_values.append(_c)
            _m = row.get("marker")
            if _m:
                marker_values.append(_m)
            if row.get("next"):
                has_next_flag = True
        levels = [CONFIDENCE_LEVEL.get(c, -1) for c in confidence_values]
        degrading_trend = (
            len(levels) >= 3
            and all(lv >= 0 for lv in levels[-3:])
            and levels[-3] < levels[-2] < levels[-1])
        collapsed = (
            len(levels) >= 2
            and levels[-2] >= 0 and levels[-1] >= 0
            and levels[-1] - levels[-2] >= 2)
        if degrading_trend:
            risk_level = "high"
            risk_reasons.append("confidence trend is degrading")
        elif collapsed:
            risk_level = "high"
            risk_reasons.append(
                "confidence collapsed from %s to %s"
                % (confidence_values[-2], confidence_values[-1]))
        elif len(marker_values) >= 2 and len(set(marker_values[-2:])) == 1:
            risk_level = "medium"
            risk_reasons.append("same marker repeated")
        elif len(confidence_values) >= 2 and len(set(confidence_values[-2:])) == 1 and confidence_values[-1] in ("thin", "shaky"):
            risk_level = "medium"
            risk_reasons.append("confidence is stuck")
        elif not confidence_values and not marker_values:
            risk_level = "medium"
            risk_reasons.append("recent entries have no confidence or marker")
        if len(hist[-4:]) >= 3 and has_next_flag is False:
            risk_level = "high"
            risk_reasons.append("recent entries have no next actions")
    return risk_level, risk_reasons


def detect_risk_escalation(hist, run=None):
    """Return escalation facts when risk increases across recent seams."""
    if len(hist) < 2:
        return []
    if run is None:
        run = hist[-STALL_RUN:]
    levels = {"low": 0, "medium": 1, "high": 2}
    recent = []
    prev_lv = None
    valid = True
    increasing = False
    for h in run:
        r = h.get("risk")
        if r:
            recent.append(r)
            lv = levels.get(r, -1)
            if lv < 0:
                valid = False
                break
            if prev_lv is not None and lv > prev_lv:
                increasing = True
            prev_lv = lv
    if len(recent) < 2:
        return []
    if valid and increasing:
        return ["Risk escalated across recent seams: %s." % " -> ".join(recent)]
    return []


def detect_stall(hist, run=None):
    """Return stall facts when the next action or pattern shows no progress."""
    if len(hist) < STALL_RUN:
        return []
    if run is None:
        run = hist[-STALL_RUN:]
    found = []
    first_verified = None
    last_verified = None
    next_ref = None
    next_all_same = True
    for h in run:
        n = h.get("next")
        if n:
            if next_ref is None:
                next_ref = n
            elif n != next_ref:
                next_all_same = False
        v = h.get("verified", 0)
        if first_verified is None:
            first_verified = v
        last_verified = v
    if next_ref and next_all_same:
        found.append("Next action has not changed for %d seams." % len(run))
    if first_verified == last_verified:
        found.append("No new verification across the last %d seams." % len(run))
    return found


def detect_recovery(hist, run=None):
    """Return recovery facts when risk decreases across recent seams."""
    if len(hist) < 2:
        return []
    if run is None:
        run = hist[-STALL_RUN:]
    recent = []
    prev_lv = None
    valid = True
    decreasing = False
    levels = {"low": 0, "medium": 1, "high": 2}
    for h in run:
        r = h.get("risk")
        if r:
            recent.append(r)
            lv = levels.get(r, -1)
            if lv < 0:
                valid = False
                break
            if prev_lv is not None and lv < prev_lv:
                decreasing = True
            prev_lv = lv
    if len(recent) < 2:
        return []
    if valid and decreasing:
        return ["Risk recovered across recent seams: %s." % " -> ".join(recent)]
    return []


CONFIDENCE_LEVEL = {"strong": 0, "thin": 1, "shaky": 2}


def confidence_volatility(hist, run=None):
    """Return the number of confidence changes in the recent window."""
    if len(hist) < 2:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    changes = 0
    prev_lv = None
    for h in run:
        c = h.get("confidence")
        if c:
            lv = CONFIDENCE_LEVEL.get(c, -1)
            if prev_lv is not None and lv != prev_lv:
                changes += 1
            prev_lv = lv
    return changes


def detect_volatility(hist, run=None):
    """Return facts when confidence oscillates rapidly across seams."""
    if len(hist) < STALL_RUN:
        return []
    if run is None:
        run = hist[-STALL_RUN:]
    changes = confidence_volatility(hist, run=run)
    if changes >= 2:
        return ["Confidence oscillated %d times across the last %d seams." % (changes, len(run))]
    return []


def confidence_decay_rate(hist, run=None):
    """Return relative confidence decay rate across the STALL_RUN window (0.0–1.0+)."""
    if len(hist) < 2:
        return 0.0
    if run is None:
        run = hist[-STALL_RUN:]
    start_val = None
    end_val = None
    valid_count = 0
    for h in run:
        c = h.get("confidence")
        if c:
            lv = CONFIDENCE_LEVEL.get(c, -1)
            if lv >= 0:
                if start_val is None:
                    start_val = lv
                end_val = lv
                valid_count += 1
    if valid_count < 2:
        return 0.0
    if start_val == 0 and end_val == 0:
        return 0.0
    if end_val <= start_val:
        # Confidence rising or flat is not decay; reading a recovery as
        # decay punished exactly the sessions that were getting better.
        return 0.0
    span = max(end_val, start_val)
    return (end_val - start_val) / span if span > 0 else 0.0


def stall_score(hist, decay=None, run=None):
    """Return a 0–100 stall severity score from recent STALL_RUN seams."""
    if len(hist) < STALL_RUN:
        return 0
    if run is None:
        run = hist[-STALL_RUN:]
    score = 0
    first_next = None
    first_verified = None
    last_verified = None
    next_set = set()
    for h in run:
        n = h.get("next")
        if n:
            if first_next is None:
                first_next = n
            next_set.add(n)
        v = h.get("verified", 0)
        if first_verified is None:
            first_verified = v
        last_verified = v
    if len(next_set) <= 1 and first_next:
        score += 40
    if first_verified is not None and first_verified == last_verified:
        score += 30
    if decay is None:
        decay = confidence_decay_rate(hist, run=run)
    if decay > 0:
        score += int(decay * 30)
    return min(score, 100)


def coverage_ratio(book):
    """Return the proportion of open items in the ledger (0.0–1.0)."""
    core = len(book.get("Core", []))
    verified = len(book.get("Verified", []))
    opened = len(book.get("Open", []))
    total = core + verified + opened
    if total == 0:
        return 0.0
    return opened / total


def completeness_score(book):
    """Return a 0–100 score representing ledger completion progress."""
    core = len(book.get("Core", []))
    verified = len(book.get("Verified", []))
    opened = len(book.get("Open", []))
    total = core + verified + opened
    if total == 0:
        return 0
    score = int((verified / total) * 100)
    if opened > 10:
        score = max(0, score - (opened - 10) * 2)
    return min(score, 100)


LEDGER_STALE_SEAMS = 8


def stale_core_count(book):
    """Return the number of Core items with no matching Verified anchor."""
    if not book:
        return 0
    core_items = [c.strip() for c in book.get("Core", []) if c.strip()]
    verified_text = " ".join(book.get("Verified", [])).lower()
    count = 0
    for entry in core_items:
        anchor = entry.split(" — ", 1)[1].strip().lower() if " — " in entry else entry.strip().lower()
        if anchor and anchor not in verified_text:
            count += 1
    return count


def detect_ledger_stagnation(hist, book):
    """Return facts when core items remain unverified across many seams."""
    if not book:
        return []
    core = book.get("Core", [])
    if not core:
        return []
    stale = stale_core_count(book)
    if stale == 0:
        return []
    if len(hist) < LEDGER_STALE_SEAMS:
        return []
    if hist[-LEDGER_STALE_SEAMS].get("verified", 0) == hist[-1].get("verified", 0):
        return ["%d core item(s) have gone unverified across %d seams." % (stale, LEDGER_STALE_SEAMS)]
    return []


def compound_pattern_facts(hist, book=None, st_score=None, vol_changes=None, run=None):
    """Return facts when multiple risk dimensions fire simultaneously."""
    facts = []
    risk_high = False
    confidence_weak = False
    ledger_stale = False
    stalled = False
    if len(hist) >= STALL_RUN:
        if run is None:
            run = hist[-STALL_RUN:]
        risk_high = False
        confidence_weak = False
        for h in run:
            if not risk_high and h.get("risk") in ("medium", "high"):
                risk_high = True
            if not confidence_weak and h.get("confidence") in ("thin", "shaky"):
                confidence_weak = True
        if not confidence_weak and vol_changes is not None and vol_changes >= 2:
            confidence_weak = True
        if st_score is not None and st_score >= 30:
            stalled = True
    if book is not None:
        if stale_core_count(book) > 0 and len(hist) >= LEDGER_STALE_SEAMS:
            it = iter(hist[-LEDGER_STALE_SEAMS:])
            first_v = next(it, {}).get("verified", 0) if hist[-LEDGER_STALE_SEAMS:] else 0
            last_v = hist[-1].get("verified", 0)
            if first_v == last_v:
                ledger_stale = True
    signals = 0
    if risk_high:
        signals += 1
    if confidence_weak:
        signals += 1
    if ledger_stale:
        signals += 1
    if stalled:
        signals += 1
    if signals >= 2:
        active = []
        if risk_high:
            active.append("risk")
        if confidence_weak:
            active.append("confidence")
        if ledger_stale:
            active.append("ledger")
        if stalled:
            active.append("progress")
        facts.insert(
            0,
            "Compound pattern: %s signals firing together — %s."
            % (signals, ", ".join(active)),
        )
    return facts


class _HealthResult:
    __slots__ = (
        "score",
        "reasons",
        "vol_changes",
        "decay",
        "st_score",
        "compound",
        "risk_esc",
        "has_stall",
    )

    def __init__(self, score, reasons, vol_changes, decay, st_score, compound, risk_esc=False, has_stall=False):
        self.score = score
        self.reasons = reasons
        self.vol_changes = vol_changes
        self.decay = decay
        self.st_score = st_score
        self.compound = compound
        self.risk_esc = risk_esc
        self.has_stall = has_stall

    def __iter__(self):
        return iter((self.score, self.reasons))


def _fuse_run(hist, run=None):
    if len(hist) < STALL_RUN:
        return (0, 0.0, 0, False, False, False, None, False, False, False)
    if run is None:
        run = hist[-STALL_RUN:]
    valid_count = 0
    first_valid = None
    last_valid = None
    next_set = set()
    real_nexts = []
    first_verified = None
    last_verified = None
    vol_changes = 0
    prev_lv = None
    last_risk = "low"
    risk_escalated = False
    risk_recovered = False
    prev_rv = None
    levels = {"low": 0, "medium": 1, "high": 2}
    has_risk = False
    has_weak_conf = False
    has_verified = False
    for h in run:
        n = h.get("next")
        if n:
            next_set.add(n)
            real_nexts.append(n)
        c = h.get("confidence")
        if c:
            lv = CONFIDENCE_LEVEL.get(c, -1)
            if lv >= 0:
                valid_count += 1
                if first_valid is None:
                    first_valid = lv
                last_valid = lv
                if prev_lv is not None and lv != prev_lv:
                    vol_changes += 1
                prev_lv = lv
            if c in ("thin", "shaky"):
                has_weak_conf = True
        v = h.get("verified", 0)
        if first_verified is None:
            first_verified = v
        last_verified = v
        if v > 0:
            has_verified = True
        r = h.get("risk")
        if r in ("medium", "high"):
            has_risk = True
        if r and r in levels:
            last_risk = r
            rv = levels[r]
            if prev_rv is not None:
                if rv > prev_rv:
                    risk_escalated = True
                elif rv < prev_rv:
                    risk_recovered = True
            prev_rv = rv
    decay = 0.0
    if valid_count >= 2:
        start_val, end_val = first_valid, last_valid
        if not (start_val == 0 and end_val == 0) and end_val > start_val:
            span = max(end_val, start_val)
            decay = (end_val - start_val) / span if span > 0 else 0.0
    s = 0
    if len(next_set) == 1 and real_nexts:
        s += 40
    if first_verified is not None and first_verified == last_verified:
        s += 30
    if decay > 0:
        s += int(decay * 30)
    st_score = min(s, 100)
    has_stall = bool(real_nexts) and len(next_set) == 1
    return (vol_changes, decay, st_score, has_stall, risk_escalated, risk_recovered, last_risk, has_risk, has_weak_conf, has_verified)


def session_health_score(hist, book=None, run=None):
    """Return health score from 0-100 based on recent session patterns."""
    score = 100
    reasons = []
    if isinstance(hist, dict):
        hist = [hist]
    if not hist or len(hist) < STALL_RUN:
        # Below the minimum window the score cannot measure anything, so it
        # returns the same neutral 100 the detectors themselves return for
        # unmeasurable inputs — with no reasons, because every line below
        # this guard would judge a session too short to judge. observations
        # applies the identical window guard to its facts.
        empty = _HealthResult(score, reasons, 0, 0.0, 0, None, False, False)
        return empty
    if run is None:
        run = hist[-STALL_RUN:]
    recent = hist[-3:]
    confidence_hits = {"thin": 0, "shaky": 0}
    last_markers = []
    for row in recent:
        c = row.get("confidence", "")
        if c in confidence_hits:
            confidence_hits[c] += 1
        m = row.get("marker")
        if m:
            last_markers.append(m)
            if len(last_markers) > 2:
                last_markers.pop(0)
    # One aggregated line per label: two shaky steps used to print the
    # identical "shaky confidence (-15)" line twice.
    for label, penalty in (("shaky", -15), ("thin", -5)):
        hits = confidence_hits[label]
        if hits:
            score += penalty * hits
            reasons.append("%s confidence x%d (%+d)"
                           % (label, hits, penalty * hits))
    if len(last_markers) >= 2 and last_markers[0] == last_markers[1]:
        score -= 10
        reasons.append("repeated marker (-10)")
    last_risk = (
        next((h.get("risk") for h in reversed(hist) if h.get("risk")), "low")
    )
    risk_penalty = {"high": -20, "medium": -10, "low": 0}
    if last_risk != "low":
        score += risk_penalty[last_risk]
        reasons.append("%s risk (%+d)" % (last_risk, risk_penalty[last_risk]))
    vol_changes, decay, st_score, has_stall, risk_esc, risk_rec, last_risk, has_risk, has_weak_conf, has_verified = _fuse_run(hist, run=run)
    if risk_esc:
        score -= 15
        reasons.append("risk escalation (-15)")
    if risk_rec:
        score += 10
        reasons.append("recovery signal (+10)")
    if vol_changes >= 2:
        score -= 20
        reasons.append("confidence oscillation (-20)")
    if decay >= 0.6:
        score -= int(decay * 15)
        reasons.append("confidence decay %.0f%% (-%d)" % (decay * 100, int(decay * 15)))
    if st_score >= 60:
        score -= 15
        reasons.append("high stall severity %d/100 (-15)" % st_score)
    elif st_score >= 30:
        score -= 8
        reasons.append("moderate stall %d/100 (-8)" % st_score)
    compound = False
    signals = 0
    if has_risk:
        signals += 1
    if has_weak_conf or vol_changes >= 2:
        signals += 1
    if book is not None and stale_core_count(book) > 0 and len(hist) >= LEDGER_STALE_SEAMS:
        if hist[-LEDGER_STALE_SEAMS].get("verified", 0) == hist[-1].get("verified", 0):
            signals += 1
    if st_score >= 30:
        signals += 1
    if signals >= 2:
        compound = True
        active = []
        if has_risk:
            active.append("risk")
        if has_weak_conf or vol_changes >= 2:
            active.append("confidence")
        if book is not None and stale_core_count(book) > 0 and len(hist) >= LEDGER_STALE_SEAMS:
            if hist[-LEDGER_STALE_SEAMS].get("verified", 0) == hist[-1].get("verified", 0):
                active.append("ledger")
        if st_score >= 30:
            active.append("progress")
        score -= 10
        reasons.append("compound pattern (-10)")
    mm = session_momentum(hist)
    if mm == "positive":
        vel = momentum_velocity(hist)
        score += 5
        reasons.append("positive momentum (+5, velocity %.0f%%)" % (vel * 100))
    elif mm == "negative":
        score -= 5
        reasons.append("negative momentum (-5)")
    ta = trend_acceleration(hist)
    if ta == "accelerating":
        score += 5
        reasons.append("trend accelerating (+5)")
    elif ta == "decelerating":
        score -= 5
        reasons.append("trend decelerating (-5)")
    conv = convergence_index(hist, run=run)
    if conv >= 75:
        score += 5
        reasons.append("high signal convergence +5")
    elif conv < 30:
        score -= 5
        reasons.append("low signal convergence -5")
    pp = pattern_persistence(hist, run=run)
    if pp == "chronic":
        score -= 5
        reasons.append("chronic pattern (-5)")
    elif pp == "transient":
        score += 5
        reasons.append("transient pattern (+5)")
    sf = session_fatigue(hist, run=run)
    if sf >= 60:
        score -= 5
        reasons.append("high session fatigue -5")
    elif sf < 20:
        score += 5
        reasons.append("low session fatigue +5")
    er = entropy_reservoir(hist, run=run)
    if er < 0.3:
        score -= 5
        reasons.append("low workspace entropy -5")
    cl = cognitive_load_index(hist, run=run, ent=er)
    if cl >= 60:
        score -= 5
        reasons.append("high cognitive load -5")
    dv = drift_velocity(hist, run=run)
    if dv >= 0.66:
        score -= 5
        reasons.append("high action drift -5")
    vd = verification_depth(hist, run=run)
    if vd <= 1 and has_verified:
        score -= 5
        reasons.append("shallow verification depth -5")
    if score >= 75 and (risk_esc or has_stall or compound):
        score -= 5
        reasons.append("possible premature convergence -5")
    rr = resolution_rate(hist, run=run)
    if rr < 0.4:
        score -= 5
        reasons.append("low thread resolution %.0f%% -5" % (rr * 100))
    loop = loop_detection(hist, run=run)
    if loop:
        score -= 5
        reasons.append("next-action loop detected -5")
    ec = escalation_likelihood(hist, run=run)
    if ec >= 50:
        score -= 5
        reasons.append("high escalation likelihood %d/100 -5" % ec)
    cd = contradiction_detection(hist)
    if cd:
        score -= 5
        reasons.append("risk-confidence contradiction -5")
    ew = evidence_weight(hist)
    if ew < 30:
        score -= 5
        reasons.append("low evidence weight %d/100 -5" % ew)
    cal = confidence_calibration_error(hist)
    if cal >= 60:
        score -= 5
        reasons.append("high calibration error %d/100 -5" % cal)
    ad = adaptability_score(hist)
    if ad < 30:
        score -= 5
        reasons.append("low adaptability %d/100 -5" % ad)
    elif ad >= 80:
        score += 5
        reasons.append("high adaptability %d/100 +5" % ad)
    lr = learning_rate(hist)
    if lr < 0.3:
        score -= 5
        reasons.append("low learning rate %.0f%% -5" % (lr * 100))
    tr = tension_resolution(hist, run=run)
    if tr < 30:
        score -= 5
        reasons.append("low tension resolution %d/100 -5" % tr)
    elif tr >= 70:
        score += 5
        reasons.append("high tension resolution %d/100 +5" % tr)
    # Measurement-presence flags. Several detectors answer "nothing to
    # measure" with the same sentinel 100 they award to measured
    # perfection, so their fusion branches are gated on whether the
    # quantity was actually observed (convention introduced by the
    # goal_set / ledger-plan gates below). Each flag mirrors the exact
    # window and counting rule of its detector, including the minimum
    # window length, so a short history cannot smuggle the sentinel
    # through an open gate.
    win4 = hist[-(STALL_RUN + 1):]
    win6 = hist[-(STALL_RUN * 2):]

    def _pair_seen(entries, pred):
        return any(pred(entries[i], entries[i + 1])
                   for i in range(len(entries) - 1))

    # Fused run-window signal-presence gates — replaces ~12 separate
    # any()/sum()/list-comprehension passes over the same slices.
    # Extended to cover win6 (last 6 entries) with position-aware flags
    # for win4/win6 gates while preserving the run-level (last 3) logic.
    verified_in_run = False
    hi_conf_in_run = False
    strong_conf_in_run = False
    conf_label_in_run = False
    verifier_in_run = False
    marker_count = 0
    adj_next_pair = False
    done_any3 = False
    effort_or_delivery3 = False
    err_events3x2_count = 0
    next_in3_found = False
    verified_in_win6 = False
    err_in_win4_count = 0
    err_in_win6_count = 0
    risk_high_seen = False
    risk_low_seen = False
    next_in_win4_found = False
    domain_in_win6_found = False
    run_start = len(win6) - STALL_RUN
    prev_has_next_run = False
    for idx, h in enumerate(win6):
        in_run = idx >= run_start
        in_win4 = idx >= len(win6) - len(win4)
        if in_run:
            if h.get("verified", 0) > 0:
                verified_in_run = True
            c = h.get("confidence")
            if c in ("strong", "shaky"):
                hi_conf_in_run = True
            if c == "strong":
                strong_conf_in_run = True
            if (c or "").strip():
                conf_label_in_run = True
            if (h.get("verifier") or "").strip():
                verifier_in_run = True
            if (h.get("marker") or "").strip():
                marker_count += 1
                if h.get("marker") == "DONE":
                    done_any3 = True
            if (h.get("extra_steps") or 0) > 0 or h.get("verified", 0) > 0 or h.get("outcome"):
                effort_or_delivery3 = True
            _e = (h.get("error") or "").strip()
            if _e:
                err_events3x2_count += 1
            has_n = bool((h.get("next") or "").strip())
            if has_n:
                next_in3_found = True
            if prev_has_next_run and has_n:
                adj_next_pair = True
            prev_has_next_run = has_n
        if h.get("verified", 0) > 0:
            verified_in_win6 = True
        if in_win4:
            if h.get("error") or h.get("verified", 0) < 0:
                err_in_win4_count += 1
            if (h.get("next") or "").strip():
                next_in_win4_found = True
        _e_w6 = (h.get("error") or "").strip()
        if _e_w6:
            err_in_win6_count += 1
        r = (h.get("risk") or "").lower()
        if r == "high":
            risk_high_seen = True
        elif r == "low":
            risk_low_seen = True
        if (h.get("next") or "").split(":", 1)[0].strip():
            domain_in_win6_found = True
    marker_pair_in_run = marker_count >= 2
    adjacent_next_pair_in_run = adj_next_pair
    err_events3x2 = len(hist) >= STALL_RUN and err_events3x2_count >= 2
    next_in3 = next_in3_found
    err_events4 = len(hist) >= STALL_RUN + 1 and err_in_win4_count >= 1
    err_subseq6 = err_in_win6_count
    err_pairs6 = len(hist) >= STALL_RUN * 2 and err_subseq6 >= 2
    verified6 = len(hist) >= STALL_RUN * 2 and verified_in_win6
    esc6 = len(hist) >= STALL_RUN * 2 and _pair_seen(
        win6, lambda a, b: (a.get("risk") or "").lower() == "low"
        and (b.get("risk") or "").lower() == "high")
    vt6 = len(hist) >= STALL_RUN * 2 and _pair_seen(
        win6, lambda a, b: (a.get("verified", 0) > 0
                            and (b.get("marker") in ("OPEN", "")
                                 or not b.get("verified", 0)))
        or (b.get("verified", 0) > 0 and a.get("marker") in ("OPEN", "")))
    va_measured = False
    if len(hist) >= STALL_RUN * 2:
        seen_names = {}
        for h in win6:
            v = h.get("verifier")
            if v:
                seen_names[v] = seen_names.get(v, 0) + 1
                if seen_names[v] >= 2:
                    va_measured = True
                    break
    thread_evt4 = False
    if len(hist) >= STALL_RUN + 1:
        for i in range(1, len(win4)):
            p = win4[i - 1]
            if p.get("error") or p.get("outcome") == "error":
                pd = (p.get("next") or "").split(":", 1)[0].strip().lower()
                cd = (win4[i].get("next") or "").split(":", 1)[0].strip().lower()
                if pd != cd or (pd == cd
                                and (win4[i].get("extra_steps") or 0) > 0):
                    thread_evt4 = True
                    break
    high_low_risk6 = len(hist) >= STALL_RUN * 2 and risk_high_seen and risk_low_seen
    next_in4 = len(hist) >= STALL_RUN + 1 and next_in_win4_found
    domain_in6 = len(hist) >= STALL_RUN * 2 and domain_in_win6_found
    err_recoverable = any(
        h.get("error") and h.get("verified", 0) == 0 and not h.get("outcome")
        for h in hist)
    ers = error_recovery_speed(hist)
    if err_recoverable:
        if ers < 40:
            score -= 5
            reasons.append("slow error recovery %d/100 -5" % ers)
        elif ers >= 80:
            score += 5
            reasons.append("fast error recovery %d/100 +5" % ers)
    oc = outcome_completeness(hist)
    if oc < 30:
        score -= 5
        reasons.append("low outcome completeness %d%% -5" % oc)
    ga = goal_alignment_score(hist, book=book)
    goal_set = bool(book) and bool((one(book, "Goal") or "").strip())
    if goal_set:
        # Without a stated goal the detector returns a sentinel 100; scoring
        # that as "high goal alignment" would reward a measurement that
        # never happened (same gate convention as ledger_volatility below).
        if ga < 30:
            score -= 5
            reasons.append("low goal alignment %d/100 -5" % ga)
        elif ga >= 80:
            score += 5
            reasons.append("high goal alignment %d/100 +5" % ga)
    ce = cognitive_efficiency(hist)
    if ce < 30:
        score -= 5
        reasons.append("low cognitive efficiency %d/100 -5" % ce)
    elif ce >= 80:
        score += 5
        reasons.append("high cognitive efficiency %d/100 +5" % ce)
    tm = thread_management(hist)
    if next_in4:
        if tm < 30:
            score -= 5
            reasons.append("low thread management %d/100 -5" % tm)
        elif tm >= 80:
            score += 5
            reasons.append("high thread management %d/100 +5" % tm)
    roc = risk_outcome_correlation(hist)
    if high_low_risk6:
        if roc < 30:
            score -= 5
            reasons.append("poor risk outcome correlation %d/100 -5" % roc)
        elif roc >= 80:
            score += 5
            reasons.append("good risk outcome correlation %d/100 +5" % roc)
    ad = assumption_diversity(hist, book=book)
    if conf_label_in_run:
        # Without labels the detector collapses to one "unknown" bucket and
        # scores 0 — absence of confidence tags, which confidence_presence
        # already reports as its designed signal. Punishing the same
        # absence again under a "diversity" name would double-count it.
        if ad < 30:
            score -= 5
            reasons.append("low assumption diversity %d/100 -5" % ad)
        elif ad >= 80:
            score += 5
            reasons.append("high assumption diversity %d/100 +5" % ad)
    ed = error_diversity(hist)
    if err_events4:
        if ed < 30:
            score -= 5
            reasons.append("low error diversity %d/100 -5" % ed)
        elif ed >= 80:
            score += 5
            reasons.append("high error diversity %d/100 +5" % ed)
    cva = confidence_verification_alignment(hist, run=run)
    if cva < 30:
        score -= 5
        reasons.append("low confidence-verification alignment %d/100 -5" % cva)
    elif hi_conf_in_run and cva >= 80:
        score += 5
        reasons.append("high confidence-verification alignment %d/100 +5" % cva)
    iv = incomplete_verification(hist, run=run)
    if verified_in_run:
        if iv < 30:
            score -= 5
            reasons.append("incomplete verification %d/100 -5" % iv)
        elif iv >= 80:
            score += 5
            reasons.append("complete verification %d/100 +5" % iv)
    ef = error_focus(hist)
    if err_pairs6:
        if ef < 30:
            score -= 5
            reasons.append("low error focus %d/100 -5" % ef)
        elif ef >= 80:
            score += 5
            reasons.append("high error focus %d/100 +5" % ef)
    vs = verification_sincerity(hist)
    if vs < 30:
        score -= 5
        reasons.append("low verification sincerity %d/100 -5" % vs)
    kr = knowledge_retention(hist)
    if kr < 30:
        score -= 5
        reasons.append("low knowledge retention %d/100 -5" % kr)
    ore = outcome_reliability(hist)
    if ore < 30:
        score -= 5
        reasons.append("low outcome reliability %d/100 -5" % ore)
    er = evidence_recency(hist)
    if er < 30:
        score -= 5
        reasons.append("low evidence recency %d/100 -5" % er)
    tr = temporal_regularity(hist)
    if tr < 30:
        score -= 5
        reasons.append("low temporal regularity %d/100 -5" % tr)
    ms = meta_stability(hist)
    if ms < 30:
        score -= 5
        reasons.append("low meta stability %d/100 -5" % ms)
    fa = feedback_amplification(hist)
    if fa < 30:
        score -= 5
        reasons.append("feedback amplification %d/100 -5" % fa)
    re_eff = reset_efficacy(hist)
    if re_eff < 30:
        score -= 5
        reasons.append("low reset efficacy %d/100 -5" % re_eff)
    om = output_momentum(hist, run=run)
    if om <= 33:
        score -= 5
        reasons.append("low output momentum %d/100 -5" % om)
    vr = verification_regression(hist)
    if vr <= 25:
        score -= 5
        reasons.append("verification regression %d/100 -5" % vr)
    elif verified_in_run and vr >= 80:
        # The scalar reads 100 both for a plateau that held real checks and
        # for a window where verification never appeared; only the former
        # is "stable verification". The penalty face needs no gate: a score
        # at or below 25 mathematically requires a drop to exist.
        score += 5
        reasons.append("stable verification %d/100 +5" % vr)
    rr = step_retry_rate(hist)
    if rr <= 25:
        score -= 5
        reasons.append("high step retry rate %d/100 -5" % rr)
    elif rr >= 80:
        score += 5
        reasons.append("low step retry rate %d/100 +5" % rr)
    pc = premature_convergence(hist, book=book, score=True)
    if done_any3:
        # The scalar reads 100 both for measured convergence (DONE steps
        # that carry verification) and for histories with no DONE step at
        # all; only the former may earn the bonus. The penalty face needs
        # no extra gate: a score below 30 mathematically requires a
        # DONE-without-verification step to exist.
        if pc < 30:
            score -= 5
            reasons.append("premature convergence %d/100 -5" % pc)
        elif pc >= 80:
            score += 5
            reasons.append("late convergence %d/100 +5" % pc)
    sd = story_switch_detection(hist, book=book)
    if sd < 30:
        score -= 5
        reasons.append("story switch %d/100 -5" % sd)
    elif next_in3 and sd >= 80:
        score += 3
        reasons.append("stable story %d/100 +3" % sd)
    cer = complexity_emission_ratio(hist)
    if effort_or_delivery3:
        if cer < 30:
            score -= 5
            reasons.append("complexity-emission ratio %d/100 -5" % cer)
        elif cer >= 80:
            score += 5
            reasons.append("lean effective reasoning %d/100 +5" % cer)
    nk = narrative_knot_detector(hist)
    if nk < 30:
        score -= 5
        reasons.append("narrative knot %d/100 -5" % nk)
    elif len(hist) >= STALL_RUN * 2 and next_in3 and nk >= 80:
        score += 3
        reasons.append("narrative resolution %d/100 +3" % nk)
    ci = confidence_inflation(hist)
    if ci < 30:
        score -= 5
        reasons.append("confidence inflation %d/100 -5" % ci)
    elif strong_conf_in_run and ci >= 80:
        score += 3
        reasons.append("verified confidence %d/100 +3" % ci)
    dcs = domain_coverage_score(hist)
    if dcs < 50:
        score -= 3
        reasons.append("narrow domain coverage %d/100 -3" % dcs)
    elif domain_in6 and dcs >= 80:
        score += 3
        reasons.append("broad domain coverage %d/100 +3" % dcs)
    vtb = verification_temporal_bias(hist)
    if verified6:
        if vtb < 30:
            score -= 5
            reasons.append("verification temporal bias %d/100 -5" % vtb)
        elif vtb >= 80:
            score += 3
            reasons.append("even verification distribution %d/100 +3" % vtb)
    ls = ledger_stasis_detector(hist, book)
    if isinstance(book, dict) and (one(book, "Next") or "").strip():
        # Without a ledger the detector returns a sentinel 100; rewarding
        # that as "ledger plan alignment" would score a measurement that
        # never happened (same gate convention as ledger_volatility below).
        if ls < 30:
            score -= 5
            reasons.append("ledger plan divergence %d/100 -5" % ls)
        elif ls >= 80:
            score += 3
            reasons.append("ledger plan alignment %d/100 +3" % ls)
    rer = risk_escalation_response(hist)
    if esc6:
        if rer < 30:
            score -= 5
            reasons.append("risk escalation not adapted %d/100 -5" % rer)
        elif rer >= 80:
            score += 3
            reasons.append("adaptive risk response %d/100 +3" % rer)
    vlt = verification_lead_time(hist)
    if vt6:
        if vlt < 30:
            score -= 3
            reasons.append("act-then-verify %d/100 -3" % vlt)
        elif vlt >= 80:
            score += 3
            reasons.append("verify-then-act %d/100 +3" % vlt)
    va = verifier_agreement(hist)
    if va_measured:
        if va < 30:
            score -= 5
            reasons.append("verifier disagreement %d/100 -5" % va)
        elif va >= 80:
            score += 3
            reasons.append("verifier consensus %d/100 +3" % va)
    cot = confidence_outcome_tracking(hist)
    if cot < 30:
        score -= 5
        reasons.append("confidence-outcome misalignment %d/100 -5" % cot)
    elif conf_label_in_run and cot >= 80:
        score += 3
        reasons.append("calibrated confidence %d/100 +3" % cot)
    ta = thread_abandonment(hist)
    if thread_evt4:
        if ta < 30:
            score -= 5
            reasons.append("thread abandonment %d/100 -5" % ta)
        elif ta >= 80:
            score += 3
            reasons.append("thread recovery %d/100 +3" % ta)
    se = step_economy(hist)
    if se < 30:
        score -= 5
        reasons.append("step economy %d/100 -5" % se)
    elif se >= 80:
        score += 3
        reasons.append("lean refinement %d/100 +3" % se)
    vi = verifier_independence(hist)
    if vi < 30:
        score -= 5
        reasons.append("verifier concentration %d/100 -5" % vi)
    elif verifier_in_run and vi >= 80:
        score += 3
        reasons.append("verifier diversity %d/100 +3" % vi)
    osr = output_stub_ratio(hist)
    if osr < 30:
        score -= 5
        reasons.append("output stub ratio %d/100 -5" % osr)
    elif osr >= 80:
        score += 3
        reasons.append("substantive actions %d/100 +3" % osr)
    nar = next_action_redundancy(hist)
    if nar < 30:
        score -= 5
        reasons.append("action redundancy %d/100 -5" % nar)
    elif adjacent_next_pair_in_run and nar >= 80:
        score += 3
        reasons.append("action diversity %d/100 +3" % nar)
    ec = error_convergence(hist)
    if err_events3x2:
        if ec < 30:
            score -= 5
            reasons.append("error clustering %d/100 -5" % ec)
        elif ec >= 80:
            score += 3
            reasons.append("errors spread across domains %d/100 +3" % ec)
    mp = marker_progression(hist)
    if mp < 30:
        score -= 3
        reasons.append("marker stall %d/100 -3" % mp)
    elif marker_pair_in_run and mp >= 75:
        score += 3
        reasons.append("marker progress %d/100 +3" % mp)
    fc = verification_freshness(hist)
    if fc < 30:
        score -= 3
        reasons.append("stale verification %d/100 -3" % fc)
    elif fc >= 80:
        score += 3
        reasons.append("fresh verification %d/100 +3" % fc)
    tc = temporal_continuity(hist)
    if tc < 30:
        score -= 3
        reasons.append("temporal discontinuity %d/100 -3" % tc)
    vl = ledger_volatility(hist, book) if isinstance(book, dict) else 100
    if vl < 30:
        score -= 3
        reasons.append("Open thread churn %d/100 -3" % vl)
    vcr = verification_completion_ratio(hist)
    if vcr < 30:
        score -= 3
        reasons.append("verifications left open %d/100 -3" % vcr)
    err_r = error_recovery_ratio(hist)
    if err_r < 30:
        score -= 3
        reasons.append("error recovery failure %d/100 -3" % err_r)
    esr = error_silence_ratio(hist)
    if esr < 30:
        score -= 3
        reasons.append("error description too short %d/100 -3" % esr)
    vs = verifier_specificity(hist)
    if vs < 30:
        score -= 3
        reasons.append("verifier specificity low %d/100 -3" % vs)
    nas = next_action_specificity(hist)
    if nas < 30:
        score -= 3
        reasons.append("next-action specificity low %d/100 -3" % nas)
    cp = confidence_presence(hist)
    if cp < 30:
        score -= 3
        reasons.append("confidence presence low %d/100 -3" % cp)
    rdr = reasoning_depth_ratio(hist)
    if rdr < 30:
        score -= 3
        reasons.append("reasoning depth shallow %d/100 -3" % rdr)
    ear = error_acknowledgment_ratio(hist)
    if ear < 30:
        score -= 3
        reasons.append("error not acknowledged %d/100 -3" % ear)
    vcs = verification_coverage_score(hist)
    if vcs < 30:
        score -= 3
        reasons.append("verification coverage thin %d/100 -3" % vcs)
    mtd = marker_transition_diversity(hist)
    if marker_pair_in_run and mtd < 30:
        # The penalty face needs the same presence flag as the bonus face
        # above: without two recorded markers the detector returns the
        # unmeasured sentinel, and absence must not read as stagnation.
        score -= 3
        reasons.append("marker sequence stagnant %d/100 -3" % mtd)
    score = max(0, min(100, score))
    return _HealthResult(score, reasons, vol_changes, decay, st_score, compound, risk_esc, has_stall)


def grade(score):
    """Return letter grade from numeric score."""
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


REMEDIATION_MAP = (
    ("confidence trend shows degradation",
     "Confidence is degrading — revisit the initial premises now.", 0),
    ("next action has not changed",
     "The next action has not moved — pivot to a genuinely different step or close the thread.", 1),
    ("escalated",
     "Risk is climbing — confirm the cause and set a checkpoint before continuing.", 2),
    ("outcomes are inaccessible",
     "Verified steps carry no outcome — record --outcome so results can be audited.", 3),
    ("no new verification",
     "Verification has stopped growing — run one check and record it with --check and --by.", 4),
    ("gone unverified",
     "Core items have gone unverified — run one check against the oldest core item.", 5),
    ("oscillated",
     "Confidence keeps shifting — consolidate one stable framing before the next step.", 6),
    ("stall severity",
     "Session has stalled — define one explicit next action with an acceptance test.", 7),
    ("recovered",
     "Risk has improved — use the momentum to probe at least one open item.", 8),
)


def remediation_suggestions(facts, score, book=None):
    """Turn observation facts + health score into an ordered action list.

    Fact-keyed advice sorts by the REMEDIATION_MAP priority (lowest is
    most severe), ledger coverage and completeness lines follow the
    fact advice, and the critical-stress line hoists to the front when
    the score drops below 30.
    """
    matched = []
    for fact in facts:
        fact_lower = fact.lower()
        for key, text, priority in REMEDIATION_MAP:
            if key in fact_lower:
                matched.append((priority, text))
                break
    matched.sort()
    suggestions = [entry[1] for entry in matched]
    cov = coverage_ratio(book) if book is not None else 0.0
    comp = completeness_score(book) if book is not None else 100
    if cov >= 0.7 and not any("ledger" in s.lower() for s in suggestions):
        suggestions.append("Ledger coverage is high (%d%% open) — label the cheapest open item for closure." % int(cov * 100))
    if comp < 20 and book and (book.get("Core") or book.get("Open")):
        suggestions.append("Ledger completeness is low (%d/100) — verify at least one core item." % comp)
    if score < 30:
        suggestions.insert(0, "Session is critically stressed — suspend and re-open with a fresh ledger entry.")
    return list(dict.fromkeys(suggestions))[:6]


def mode_seam(book, json_flag=False, dry_run=False, quiet=False, message=None,
            from_stdin=False):
    """Run a seam: re-anchor, record a history row, surface observations.

    ``--json`` mirrors the full text report machine-readably; ``--quiet``
    prints only the fact lines; ``--dry-run`` skips the history append;
    ``--message`` annotates the recorded row; ``--from-stdin`` records
    one row per input line.
    """
    extra_nexts = []
    if from_stdin:
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
    hist, _, repair_reasons = read_history()
    gap = int(time.time()) - hist[-1]["t"] if hist else 0
    if not (json_flag or quiet):
        if gap > RESUME_GAP:
            print_reentry(
                book,
                "── mindseam ─ seam (long gap: %d minutes since the last one)" % (gap // 60),
            )
        else:
            print("── mindseam ─ seam")
            print_ledger(book)
    meta = read_meta() or {}
    rows_written = 0
    compact_reasons = []
    if not dry_run:
        nexts_to_record = extra_nexts if extra_nexts else [None]
        for next_value in nexts_to_record:
            if next_value is not None:
                book["Next"] = [next_value]
            hist, compact_reasons = append_history(book, meta=meta)
            if message and hist:
                hist[-1]["msg"] = message
                problem = atomic_write_text(
                    HISTORY, json.dumps(hist, ensure_ascii=False))
                if problem:
                    print("WARNING: could not write seam message — "
                          + problem, file=sys.stderr)
            rows_written += 1
    for key in METACOGNITION_EVENT_KEYS:
        meta.pop(key, None)
    state_reasons = repair_reasons + compact_reasons
    found = observations(hist, meta=meta, book=book)
    risk_level, risk_reasons = assess_risk(hist)
    if risk_level != "low" or risk_reasons:
        meta["risk"] = {"level": risk_level, "reasons": risk_reasons}
    else:
        meta.pop("risk", None)
    trend = meta.setdefault("trend", {})
    risks = trend.setdefault("risk", [])
    risks.append(risk_level)
    if len(risks) > STALL_RUN:
        del risks[:-STALL_RUN]
    health_score, health_reasons = session_health_score(hist, book=book)
    write_meta(meta)
    write_skillbook(extract_skillbook(hist))
    if json_flag:
        payload = _seam_json_payload(book, hist, found, gap)
        payload["state_repairs"] = list(state_reasons)
        payload["telemetry"] = {
            k: (meta[k] if isinstance(meta.get(k), str) else
                meta[k].get("level") if k == "risk" and isinstance(meta.get(k), dict)
                else None)
            for k in ("marker", "confidence", "verifier", "risk")
        }
        payload["trend"]["score"] = {
            "value": health_score,
            "grade": grade(health_score),
            "factors": list(health_reasons or []),
        }
        payload["remediation"] = remediation_suggestions(found, health_score, book=book)
        actions = heal_actions(hist, book=book) if len(hist) >= STALL_RUN else []
        payload["heal"] = list(actions[:HEAL_REPORT_MAX])
        if dry_run:
            payload.setdefault("warnings", []).append(
                "dry-run: history.json was not updated")
        if message and not dry_run and hist:
            payload.setdefault("warnings", []).append("message: %s" % message)
        if extra_nexts:
            payload.setdefault("warnings", []).append(
                "from-stdin: %d next actions recorded" % len(extra_nexts))
        elif from_stdin:
            payload.setdefault("warnings", []).append(
                "from-stdin: 0 next actions recorded")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if quiet:
        for f in found:
            print(f)
        return 0
    if state_reasons:
        print()
        print("State repair:")
        for reason in state_reasons:
            print("· " + reason)
    if found:
        print()
        for f in found:
            print("· " + f)
        print()
        print("You would not have noticed that; I keep the record, so here it is.")
        print("If that is depth, carry on. If it is a stall, the moves open to you are:")
        print("  " + SHIFTS)
    meta_parts = []
    if meta.get("marker"):
        meta_parts.append("marker: %s" % meta["marker"])
    if meta.get("confidence"):
        meta_parts.append("confidence: %s" % meta["confidence"])
    if meta.get("verifier"):
        meta_parts.append("verifier: %s" % meta["verifier"])
    if meta.get("risk"):
        risk = meta["risk"]
        meta_parts.append("risk: %s" % risk.get("level", "low").upper())
        if risk.get("reasons"):
            meta_parts.append("risk reasons: %s" % ", ".join(risk["reasons"]))
    if meta_parts:
        print()
        print("Telemetry: " + "; ".join(meta_parts))
    trend_parts = []
    if meta.get("trend"):
        confidence_trend = meta["trend"].get("confidence", [])
        if len(confidence_trend) >= 3:
            trend_parts.append("confidence trend: %s" % " -> ".join(confidence_trend[-3:]))
        marker_trend = meta["trend"].get("marker", [])
        if len(marker_trend) >= 3:
            trend_parts.append("marker trend: %s" % " -> ".join(marker_trend[-3:]))
    if hist:
        risk_trend_parts = [h["risk"] for h in hist[-3:] if h.get("risk")]
        if len(risk_trend_parts) >= 2:
            trend_parts.append("risk trend: %s" % " -> ".join(risk_trend_parts))
    trend_parts.append("score: %d/100 (%s)" % (health_score, grade(health_score)))
    if health_reasons:
        trend_parts.append("score factors: %s" % ", ".join(health_reasons))
    if trend_parts:
        print()
        print("Trend: " + "; ".join(trend_parts))
    suggestions = remediation_suggestions(found, health_score, book=book)
    if suggestions:
        print()
        print("Remediation:")
        for suggestion in suggestions:
            print("  - " + suggestion)
    actions = heal_actions(hist, book=book) if len(hist) >= STALL_RUN else []
    if actions:
        print()
        print("Heal (%d detector%s below threshold):" % (len(actions), "" if len(actions) == 1 else "s"))
        for action in actions[:HEAL_REPORT_MAX]:
            print("  - " + action)
        if len(actions) > HEAL_REPORT_MAX:
            print("  - ... %d more; the ones above are the cheapest to act on."
                  % (len(actions) - HEAL_REPORT_MAX))
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


def mode_resume(book, json_flag=False):
    """Re-anchor after a gap: premise, invariants, full ledger.

    ``--json`` borrows the ``gh --json`` family the way the other
    subcommands do: the machine face mirrors the text report's data —
    ledger digest, persisted risk, health score with its grade and
    factors, the risk trend and the state repairs — without the
    premise prose, which a host cannot consume anyway. The side
    effect is unchanged: a resume still appends one history row under
    either face, the way ``seam --json`` does.
    """
    hist, _, repair_reasons = read_history()
    if not json_flag:
        print_reentry(book, "── mindseam ─ resume")
    hist, compact_reasons = append_history(book)
    state_reasons = repair_reasons + compact_reasons
    meta = read_meta() or {}
    risk = meta.get("risk")
    score, score_reasons = session_health_score(hist, book=book)
    score_grade = grade(score)
    trend_parts = []
    if hist:
        recent_risks = [h["risk"] for h in hist[-3:] if h.get("risk")]
        if len(recent_risks) >= 2:
            trend_parts.append("risk trend: %s" % " -> ".join(recent_risks))
    if score < 100 or score_reasons:
        trend_parts.append("score: %d/100 (%s)" % (score, score_grade))
        if score_reasons:
            trend_parts.append("score factors: %s" % ", ".join(score_reasons))
    if json_flag:
        payload = {
            "ledger": {
                "goal": one(book, "Goal") or None,
                "core": list(book.get("Core", [])),
                "verified_count": len(book.get("Verified", [])),
                "open": list(book.get("Open", [])),
                "next": one(book, "Next") or None,
            },
            "history_count": len(hist),
            "state_repairs": list(state_reasons),
            "risk": {
                "level": (risk.get("level", "low")
                          if isinstance(risk, dict) else "low"),
                "reasons": list(risk.get("reasons", [])
                                if isinstance(risk, dict) else []),
            },
            "trend": {
                "risk": [h["risk"] for h in hist[-3:] if h.get("risk")],
                "score": {
                    "value": score,
                    "grade": score_grade,
                    "factors": list(score_reasons or []),
                },
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if state_reasons:
        print()
        print("State repair:")
        for reason in state_reasons:
            print("· " + reason)
    if risk:
        print()
        print("Persisted risk: %s" % risk.get("level", "low").upper())
        for reason in risk.get("reasons", []):
            print("· " + reason)
    if trend_parts:
        print()
        print("Trend: " + "; ".join(trend_parts))
    return 0


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

    meta = read_meta()
    if getattr(args, "marker", None):
        # Detectors compare markers by exact equality ("PHEW", "OPEN"):
        # an untrimmed marker silently missed every settle and phase
        # check, so it is normalised like --verifier/--error, not passed
        # through raw (round 55).
        marker = args.marker.strip()
        if not marker:
            refused.append(
                (
                    "marker must be at least one non-whitespace character.",
                    '--marker OPEN'
                )
            )
        else:
            meta["marker"] = marker
            trend = meta.setdefault("trend", {})
            markers = trend.setdefault("marker", [])
            markers.append(marker)
            if len(markers) > 5:
                del markers[:-5]
    if getattr(args, "confidence", None):
        if args.confidence not in ("strong", "thin", "shaky"):
            refused.append(
                (
                    "confidence must be strong, thin, or shaky.",
                    '--confidence strong|thin|shaky'
                )
            )
        else:
            meta["confidence"] = args.confidence
            trend = meta.setdefault("trend", {})
            confidences = trend.setdefault("confidence", [])
            confidences.append(args.confidence)
            if len(confidences) > 5:
                del confidences[:-5]
    if getattr(args, "verifier", None):
        verifier = args.verifier.strip()
        if len(verifier) < 5:
            refused.append(
                (
                    "verifier must be at least 5 non-whitespace characters.",
                    '--verifier "command exit 0" or "n ≤ 6, empty and maximum"',
                )
            )
        else:
            meta["verifier"] = verifier
            trend = meta.setdefault("trend", {})
            verifiers = trend.setdefault("verifier", [])
            verifiers.append(verifier)
            if len(verifiers) > 5:
                del verifiers[:-5]
    if getattr(args, "error", None) is not None:
        value, problem = clean_scalar(args.error)
        if problem:
            refused.append(("--error %s." % problem, '--error "domain: what broke"'))
        else:
            meta["error"] = value
    if getattr(args, "outcome", None) is not None:
        value, problem = clean_scalar(args.outcome)
        if problem:
            refused.append(("--outcome %s." % problem, '--outcome "ok" or "failed: what blocked it"'))
        else:
            meta["outcome"] = value
    if getattr(args, "extra_steps", None) is not None:
        if args.extra_steps < 0:
            refused.append(
                ("--extra-steps cannot be negative.", "--extra-steps 0 or a positive count")
            )
        else:
            meta["extra_steps"] = args.extra_steps
    if meta:
        write_meta(meta)

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


def mode_ship(book, text, strict=False, json_flag=False):
    """Report inner-register leakage and completion-gate observations in outgoing text.

    A report, not a gate by default: it exits 0 whether or not it finds anything, because
    the caller asked it to look and it looked. With --strict, completion-gate failures
    become non-zero exits: the gate moves from observation to enforcement.
    ``--json`` borrows the ``gh --json`` family: the findings, the gate
    observations and the risk assessment ride one payload whose exit
    contract is byte-identical to the text face — a host gating on the
    process exit code gets the same answer either way.
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
        if index not in structural and REPETITION_CHAR_RUN.search(line):
            findings.append("repetition loop: a character run of 20 or more")
            break

    gate = []
    hist = read_history()[0]
    found_conf = False
    found_marker = False
    for row in reversed(hist):
        if not found_conf:
            confidence = row.get("confidence")
            if confidence:
                found_conf = True
                if confidence == "shaky":
                    gate.append("shaky confidence was not settled before delivery")
        if not found_marker:
            marker = row.get("marker")
            if marker:
                found_marker = True
                if marker != "PHEW":
                    gate.append("marker '%s' was not followed by a settle" % marker)
        if found_conf and found_marker:
            break

    if book.get("Open"):
        gate.append("%d open question(s) remain" % len(book["Open"]))

    risk_level, risk_reasons = assess_risk(hist)
    escalation = detect_risk_escalation(hist)
    recovery = detect_recovery(hist)

    if json_flag:
        payload = {
            "clean": not (findings or gate or risk_reasons
                          or escalation or recovery),
            "findings": list(findings),
            "gate": list(gate),
            "risk": {
                "level": risk_level,
                "reasons": list(risk_reasons),
                "escalation": list(escalation),
                "recovery": list(recovery),
            },
            "strict": bool(strict),
            "exit": 2 if (strict and gate) else 0,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload["exit"]
    if not findings and not gate and not risk_reasons and not escalation and not recovery:
        print("clean — the outgoing register holds.")
        return 0
    print("── mindseam ─ ship")
    for f in findings[:7]:
        print("· " + f)
    if gate:
        print()
        print("Completion-gate observations:")
        for g in gate:
            print("· " + g)
    if risk_level != "low" or risk_reasons or escalation or recovery:
        print()
        print("Risk assessment: %s" % risk_level.upper())
        for r in risk_reasons:
            print("· " + r)
        for e in escalation:
            print("· " + e)
        for r in recovery:
            print("· " + r)
    print()
    print("Expand the whole span into clean language before it ships. The switch is total, never cosmetic.")
    if strict and gate:
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


def _history_when(ts, human=False, now=None):
    """Render a row timestamp for the text table.

    The default face is the absolute local time the other audit tools
    print. ``--human`` borrows ``git log``'s relative dates /
    ``ls -lh``: the span since the row landed, for a reader who wants
    "how stale is this" without doing clock arithmetic. JSON, CSV,
    ``--fields`` and ``--format`` keep the raw epoch either way, the
    way ``info --human`` keeps raw seconds in its JSON payload.
    """
    if not ts:
        return "(no timestamp)"
    if human:
        age = int((now if now is not None else time.time()) - int(ts))
        if age < 0:
            return "in the future"
        return _humanize_seconds(age) + " ago"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


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
    if keep_n is not None and keep_n >= 0 and len(read_history()[0]) > keep_n:
        # Persist the truncated history to disk first, then work
        # from the in-memory slice so the rest of the filters
        # see the slimmed window without re-reading.
        keep_n = int(keep_n)
        full = read_history()[0]
        truncated = full[-keep_n:] if keep_n > 0 else []
        problem = atomic_write_text(
            HISTORY, json.dumps(truncated, ensure_ascii=False))
        if problem:
            print("WARNING: could not rotate history.json — "
                  + problem, file=sys.stderr)
        hist = truncated
    hist = read_history()[0]
    # Borrowed from ``docker ps --filter name=value`` /
    # ``kubectl get --field-selector status=Running``: keep only the
    # rows whose field equals the given value, one ``key=value`` pair
    # per ``--filter`` flag, all pairs ANDed the way docker ANDs its
    # filters. The value compares against the row's string form with
    # both sides stripped, so ``--filter marker=OPEN`` and
    # ``--filter confidence=shaky`` read the way a host expects.
    # An unknown key or a malformed pair is declined, the way docker
    # refuses a filter it cannot parse — silence would hand back a
    # result set the caller believes covers more than it does.
    # Every render flag downstream honours the narrowed set, so
    # ``--filter confidence=shaky --count`` and
    # ``--filter marker=OPEN --json`` compose like any other filter.
    raw_filters = getattr(args, "filter", None) or []
    field_filters = []
    for pair in raw_filters:
        if "=" not in pair:
            print("CANNOT: --filter expects key=value, got %r" % pair,
                  file=sys.stderr)
            print("  e.g. --filter marker=OPEN", file=sys.stderr)
            return 2
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if not key or key not in HISTORY_ROW_FIELDS:
            print("CANNOT: --filter key %r is not a history field." % key,
                  file=sys.stderr)
            print("  fields: %s" % ", ".join(HISTORY_ROW_FIELDS),
                  file=sys.stderr)
            return 2
        field_filters.append((key, value))
    for key, value in field_filters:
        hist = [row for row in hist
                if str(row.get(key, "") if row.get(key) is not None else "").strip()
                == value]
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
            print("── mindseam ─ history (no rows)")
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
        print("── mindseam ─ history (row %d of %d)" % (n, len(hist)))
        ts = row.get("t")
        when = _history_when(ts, human=bool(getattr(args, "human", False)))
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
                print("── mindseam ─ history (no rows with a next action)")
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
        print("── mindseam ─ history (%d domains across %d seams)" % (len(counts), total))
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
            print("── mindseam ─ history span (no rows)")
            return 0
        first_t = int(hist[0].get("t") or 0)
        last_t = int(hist[-1].get("t") or 0)
        duration = max(0, last_t - first_t)
        first_when = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(first_t)) if first_t else "(none)"
        last_when = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(last_t)) if last_t else "(none)"
        print("── mindseam ─ history span")
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
            print("── mindseam ─ history (%d unique msg annotations across %d rows)"
                  % (len(deduped), len(hist)))
            for index, row in enumerate(deduped, 1):
                msg = row.get("msg") or "(empty)"
                print("  %3d  %s" % (index, msg))
        else:
            print("── mindseam ─ history (%d unique next actions across %d rows)"
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
            print("── mindseam ─ history (no empty-next rows)")
            return 0
        print("── mindseam ─ history (%d empty-next rows)" % len(hist))
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
        # ``count=$(mindseam history --since 3600 --grep TODO --count)``
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
            print("── mindseam ─ history (no rows)")
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
        print("── mindseam ─ history (row %d of %d)" % (n, len(hist)))
        ts = row.get("t")
        when = _history_when(ts, human=bool(getattr(args, "human", False)))
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
    label = "── mindseam ─ history (%d entries" % len(hist)
    if since_seconds is not None and since_seconds >= 0:
        label += ", last %d s" % since_seconds
    if grep_text:
        label += ", grep %r" % grep_text
    if getattr(args, "reverse", False):
        label += ", newest first"
    print(label + ")")
    human = bool(getattr(args, "human", False))
    now = time.time()
    for index, row in enumerate(hist, 1):
        ts = row.get("t")
        when = _history_when(ts, human=human, now=now)
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
    hist = read_history()[0]
    meta = read_meta() or {}
    goal = one(book, "Goal")
    nxt = one(book, "Next")
    last_seam_t = hist[-1]["t"] if hist else None
    now = int(time.time())
    gap_seconds = (now - last_seam_t) if last_seam_t is not None else None
    payload = {
        "ledger": {
            "goal": goal or None,
            "Goal": list(book.get("Goal", [])),
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
        "skillbook_entries": len(read_skillbook()),
        "risk": ((meta.get("risk") or {}).get("level", "unknown")
                 if isinstance(meta.get("risk"), dict) else "unknown"),
        "meta_keys": sorted(str(k) for k in meta),
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
        print("mindseam " + __version__)
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
        # same code ``mindseam ship --strict`` uses to turn a
        # report into a gate.
        issues = _info_check_issues(book, hist, gap_seconds)
        if json_flag:
            print(json.dumps({
                "valid": not issues,
                "issues": issues,
            }, indent=2, ensure_ascii=False))
            return 0 if not issues else 2
        if not issues:
            print("── mindseam ─ info check")
            print("  ledger: ok")
            return 0
        print("── mindseam ─ info check")
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
            for dirpath, _, filenames in os.walk(workspace_path):
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
        print("── mindseam ─ info memory")
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
            print("── mindseam ─ info %s" % section)
            for name, doc in fields.items():
                print("  %-22s  %s" % (name, doc))
        return 0
    if json_flag:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("── mindseam ─ info")
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


SKILLBOOK_MIN_RECURRENCE = 2
SKILLBOOK_MAX_ENTRIES = 20
SKILLBOOK = os.path.join(LEDGER_DIR, "skillbook.md")


def extract_skillbook(hist):
    """Mine recurring patterns from the seam history (ACE-style).

    Two pattern kinds surface: ``error`` — the same ``"domain: what
    broke"`` text recurring at least SKILLBOOK_MIN_RECURRENCE times —
    and ``hard`` — the same domain prefix in the next action paired
    with unplanned extra steps. Utility sums outcome signals: ``ok``
    +1, ``failed`` -1, absent 0; negative-utility patterns never ship.
    """
    counts = {}
    for h in hist:
        err = (h.get("error") or "").strip()
        if err:
            entry = counts.setdefault(
                ("error", err), {"count": 0, "utility": 0})
            entry["count"] += 1
            outcome = (h.get("outcome") or "").strip().lower()
            if outcome.startswith("ok"):
                entry["utility"] += 1
            elif outcome:
                entry["utility"] -= 1
        nxt = (h.get("next") or "").strip()
        domain = nxt.split(":", 1)[0].strip() if ":" in nxt else ""
        if domain and (h.get("extra_steps") or 0) > 0:
            entry = counts.setdefault(
                ("hard", domain), {"count": 0, "utility": 0})
            entry["count"] += 1
            outcome = (h.get("outcome") or "").strip().lower()
            if outcome.startswith("ok"):
                entry["utility"] += 1
            elif outcome:
                entry["utility"] -= 1
    entries = [
        {"kind": kind, "text": text, "count": v["count"],
         "utility": v["utility"]}
        for (kind, text), v in counts.items()
        if v["count"] >= SKILLBOOK_MIN_RECURRENCE and v["utility"] >= 0
    ]
    entries.sort(key=lambda e: (-e["count"], e["kind"], e["text"]))
    return entries[:SKILLBOOK_MAX_ENTRIES]


def read_skillbook():
    """Load the persisted skillbook entries, tolerating any damage."""
    if not os.path.exists(SKILLBOOK):
        return []
    try:
        with open(SKILLBOOK, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return []
    return data if isinstance(data, list) else []


def write_skillbook(entries):
    """Persist the skillbook entries; the file always exists after."""
    problem = ensure_dir()
    if problem:
        print("WARNING: skillbook was not saved — " + problem, file=sys.stderr)
        return
    atomic_write_text(SKILLBOOK, json.dumps(entries, ensure_ascii=False, indent=2))


def mode_skillbook(json_flag=False):
    """Print the recurring-pattern skillbook.

    The seam command refreshes ``.mindseam/skillbook.md`` as a side
    effect; this subcommand prints the same entries on demand, in
    plain text or JSON.
    """
    entries = extract_skillbook(read_history()[0])
    write_skillbook(entries)
    if json_flag:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0
    if not read_history()[0]:
        print("No skillbook yet — run a seam to start harvesting patterns.")
        return 0
    if not entries:
        print("No high-utility patterns yet — the skillbook fills as seams repeat.")
        return 0
    print("── mindseam ─ skillbook")
    for e in entries:
        print("  [%s] %s (x%d, utility %+d)"
              % (e["kind"], e["text"], e["count"], e["utility"]))
    return 0


def mode_discover(json_flag=False):
    """Rank the domains the session visited and suggest the next pass.

    A read-only reflection over history.json: count the domain prefix
    of every recorded next action, rank by visits, and surface the
    most-visited domain as the suggested next pass when one exists.
    """
    hist = read_history()[0]
    visits = {}
    for h in hist:
        nxt = (h.get("next") or "").strip()
        if not nxt or ":" not in nxt:
            continue
        domain = nxt.split(":", 1)[0].strip()
        if domain:
            visits[domain] = visits.get(domain, 0) + 1
    ranked = [
        {"name": name, "visits": count}
        for name, count in sorted(visits.items(),
                                  key=lambda kv: (-kv[1], kv[0]))
    ]
    if json_flag:
        payload = {"domains": ranked}
        if ranked:
            payload["suggested_next"] = ranked[0]["name"]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not ranked:
        print("No history yet — run a seam and the domain map appears.")
        return 0
    print("── mindseam ─ discover")
    for d in ranked:
        print("  %-24s %d visit%s" % (d["name"], d["visits"],
                                      "" if d["visits"] == 1 else "s"))
    print()
    print("Suggested next pass: %s — the domain the session kept returning to."
          % ranked[0]["name"])
    return 0


# Borrowed from DietrichGebert/ponytail (MIT): the read-only audit that
# emits tagged one-line findings ranked biggest first and closes with
# "Lean already. Ship." when there is nothing to cut. Ponytail audits
# code for over-engineering; the seam audit applies the same shape to
# the ledger — the artefact this controller actually keeps. Report
# only: audit never writes, and findings never gate unless --strict.
# Borrowed from DietrichGebert/ponytail (MIT): the read-only audit that
# emits tagged one-line findings ranked biggest first and closes with
# "Lean already. Ship." when there is nothing to cut. Ponytail audits
# code for over-engineering; the seam audit applies the same shape to
# the ledger — the artefact this controller actually keeps. Report
# only: audit never writes, and findings never gate unless --strict.
#
# Tag taxonomy: the four original tags (delete / stdlib / yagni / shrink)
# audit the ledger surface itself; the three "facet" tags (goal-stale /
# next-stall / core-drift) audit the ledger against history, the way a
# ponytail audit considers how the code evolved, not only what the code
# looks like in this commit.
AUDIT_TAGS = (
    "delete", "stdlib", "yagni", "shrink",
    "goal-stale", "next-stall", "core-drift",
)

INTENSITY_LEVELS = ("off", "lite", "full")
INTENSITY_ENV = "MINDSEAM_INTENSITY"


def resolve_intensity(explicit=None):
    """Resolve the verbosity ladder: flag > MINDSEAM_INTENSITY > full.

    Borrowed from ponytail's mode resolution (``PONYTAIL_DEFAULT_MODE``,
    then config, then ``full``) minus the config file — a controller
    with two env-read commands does not earn one. An unset or blank
    variable reads as the default; validation of the resolved value is
    the caller's job, because the refusal message names the flag that
    reached it.
    """
    if explicit is not None and explicit.strip():
        return explicit.strip().lower()
    env = os.environ.get(INTENSITY_ENV, "")
    if env.strip():
        return env.strip().lower()
    return "full"


_AUDIT_NUMBERED = re.compile(r"^[?✓]\d+\s+")


def _audit_norm(text):
    """Collapse a ledger row to its comparable form for duplicate checks.

    The controller prefixes Open rows with ``?NN`` and Verified rows
    with ``✓NN``; those ids are allocation artifacts, so the
    duplicate check strips them before comparing the content the
    reader actually sees.
    """
    return _AUDIT_NUMBERED.sub(
        "", " ".join((text or "").split())).casefold()


def audit_findings(book, hist):
    """Tagged findings over the ledger, ranked biggest cut first.

    Tags, adapted from ponytail's five code tags to the ledger:

    - ``delete`` — an Open entry duplicating another Open entry or an
      already-Verified line (settled work still posing as a question).
    - ``stdlib`` — a Verified entry recorded twice; one canonical
      checkpoint would do, the way one stdlib call replaces a
      hand-rolled copy.
    - ``yagni`` — Core entries parked beyond the two live slots the
      ledger surface actually reads.
    - ``shrink`` — history rows whose next action is blank; they are
      noise in the audit log and rotate out with ``history --keep``.

    Within a tag, findings keep ledger order (Core, Verified, Open),
    and the tag order above is the severity order.
    """
    findings = []

    def first_seen(section, entries):
        seen = {}
        for index, row in enumerate(entries):
            key = _audit_norm(row)
            if key:
                seen.setdefault(key, "%s #%d" % (section, index + 1))
        return seen

    open_seen = first_seen("Open", book.get("Open", []))
    verified_seen = first_seen("Verified", book.get("Verified", []))

    def emit(tag, what, replacement):
        findings.append({"tag": tag, "what": what,
                         "replacement": replacement})

    for index, row in enumerate(book.get("Open", [])):
        key = _audit_norm(row)
        if not key:
            continue
        if open_seen.get(key) != "Open #%d" % (index + 1):
            emit("delete",
                 "Open #%d repeats %s" % (index + 1, open_seen[key]),
                 "one row per question; close the duplicate")
        elif key in verified_seen:
            emit("delete",
                 "Open #%d is already answered by %s"
                 % (index + 1, verified_seen[key]),
                 "the question is settled; it can leave Open")

    for index, row in enumerate(book.get("Verified", [])):
        key = _audit_norm(row)
        if key and verified_seen.get(key) != "Verified #%d" % (index + 1):
            emit("stdlib",
                 "Verified #%d repeats %s" % (index + 1, verified_seen[key]),
                 "keep one canonical checkpoint")

    parked = len(book.get("Core", [])) - 2
    if parked > 0:
        emit("yagni",
             "Core carries %d parked item%s beyond the two live slots"
             % (parked, "" if parked == 1 else "s"),
             "verify or demote them; the surface reads two at a time")

    blank_next = sum(1 for h in hist if not (h.get("next") or "").strip())
    if blank_next:
        emit("shrink",
             "%d history row%s carry a blank next action"
             % (blank_next, "" if blank_next == 1 else "s"),
             "rotate them out with `history --keep`")

    # Borrowed from `gh audit-log` / `journalctl --list-boots` /
    # ponytail's "drift" check: a Goal field that has not been
    # re-confirmed in the most recent seams is parked; the user
    # moved on, the ledger did not. The detector looks at the last
    # 10 history rows: if every one of them carried no `goal`
    # annotation (i.e. the agent did not re-anchor to Goal) and
    # the ledger Goal is non-empty, the goal is stale. The
    # threshold is 10 so a short conversation does not trip the
    # finding; the finding is also emitted as a soft signal —
    # `goal-stale` is a noun, not a verdict — and the replacement
    # points the host at `note --goal` to re-anchor.
    goal_text = (book.get("Goal") or [""])[0].strip() if book.get("Goal") else ""
    if goal_text and len(hist) >= 10:
        recent = hist[-10:]
        stale = [h for h in recent
                 if not (h.get("goal") or "").strip()
                 and (h.get("next") or "").strip()]
        if len(stale) == len(recent):
            emit("goal-stale",
                 "Goal has not been re-anchored in the last %d seams"
                 % len(stale),
                 "re-run `note --goal ...` to confirm the commitment, or `note --next` to record a new one")

    # Borrowed from ponytail's "drift" pattern and
    # `tshark -qz io,phs` (long-tail detection): the same `next`
    # appearing repeatedly in the recent history without becoming
    # Verified is the agent spinning on a topic it cannot resolve.
    # The window is the last 5 history rows, and the bar is the
    # same `next` showing up in 3 of them. The bar is a *fraction*
    # of the window, not an absolute number, so a session that
    # has only 2 seams cannot trip it; the replacement points the
    # host at `note --close` (when the topic actually finished)
    # or `note --next` (when the topic should change).
    if len(hist) >= 5:
        recent = hist[-5:]
        counts = {}
        for h in recent:
            nxt = (h.get("next") or "").strip()
            if nxt:
                counts[nxt] = counts.get(nxt, 0) + 1
        repeats = [(n, c) for n, c in counts.items() if c >= 3]
        repeats.sort(key=lambda nc: (-nc[1], nc[0]))
        for nxt, c in repeats:
            emit("next-stall",
                 "`%s` appears in %d of the last %d seams without resolution"
                 % (nxt, c, len(recent)),
                 "either close the topic with `note --close N` or change it with `note --next`")

    # Borrowed from `git log --check` / `cargo check` (live vs.
    # declared consistency): if the most recent `next` action
    # is also pinned in the Core section, the Core entry has
    # drifted (the agent committed to it but the live work moved
    # on). Conversely, an empty live `next` while Core still
    # carries a topic means the Core commitment outlasted the
    # session. Both directions are recorded as `core-drift` so
    # a host reading the audit can see the gap either way.
    # The finding only fires when Core actually has a commitment
    # to drift from — an empty Core is a fresh session, not a
    # drift, the way `cargo check` does not complain about a
    # fresh ``Cargo.toml`` with no deps.
    live_next = ""
    if book.get("Next"):
        # The `Next` field can hold multiple lines (one for
        # each recorded action); the "live" next is the last
        # non-empty one, the way the seam renders the rightmost
        # column.
        for n in reversed(book["Next"]):
            if n.strip():
                live_next = n.strip()
                break
    core_items = [c.strip() for c in book.get("Core", []) if c.strip()]
    if core_items:
        if live_next and live_next not in core_items:
            emit("core-drift",
                 "Next is `%s` but it is not in the Core"
                 % live_next,
                 "either move it to Core with `note --core` or change Next with `note --next`")
        if not live_next:
            emit("core-drift",
                 "Next is empty while Core still lists %d item%s"
                 % (len(core_items), "" if len(core_items) == 1 else "s"),
                 "re-anchor Next with `note --next ...` or retire the Core commitment")

    order = {tag: rank for rank, tag in enumerate(AUDIT_TAGS)}
    findings.sort(key=lambda f: (order[f["tag"]], f["what"]))
    return findings


def mode_audit(book, json_flag=False, strict=False, intensity=None, tags=None):
    """Audit the ledger for waste, one tagged line per finding.

    Borrowed from ponytail's ``/ponytail-audit`` contract: scan the
    whole artefact, not a diff; one line per finding in the form
    ``<tag> <what to cut>. <replacement>.`` ranked biggest first; end
    with the net count. If there is nothing to cut, say so in ponytail's
    own words. Report only — audit writes nothing and exits 0 whether
    or not findings exist; ``--strict`` turns findings into a non-zero
    exit for CI pipelines that want the gate.

    ``--intensity`` borrows ponytail's ladder (``PONYTAIL_DEFAULT_MODE``
    pattern): the flag wins over the ``MINDSEAM_INTENSITY`` environment
    variable, the environment wins over the ``full`` default. ``lite``
    caps the printed report at the three most severe findings and says
    how many were held back; ``full`` prints everything; ``off`` is the
    ponytail-off refusal — audit does not run. The JSON face always
    carries the complete finding list, the way a host that asked for
    JSON asked for the data, not the dial.

    ``--tag`` borrows from ``gh pr list --label <name>`` /
    ``cargo bench --bench <name>``: a comma-separated list of tags
    narrows the report to just those tags. The full finding set is
    still computed, but only the chosen tags are printed and only
    the chosen tags are reflected in the JSON ``findings`` array;
    the ``by_tag`` map in JSON carries the count per tag so a host
    can tell which tags fired. An unknown tag is refused with exit
    2 to stderr, the way ``gh --label unknown`` refuses an
    unrecognised label.
    """
    level = resolve_intensity(intensity)
    if level == "off":
        print("CANNOT: audit intensity is off.")
        print("  set --intensity lite|full (or MINDSEAM_INTENSITY) to run the audit")
        return 2
    if tags:
        chosen = [t.strip() for t in tags.split(",") if t.strip()]
        unknown = [t for t in chosen if t not in AUDIT_TAGS]
        if unknown:
            print("CANNOT: --tag %s is not a recognised audit tag."
                  % (", ".join(unknown)),
                  file=sys.stderr)
            print("  known tags: %s" % ", ".join(AUDIT_TAGS),
                  file=sys.stderr)
            return 2
    else:
        chosen = []
    hist, _, _ = read_history()
    findings = audit_findings(book, hist)
    if chosen:
        findings = [f for f in findings if f["tag"] in chosen]
    by_tag = {}
    for f in findings:
        by_tag[f["tag"]] = by_tag.get(f["tag"], 0) + 1
    if json_flag:
        payload = {
            "lean": not findings,
            "net": len(findings),
            "intensity": level,
            "tags": chosen or list(AUDIT_TAGS),
            "by_tag": by_tag,
            "findings": findings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not strict else (0 if not findings else 1)
    if not findings:
        if chosen:
            print("Lean on %s. Ship." % ", ".join(chosen))
        else:
            print("Lean already. Ship.")
        return 0
    shown = findings[:3] if level == "lite" else findings
    for f in shown:
        print("%s %s. %s." % (f["tag"], f["what"], f["replacement"]))
    if len(shown) < len(findings):
        print("+%d more finding%s — rerun with --intensity full to see them."
              % (len(findings) - len(shown),
                 "" if len(findings) - len(shown) == 1 else "s"))
    print("Net: %d item%s removable."
          % (len(findings), "" if len(findings) == 1 else "s"))
    return 0 if not strict else (0 if not findings else 1)



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
    rs = sub.add_parser("resume", help="premise, invariants and full ledger, after a gap")
    rs.add_argument("--json", action="store_true",
                    help="emit machine-readable output for the discoverability layer")

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
    n.add_argument("--marker")
    n.add_argument("--confidence")
    n.add_argument("--verifier")
    n.add_argument("--error", help="what failed on this step, as 'domain: what broke'")
    n.add_argument("--outcome", help="how the step actually landed (ok, failed, blocked, ...)")
    n.add_argument("--extra-steps", dest="extra_steps", type=int,
                   help="how many unplanned sub-steps this step cost")

    s = sub.add_parser("ship", help="register check on anything about to leave")
    s.add_argument("file", help="path, or - for stdin")
    s.add_argument("--strict", action="store_true",
                   help="exit non-zero when a finding is reported (CI gate)")
    s.add_argument("--json", action="store_true",
                   help="emit machine-readable output for the discoverability layer")

    info_p = sub.add_parser("info", help="print an aggregate digest of the workspace state")
    info_p.add_argument("--json", action="store_true",
        help="emit machine-readable output for the discoverability layer")
    info_p.add_argument("--warnings-only", dest="warnings_only", action="store_true",
        help="print only the warning lines (like gh run list --state failed)")
    info_p.add_argument("--version", dest="version_only", action="store_true",
        help="print the controller version on its own (like gh --version / kubectl version)")
    info_p.add_argument("--human", dest="human", action="store_true",
        help="render time spans in human-readable units (like df -h / git log --relative-date)")
    info_p.add_argument("--check", dest="check_only", action="store_true",
        help="report ledger health issues without repairing (like git fsck, exit 2 on issues)")
    info_p.add_argument("--memory", dest="memory_only", action="store_true",
        help="report workspace disk size in human units (like free -m / du -h / docker system df)")
    info_p.add_argument("--list-fields", dest="list_fields", action="store_true",
        help="describe the ledger schema (like kubectl explain / man page)")

    hist_p = sub.add_parser("history", help="tail the seam audit log")
    hist_p.add_argument("-n", "--limit", dest="limit", type=int, default=None,
        help="print only the most recent N entries (alias of --tail, like git log -n)")
    hist_p.add_argument("--tail", dest="tail", type=int, default=None,
        help="print only the most recent N entries (like tail -n N)")
    hist_p.add_argument("--head", dest="head", type=int, default=None,
        help="print only the first N entries (like head -n N)")
    hist_p.add_argument("--json", action="store_true",
        help="emit machine-readable output for the discoverability layer")
    hist_p.add_argument("--reverse", action="store_true",
        help="show oldest first (like git log --reverse), default is newest first")
    hist_p.add_argument("--since", dest="since", type=int, default=None,
        help="keep only rows from the last N seconds (like docker logs --since 30m)")
    hist_p.add_argument("--grep", dest="grep", default=None,
        help="keep only rows whose next action contains TEXT (like git log --grep)")
    hist_p.add_argument("--exclude", dest="exclude", default=None,
        help="drop rows whose next action or msg contains TEXT (like git log --invert-grep)")
    hist_p.add_argument("--until", dest="until", type=int, default=None,
        help="drop rows newer than N seconds ago (like git log --until, the upper bound on --since)")
    hist_p.add_argument("--keep", dest="keep", type=int, default=None,
        help="discard rows older than the last N and persist the slimmed history (like logrotate --keep, docker system prune)")
    hist_p.add_argument("--dedup", dest="dedup", action="store_true",
        help="collapse the surviving rows to unique next actions (like sort -u / uniq)")
    hist_p.add_argument("--dedup-by-msg", dest="dedup_by_msg", action="store_true",
        help="collapse the surviving rows to unique msg annotations (like sort -u -k 2)")
    hist_p.add_argument("--row-id", dest="row_id", default=None,
        help="return the single row at the 1-based index N (like git log --skip N -n 1 / sed -n 'Np')")
    hist_p.add_argument("--empty", dest="empty", action="store_true",
        help="keep only the rows whose next action is blank (like find -empty / awk '/^$/')")
    hist_p.add_argument("--quiet", dest="quiet", action="store_true",
        help="print only the next action of each row, one per line (like git log --oneline)")
    hist_p.add_argument("-c", "--count", dest="count", action="store_true",
        help="print only the row count (like wc -l, like git rev-list --count)")
    hist_p.add_argument("--first-match", dest="first_match", action="store_true",
        help="stop after the first matching row (like grep -m 1 / ripgrep --max-count=1)")
    hist_p.add_argument("--fields", dest="fields", default=None,
        help="comma-separated list of history fields to print (like docker ps --format)")
    hist_p.add_argument("--format", dest="format", default=None,
        help=("per-row template where placeholders are replaced with "
              "the row fields. Available placeholders: "
              "%%t (timestamp), %%n (next action), %%m (message), "
              "%%v (verified count), %%o (open count), "
              "%%h (row index, 1-based). "
              "Example: '%%t %%n' (like git log --format='%%h %%s')."))
    hist_p.add_argument("--csv", dest="csv", action="store_true",
        help="emit history as CSV (like aws --output csv, PowerShell ConvertTo-Csv)")
    hist_p.add_argument("--domains", dest="domains", action="store_true",
        help="group history by next-action domain prefix, the way JIT-Agent factors memory/planning/action/capability")
    hist_p.add_argument("--span", dest="span", action="store_true",
                   help="print the first-seam, last-seam and duration of the window (like git log --stat / journalctl --list-boots)")
    hist_p.add_argument("--filter", dest="filter", action="append", metavar="KEY=VALUE",
                   help="keep only rows whose field KEY equals VALUE; repeatable, all filters AND together (like docker ps --filter)")
    hist_p.add_argument("--human", dest="human", action="store_true",
                   help="render row timestamps as relative spans (like git log relative-date / ls -lh); JSON and CSV keep the raw epoch")

    sk = sub.add_parser("skillbook", help="recurring patterns harvested from the seam history")
    sk.add_argument("--json", action="store_true",
                    help="emit machine-readable output for the discoverability layer")
    dv = sub.add_parser("discover", help="rank the visited next-action domains")
    dv.add_argument("--json", action="store_true",
                    help="emit machine-readable output for the discoverability layer")
    au = sub.add_parser("audit", help="report ledger waste, one tagged line per finding (report only)")
    au.add_argument("--json", action="store_true",
                    help="emit machine-readable output for the discoverability layer")
    au.add_argument("--strict", action="store_true",
                    help="exit non-zero when a finding is reported (CI gate)")
    au.add_argument("--intensity", dest="intensity", default=None,
                    help="finding verbosity ladder: lite caps the report at 3 findings, full prints all (default), off refuses to run. Flag beats the MINDSEAM_INTENSITY environment variable (like PONYTAIL_DEFAULT_MODE)")
    au.add_argument("--tag", dest="tag", default=None,
                    help="comma-separated list of audit tags to include (delete,stdlib,yagni,shrink,goal-stale,next-stall,core-drift); unknown tags are refused. The full audit still runs; only the listed tags appear in the report (like gh pr list --label)")

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

    try:
        book = read_ledger()
    except LedgerReadError as exc:
        print("CANNOT: ledger was unreadable — %s." % exc)
        print("  repair or remove .mindseam/WORKSPACE.md before recording more state")
        return 2
    if args.cmd == "ship":
        return mode_ship(book, text, strict=getattr(args, "strict", False),
                         json_flag=getattr(args, "json", False))
    if args.cmd == "skillbook":
        return mode_skillbook(
            json_flag=getattr(args, "json", False))
    if args.cmd == "discover":
        return mode_discover(
            json_flag=getattr(args, "json", False))
    if args.cmd == "audit":
        return mode_audit(
            book,
            json_flag=getattr(args, "json", False),
            strict=getattr(args, "strict", False),
            intensity=getattr(args, "intensity", None),
            tags=getattr(args, "tag", None))
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
        return mode_resume(book, json_flag=getattr(args, "json", False))
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


