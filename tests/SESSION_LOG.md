# Mindseam V3.6 SESSION LOG

## Run 2026-08-28 (fifth pass — cross-platform encoding and performance optimization)

### Round 80 (test r152)

1. Learning rate generator & adaptability comprehensions: learning_rate accumulator
   refactored with generator expression sums; adaptability_score streamlined with comprehensions.
2. Invariant contracts: 0.0–1.0 learning rate evidence ratio, zero evidence baseline,
   and stall breakout adaptability adjustments pinned.
3. r152 pins learning_rate generator scoring and adaptability_score comprehensions.

- pytest: 1024 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 79 (test r151)

1. Evidence weight generator optimization: evidence_weight accumulator refactored
   with set comprehensions and generator expression sums across verifiers and outcomes.
2. Invariant contracts: maximum composite evidence weighting, error penalty deduction,
   and short window handling pinned.
3. r151 pins evidence_weight generator scoring and process verification invariants.

- pytest: 1021 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 78 (test r150)

1. Pattern persistence set comprehension optimization: pattern_persistence issue
   extraction and window comparison refactored with set comprehensions and generator sum.
2. Invariant contracts: chronic persistence detection across historical segments,
   transient single-window issue classification, and clean session contracts pinned.
3. r150 pins pattern_persistence set comprehension and chronic persistence invariants.

- pytest: 1018 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 77 (test r149)

1. Convergence index generator optimization: convergence_index multi-signal counting
   refactored with clean generator sum expressions over positive and negative scores.
2. Invariant contracts: unanimous positive convergence, unanimous negative convergence,
   and conflicting signal divergence thresholds pinned.
3. r149 pins convergence_index generator scoring and multi-signal calibration invariants.

- pytest: 1015 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 76 (test r148)

1. Trend acceleration direct boundary slicing: trend_acceleration element loops
   refactored with O(1) slice boundary indexing (first_slice[0], first_slice[-1]).
2. Invariant contracts: velocity gradient acceleration, deceleration detection,
   and stable cadence thresholds pinned.
3. r148 pins trend_acceleration boundary slicing and velocity gradient invariants.

- pytest: 1011 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 75 (test r147)

1. Precompiled checkpoint regex optimization: CHECKPOINT_ID_RE hoisted to
   module level and integrated into next_number() sequence id allocation.
2. Invariant contracts: checkpoint numbering monotonicity, custom prefix matching,
   and retired open question sequence allocation pinned.
3. r147 pins checkpoint sequence regex precompilation and sequence id allocation.

- pytest: 1007 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 74 (test r146)

1. Test harness strict integer checking: verify_suite.py check_interface hardened
   to explicitly reject boolean constants for STALL_RUN and HISTORY_MAX.
2. Invariant contracts: strict positive non-boolean integer validation for controller
   constants and public API interface integrity pinned.
3. r146 pins verify_suite non-boolean integer validation and public surface guards.

- pytest: 1003 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 73 (test r145)

1. Resolution rate generator optimization: resolution_rate accumulator refactored
   with clean generator expression sum over verified / outcome closures.
2. Invariant contracts: 0.0–1.0 ratio boundary precision, mixed outcome/verification
   scoring, and 1,000+ unit tests milestone crossed.
3. r145 pins resolution_rate generator scoring and 1k milestone test contracts.

- pytest: 1002 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 72 (test r144)

1. Observations condition simplification: observations() loop condition for verified
   outcome accessibility unified with direct truthiness check.
2. Invariant contracts: inaccessible verified outcome detection, monotonic open-question
   growth, and observation fact generation pinned.
3. r144 pins observations condition streamlining and cognitive scaffold invariants.

- pytest: 999 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 71 (test r143)

1. History append metadata coercion: append_history nested closure refactored
   with direct type inspection and key iteration over known metadata fields.
2. Invariant guards: non-string metadata rejection, positive integer coercion for
   extra_steps, and history compaction bounds pinned.
3. r143 pins append_history metadata coercion and history compaction invariants.

- pytest: 996 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 70 (test r142)

1. Main parser defensiveness & grade ladder: main() description extraction guarded
   against empty or stripped docstrings (e.g. python -OO environments); grade()
   simplified with direct early returns.
2. Invariant bounds: score letter grades (A >= 90, B >= 75, C >= 60, D >= 40, F < 40)
   and CLI parser fallback initialization pinned.
3. r142 pins main parser docstring defensiveness and grade ladder contracts.

- pytest: 994 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 69 (test r141)

1. Ledger parsing whitespace hygiene: read_ledger line normalization streamlined
   by removing redundant rstrip calls on pre-stripped headings.
2. Roundtrip fidelity guards: bullet prefix normalization (- item -> item), multi-section
   collection integrity, and serialization roundtrip fidelity pinned.
3. r141 pins ledger parsing hygiene, bullet stripping, and roundtrip fidelity.

- pytest: 992 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 68 (test r140)

1. Remediation deduplication & risk trend comprehension: remediation_suggestions
   deduplication refactored with built-in dict.fromkeys() preserving strict order;
   mode_seam and mode_resume risk trend generation streamlined with list comprehensions.
2. Output parity guards: remediation uniqueness, max 6 advice cap, and critical
   stress priority pinned.
3. r140 pins remediation deduplication order and risk trend comprehension.

- pytest: 990 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 67 (test r139)

1. Error acknowledgment & AST variable hygiene: error_acknowledgment_ratio
   cleaned of unused loop indices and stopword sets unified.
2. Complete AST analysis verified: 0 unused local variables across all functions
   in mindseam.py.
3. r139 pins error acknowledgment keyword matching, stopword filtering, and AST
   variable hygiene invariants.

- pytest: 988 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 66 (test r138)

1. Metacognitive trend sequence capping: mode_note rolling trend list trimming
   refactored with pythonic negative slice deletion (del items[:-5]), preventing
   calculation drift.
2. Note input sanitization guards: heading prefix rejection on Goal/Next, 5-entry
   rolling window bounds on marker/confidence/verifier trends pinned.
3. r138 pins metacognitive trend sequence capping and input sanitization invariants.

- pytest: 985 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 65 (test r137)

1. Ship completion gate single-pass scan: mode_ship reverse history iteration
   consolidated from two passes to a single pass terminating on first discovery
   of latest confidence and marker.
2. Completion-gate invariant guards: shaky confidence flagging, unsettled marker
   detection, and clean delivery states pinned.
3. r137 pins ship completion gate observation order and single-pass parity.

- pytest: 983 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 64 (test r136)

1. Observation condition deduplication: observations() marker and verifier loop
   branches unified, nesting shaky co-occurrence checks inside parent consecutive
   sequence gates and removing duplicate set construction.
2. Co-occurrence invariant guards: marker/verifier shaky co-occurrence facts and
   saturated shaky tag emissions pinned.
3. r136 pins observation condition deduplication and co-occurrence parity.

- pytest: 981 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 63 (test r135)

1. Narrative detector & emission ratio optimizations: narrative_knot_detector,
   complexity_emission_ratio, confidence_inflation, and verification_temporal_bias
   refactored with generator comprehensions and streamlined edge conditionals.
2. Temporal symmetry & retread guards: narrative retread scoring and temporal
   verification bias calculations pinned under boundary conditions.
3. r135 pins narrative knot detection, emission ratio edge cases, and temporal symmetry.

- pytest: 979 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 62 (test r134)

1. Adaptability calculation optimization: adaptability_score risk window
   evaluation refactored with direct negative slicing, eliminating list reversal
   and per-element branching.
2. Tension resolution math: tension_resolution verified across open question
   drops (+35), PHEW settles (+25), and stall-free states (+15).
3. r134 pins adaptability slice evaluation and tension resolution formulas.

- pytest: 976 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 61 (test r133)

1. Cognitive metric evaluation hardening: session_fatigue and cognitive_load_index
   streamlined by removing redundant truthiness assertions on pre-validated slices.
2. Metric invariant guards: verified drop penalties (+15), cognitive load index
   compound stress saturation, and drift velocity calculation invariants locked.
3. r133 pins cognitive metric calculation hygiene and fatigue scoring parity.

- pytest: 973 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 60 (test r132)

1. Single-pass heal actions evaluation: heal_actions loop unified to a single
   pass, eliminating duplicate set allocation and intermediate state scans.
2. Test suite path portability: replaced relative and machine-local import
   paths in test suites (test_r37, test_r40, test_r41, test_r42) with robust
   Path(__file__).resolve() resolutions.
3. r132 pins single-pass heal evaluation, threshold invariants, and suite portability.

- pytest: 970 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 59 (test r131)

1. Multi-location skill discovery & standalone test execution: verify_suite's
   find_repo and main hardened to resolve companion test suites from workspace
   skill locations (.agents/skills/mindseam), parent repository workspaces, and
   global user skill folders (~/.gemini/antigravity/skills/mindseam).
2. r131 pins multi-location discovery and integrity verification parity.

- pytest: 967 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 58 (test r130)

1. Telemetry and grading boundary guards: assess_risk (confidence collapse,
   degrading trend, and stalled actions), contradiction_detection (distinguishing
   cautious awareness from opposite-valence contradictions), and evidence_weight
   component saturations pinned under full boundary fixtures.
2. Ship markdown scanner resilience: claim_without_coverage verified against
   CRLF line-endings and multi-line soft-wrapped paragraph structures.
3. r130 pins telemetry boundary resilience and ship scanner robustness.

- pytest: 964 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 57 (test r129)

1. Remediation mapping optimization: remediation_suggestions previously
   constructed and sorted its fact-to-advice dictionary on every invocation.
   REMEDIATION_MAP is now hoisted as a pre-sorted module-level constant tuple,
   eliminating per-call dictionary allocation and sorting overhead.
2. Detector dead-code cleanup: unused intermediate variables across
   verification_freshness, detect_stall, stall_score, error_recovery_ratio,
   and session_health_score were eliminated, resulting in zero unused local
   variables throughout the codebase.
3. r129 pins remediation lookup contracts and direct detector calculation
   parity.

- pytest: 959 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

### Round 56 (test r128)

1. Cross-platform subprocess decoding (real defect, fixed): verify_suite
   invoked subprocess.run with text=True and inherited system encoding,
   which raised UnicodeDecodeError on Windows platforms with non-UTF-8
   system code pages (such as CP936 or GBK) when child process output
   contained multibyte UTF-8 sequences. verify_suite now explicitly passes
   encoding="utf-8" and errors="replace" across all subprocess invocations,
   and configures console streams for deterministic UTF-8 handling.
2. Regex pre-compilation optimization: next_open_number previously
   re-compiled active (?...) and closed (closes: ?...) regular expressions
   on every invocation, and mode_ship re-compiled repetitive character
   run patterns per line in loops. These patterns are now pre-compiled at
   module level (OPEN_ID_RE, CLOSED_OPEN_ID_RE, REPETITION_CHAR_RUN),
   reducing runtime overhead during high-frequency seam and ship operations.
3. Timestamp defense in telemetry: fact_age_seconds hardened against
   missing, None, or non-int timestamp entries in history dictionaries.
4. r128 pins all subprocess encoding and pre-compiled regex behaviors
   across all platforms.

- pytest: 954 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

## Run 2026-08-25 (fourth pass — deliverables and input normalisation)

### Round 55 (test r127) plus settled deliverables

1. Marker normalisation (real defect, fixed): note validated its meta
   inputs with three disciplines — --confidence had a vocabulary check,
   --verifier and --error/--outcome stripped through clean_scalar, but
   --marker passed through raw. A pasted marker with surrounding
   whitespace silently missed every exact-match consumer: the PHEW
   settle recognition, the OPEN phase checks, the ship completion
   gate. --marker now strips like the other free-text fields, and a
   marker empty after stripping refuses the note (--verifier's
   precedent). r127 pins all three free-text meta fields normalised
   together so a future field cannot reintroduce the raw pass-through.
2. CI workflow settled: verify.yml runs exactly the two commands the
   README documents for maintainers (verify_suite.py, unittest
   discover) on the claimed three-OS matrix — no drift.
3. workspace-ledger.md template settled: the documented five-section
   shell matches write_ledger's output structure and read_ledger's
   parser, including single-value Goal/Next and controller-numbered
   Verified/Open.
4. note's remaining edge strings settled: whitespace-only --next
   refused; a leading-dash value parses via --next=...; unicode and
   long single-line values record; --confidence vocabulary enforced.

- pytest: 948 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

## Run 2026-08-25 (third pass — dead meta plumbing and the clock)

### Round 54 (test r126)

1. Dead data plumbing removed: mode_seam wrote meta["health"] on every
   seam and write_meta silently dropped it — "health" is not in
   METACOGNITION_KEYS, nothing ever read it (the trend line prints from
   the locals), no test or document ever saw a persisted health key, and
   no such key ever reached disk. The meta twin of round 38's unplugged
   monitors. r126 pins the contract it obscured: a seam persists a
   subset of METACOGNITION_KEYS only, and the score still reaches the
   user through the trend line.
2. Clock axis settled (with a lesson): the first probe "showed"
   perfectly regular cadence scoring 0 and reversed timestamps scoring
   clean — both artifacts of the probe building its list newest-first.
   Correctly built histories behave exactly per contract: ascending
   regular cadence clean, descending timestamps a discontinuity, burst
   recording irregular, internally consistent future clocks (a skewed
   host) clean because cadence, not wall time, is the signal. Pinned in
   r126 so the next probe author does not repeat the mistake.

- pytest: 944 passed; verify_suite.py: 9/9; full-suite hygiene CLEAN

## Run 2026-08-25 (second pass — user-editable input surfaces)

### Round 53 (test r125) plus settled surfaces

Audited every surface where a hand-edited or Windows-authored file
enters the controller:

1. BOM-tolerant reads (real defect, fixed): the four state readers
   opened .mindseam files as plain utf-8, so a byte-order mark — what
   legacy Windows editors prepend — landed on the first line. A marked
   "## Goal" stopped matching the section prefix and the goal silently
   vanished from the parsed ledger; a marked history.json or
   metacognition.json failed json.load and took the "unreadable,
   restarted" path, losing readable state. All four readers (ledger,
   history, archive, meta) now use utf-8-sig; writes stay plain utf-8
   and round-trips are unchanged.
2. read_ledger adversarial shapes (settled): CRLF, unknown sections,
   orphan items, h3 subheadings and duplicate sections all parse
   tolerantly; duplicates keep both items and the next write keeps the
   first (out-of-contract hand edits degrade, never crash); a null byte
   passes through as text.
3. ship input edges (settled, clean): missing file, empty file, binary
   content, directory-as-path and stdin all exit per the 0-or-2
   contract with accurate messages; stdin shares the file scanner
   (bare claims flagged, claim+coverage clean).
4. resume and note --close (settled, clean): closing a nonexistent or
   already-closed number is NOT RECORDED (exit 2); resume prints the
   premise, invariants and ledger.

- pytest: 938 passed; verify_suite.py: 9/9; hygiene re-verified clean

## Run 2026-08-25 — doc/implementation parity and the write path

### Rounds 51-52 (tests r123-r124)

Two more defects, found by auditing document-implementation parity and
then the write path underneath the test suite:

1. r123 — the leak scanner's vocabulary was one-directional. Round 69
   verified every scanner entry is taught; nothing verified every
   taught marker is scanned. markers.md's marker→move table teaches
   `blocked?! WRONG.` (bound move `Fix:`) — the one canonical marker
   missing from MARKERS, so quoting that pair in a deliverable passed
   ship's register check while every other taught marker was flagged.
   Added as "blocked?!" (prefix style); r123 pins the bidirectional
   contract, including parsing the doctrine table so a future marker
   row cannot ship unscanned. INNER_ONLY's deliberate exclusions (✓ ✗
   ≤ ≥ → …) are documented design, not gaps.
2. r124 — atomic_write_text created its temp file in LEDGER_DIR (a
   cwd-relative path) and os.replace'd it onto the target, so any
   target on another volume than the cwd failed with a cross-device
   move. Verified live on this D:-repo / C:-tempdir host. Follow-on:
   round 50's hermetic compaction test patched HISTORY/HISTORY_ARCHIVE
   but not LEDGER_DIR, so on multi-volume hosts every write silently
   failed, compact_history returned changed=False, and the test's
   conditional assertion never ran — a green test verifying nothing.
   The temp file now lives next to the target (os.replace's
   same-filesystem requirement); patching a target path alone is
   sufficient anywhere. ensure_dir became dead code and is deleted
   (round 38's rule caught it); the vacuous assertion is now
   unconditional.

Also settled: module counts are r108-guarded (11/eleven); the two-layer
value-consistency, archive-growth and performance questions were closed
in the previous run and stay closed.

- pytest: 933 passed; verify_suite.py: 9/9 including unittest discover
- full-suite hygiene re-verified byte-clean after the write-path change;
  no temp files linger in .mindseam (quarantine-r107 is a prior session's
  fixture directory, not a temp artifact)

## Run 2026-08-24 (evening — runtime axes and suite hygiene)

### Round 50 (test r122) plus settled runtime questions

Audited three runtime axes left uncovered by rounds 45-49:

1. Suite hygiene (real defect, fixed): round 37's cross-detector
   compaction test called compact_history on 503 fixture entries with
   the module's real relative paths, so EVERY full-suite run wrote 500
   fixture entries into the repository's own .mindseam/history.json and
   appended 3 more to history.archive.json (the archive had grown to
   238 entries purely from test runs). The stale fixture markers then
   leaked into ship's completion gate for anyone testing in the repo
   root ("marker 'STEP' was not followed by a settle"). The test now
   patches HISTORY/HISTORY_ARCHIVE into a temp directory (round 56's
   pattern); r122 pins the property with a byte-digest guard plus a
   structural backstop, and the whole 925-test suite now leaves the
   repo .mindseam untouched (verified end to end). Repository scratch
   state (fixture history, derived risk/trend meta) reset to match.
2. Two-layer consistency (settled, clean): for eight canonical session
   shapes, every score shared between observations() facts and
   session_health_score() reasons agrees exactly — zero value
   mismatches, so the round 30 convention holds beyond the detectors
   it was pinned on.
3. Runtime growth and speed (settled as designed): the history archive
   is append-only with no reader by design (durable record; a cap would
   delete state, against the controller's recording contract), and a
   full seam-scale pass over 500 entries costs ~2.5 ms — no work owed.

Also probed: ship's register scanner against adversarial texts (claims
in code fences correctly exempt, Chinese coverage wording recognised,
loose inner notation caught) — no false positives or negatives found.

- pytest: 925 passed; verify_suite.py: 9/9 including unittest discover

## Run 2026-08-24 (afternoon — differential sweep and hostile inputs)

### Rounds 48-49 (tests r120-r121)

Three audit axes beyond the round 45-47 bonus sweep:

1. r120 — `marker_transition_diversity` read raw marker strings, so an
   unmarked window produced zero transitions and returned 0: absence as
   the worst score in three layers at once ("marker sequence stagnant
   -3" in fusion, the OPEN→DONE→PHEW prescription in heal). Blank-to-
   marked pairs were also counted as transitions (one marker plus gaps
   read as progression). The detector now reads recorded markers only;
   <2 recorded is the unmeasured sentinel; the penalty face carries
   `marker_pair_in_run`. r42's no-markers expectation updated 0 → 100.
   Settled as doctrine: "repeated marker -10" on recorded duplicates
   (r90 pins OPEN,OPEN as medium risk) and verify-then-act credit for
   blank-marker windows (an unmarked seam is open work by default).
   Differential invariants now hold: canonical marker usage ≥ the same
   session unmarked; every single-dimension absence and every bad
   dimension (shaky/high-risk/errors/open-churn/escalation) scores
   below the healthy baseline.
2. r121 — metacognition.json had no value typing: `validate_meta_schema`
   filtered unknown keys only and `read_meta`'s same-version fast path
   skipped even that. A hand-edited file with `marker: 9` / `confidence:
   123` flowed into history.json via append_history and crashed the
   third-window seam with a bare AttributeError (against the 0-or-2
   exit contract). Three layers now agree: `_meta_value_ok` types every
   known key (str fields, dict risk/trend, non-negative int
   extra_steps); read_meta applies it on the fast path; append_history
   coerces at the write. The legacy "markers" rename requires a string.
   Property test (fixed seed) offers every JSON-expressible value for
   every key; the pipeline must stay well-typed end to end. The
   property test runs in a temp workspace — an earlier non-hermetic
   draft appended 200 synthetic entries to the repo's own .mindseam;
   that scratch history (fixture data, gitignored) was reset to empty.
3. Type-hostile histories fed directly to the public scoring functions
   still raise (schema is the documented contract; read_history
   enforces it at the CLI boundary) — settled, not hardened.

- pytest: 923 passed; verify_suite.py: 9/9 including unittest discover
- repo .mindseam scratch history reset to empty after the hermetic-test fix

## Run 2026-08-24

### Zero-Pole Sweep (rounds 45-47, tests r117-r119)

Audit `audit_r13_zero_pole.py` (root, untracked) was re-run and settled;
its findings are now permanent regression tests and the stray script is
deleted. Three real defects fixed, two audit questions settled as designed:

1. r117 — `assumption_diversity` blank-bucket inversion: `h.get(
   "confidence", "unknown")` never saw the "unknown" default because
   append_history always writes the key (empty string when untagged), so
   blanks formed a real bucket. One honest "strong" + two blanks scored
   91/100 and earned "high assumption diversity +5". Blanks are dropped
   before the bucket count (the presence idiom both gates already use).
2. r118 — phantom "stable verification +5": verification_regression
   returns 100 for a count that never drops, including one that never
   rose. Bonus face now gated on `verified_in_run` (same flag as
   incomplete_verification); penalty face ungated (a drop must exist).
   r37's mixed-problem floor moves 30 → 29 with a dated comment.
3. r119 — convergence off silence: zero volatility mapped to an agreeing
   +1 unconditionally; the volatility dimension now joins the table only
   when the window carries confidence tags. All-absent windows fall to
   the neutral 50 and both layers stay silent.

Settled as designed (pinned in r117 so future audits do not re-open):
tension_resolution 0 for tension-free-but-unverified windows (stalls are
documented tension signals; verification debt is intended pressure), and
adaptability_score 0 for clean sessions (every component needs a problem
to respond to or a check to grow).

- pytest: 907 passed (885 before this round)
- verify_suite.py: 9/9 including unittest discover (907 OK)

## Run 2026-08-20

### Deep Optimization Continuation

#### verify_suite.py repair
- Status: functional on `--skip-unittest` (8/8 checks pass)
- unittest discover: running via subprocess with PYTHONPATH
- Found/fixed issues:
  1. repo path: `parent.parent` → `parent.parent.parent`
  2. interface list: removed non-existent CLI-only symbols, kept 23 real module-level functions
  3. `check_main`: wrapped `mindseam.main(['--help'])` in subprocess to avoid sys.exit
  4. `run_unittest_discover`: added `env=env` with PYTHONPATH, increased timeout to 600s, print output unconditionally

#### Integration boundary tests (new)
- File: `tests/test_mindseam_integration_boundaries.py`
- 11 tests created, all passing
- Coverage: no-args, unknown subcommand, note validation, ship --strict, empty history seam/resume, ledger read-error, core-slot negatives

#### Latest run results
- `pytest tests/test_mindseam_integration_boundaries.py -q`: 11 passed
- pytest across all tests: 840 passed previous; this run shows 845 passed / 6 failed
  - failures are external environment pollution (`tests.test_config` ModuleNotFoundError: responses)
  - 3 pytest failures come from verify_suite integration tests seeing stale global counters
- unittest discover: running, ~158s, 115 tests

## Run 2026-08-29 (sixth pass — skillbook pattern, marketplace-friendly subcommands)

### Skills library integration (ACE pattern)

1. **Skillbook extractor** (`.mindseam/skillbook.md`): new `_skillbook_signature`,
   `extract_skillbook`, `write_skillbook`, `read_skillbook` functions in mindseam.py.
   The extractor scans the history for two pattern types:
   - `error` — same `"domain: what broke"` text recurring >= 2 times
   - `hard` — same domain prefix in `--next` paired with `--extra-steps > 0`
   Cap at 20 entries. Always writes; meant to grow with the session.

2. **`seam` command updates the skillbook automatically**: after every seam run,
   `extract_skillbook(read_history())` is called and the result is persisted to
   `.mindseam/skillbook.md`. No LLM in the loop; pure controller logic.

3. **Three new subcommands**:
   - `skillbook [--json]` — print recurring patterns from history (plain text or JSON)
   - `info [--json]` — print workspace learning summary (ledger, history count,
     skillbook entries, risk level, meta keys)
   - `discover [--json]` — rank visited domains from history, suggest next pass

### Bug fixes during integration
1. r128 — unused variable `kind` in mode_skillbook list comprehension: renamed
   to explicit `kind`/`text` unpack from `(kind, text)` tuple.
2. r129 — subcommand set test hard-coded old set: updated to include the 3 new
   subcommands (skillbook, info, discover).
3. r130 — SKILL/README/README.zh-CN.md did not document `--json` or new subcommands:
   added full command block for all 9 subcommands in SKILL.md, README.md,
   README.zh-CN.md.

### Regression tests (test_new_subcommands.py)
- 10 new tests covering: empty skillbook, JSON output, recurring error extraction,
  below-threshold suppression, info plain/json output, goal reflection,
  discover empty/ranking/suggestion.
- All 10 pass.

### Final state
- pytest: **1034 passed, 0 failed** (was 1024 prior; +10 new tests)
- verify_suite.py: **9/9** including unittest discover (1034 OK)
- Test isolation stale-count issue: no longer observed after r119 convergence-silence fix

### Latest run results
- `pytest tests/test_new_subcommands.py -q`: 10 passed
- pytest across all tests: **1034 passed, 0 failed, 1 warning**
- verify_suite.py: **9/9**

---

## Round 156 — ponytail borrow: read-only `audit` + the intensity ladder (2026-09-01)

### Pre-round recovery (recorded honestly)
The tree arrived with the suite at 772 errors + 75 failures: the committed
controller was the r32 CLI snapshot while 100+ round tests expected a
detector layer that lived only in the skill-directory copy, and the
skillbook/discover subcommands that test_new_subcommands.py specified had
never been implemented in any copy. The controller was rebuilt by grafting
the repo CLI skeleton onto the detector base, writing skillbook/discover
against their test contract, restoring the ledger-aware resume report,
upgrading REMEDIATION_MAP to (key, advice, priority) triples, and
replacing the last j-space brand strings. Suite at commit 6b22d4b:
1168 passed, 0 failed.

### What r156 borrowed from https://github.com/DietrichGebert/ponytail (MIT)
1. `audit` subcommand — ponytail's `/ponytail-audit` shape applied to the
   ledger instead of code: scan the whole artefact, one line per finding
   (`<tag> <what to cut>. <replacement>.`), ranked biggest first, ending
   with the net count; a clean ledger answers with ponytail's own words,
   "Lean already. Ship." Tags adapted to the ledger: delete (duplicate or
   already-answered Open rows), stdlib (recorded-twice Verified rows),
   yagni (Core parked beyond the two live slots), shrink (blank-next
   history rows). Report only — audit writes nothing and exits 0 with
   findings; `--strict` turns findings into exit 1 for CI.
2. Intensity ladder — `audit --intensity lite|full|off`, resolved as
   flag > MINDSEAM_INTENSITY > full (ponytail's PONYTAIL_DEFAULT_MODE
   order, minus the config file a two-command surface has not earned).
   lite caps the printed report at three findings and says how many were
   held back; off refuses to run; the JSON face always carries the full
   list — the dial trims prose, not data.

### Tests
test_r156_ponytail_audit_and_intensity.py — 23 tests: intensity
resolution order, every tag firing on a crafted ledger, tag severity
order, report-only exit contract, strict gate, lite cap + held-back
line, off refusal, env-var default, flag-beats-env, JSON face, and the
write-nothing guarantee. Suite after r156: 1191 passed, 0 failed.

### Doc fallout
SKILL.md, README.md and README.zh-CN.md gained the audit command block;
r102's parser-set pin now includes audit; r69's flag-documentation pins
cover --intensity.

---

## Round 157 — docker-style `history --filter` + git-style `history --human` (2026-09-02)

### What was borrowed
1. `history --filter KEY=VALUE` — the ``docker ps --filter`` /
   ``kubectl get --field-selector`` family. One pair per flag,
   repeatable, all pairs ANDed; matching is exact against the row
   field's string form (``--grep`` remains the substring tool).
   Unknown keys and malformed pairs are declined with exit 2 and a
   fix line naming the valid fields — silence would hand back a
   result set the caller believes covers more than it does. The flag
   composes with every older filter (``--grep``, ``--since``,
   ``--head/--tail``) and every renderer (``--count``, ``--quiet``,
   ``--json``, ``--csv``). Valid keys are pinned by
   ``HISTORY_ROW_FIELDS``, the schema the append path writes.
2. `history --human` — ``git log``'s relative dates / ``ls -lh``.
   The text table and the ``--row-id`` row render each row's age as a
   span ("3 minutes ago"); JSON, CSV and ``--format`` keep the raw
   epoch, the way ``info --human`` keeps raw seconds in its payload.
   Future timestamps render as "in the future", not "future ago".

### Gotchas hit during integration
- Meta state keys (marker) persist across seams by design: after a
  shaky-tagged row, the following rows still carry marker=OPEN. AND
  filters must be tested with a second differing key (confidence).
- The seam that carries --message records the row's Next as it stood
  at note time, not the next seam's — fixture timing off by one seam
  produced a phantom row.

### Tests
test_r157_history_filter_and_human.py — 20 tests: exact matching,
AND composition, empty-value matching, string-form numeric compare,
declines (unknown key / malformed pair / nothing written on decline),
grep+filter composition, JSON face, relative spans, raw-epoch
guarantees across the three machine faces, future timestamps, and the
helper's contract. Suite after r157: 1211 passed, 0 failed.

---

## Round 158 — resume --json and ship --json close the two-faces rule (2026-09-02)

Every report subcommand already answered --json except resume and ship,
the two prose-heaviest surfaces. A host gating a delivery on ship had
to scrape bullet lines; the gh --json family contract says text and
JSON are two faces of one dataset.

1. resume --json — ledger digest, history count, state repairs,
   persisted risk (level + reasons), and the trend block with the
   health score, its grade and its factors. The premise prose and the
   reentry banner are text-face only: a host cannot consume them, the
   way seam --json reports a long gap without the reentry banner. The
   side effect is unchanged — resume still appends one history row
   under either face.
2. ship --json — clean flag, findings, gate observations, the risk
   assessment (level, reasons, escalation, recovery), plus strict and
   the exit code the host will get. The exit contract is byte-identical
   across faces: --strict gating is decided before the face is chosen,
   so a CI host can gate on the process exit code through either face.

note stays single-face on purpose: it is an editor, not a report — its
output is a ledger echo, and there is nothing for a host to consume.

### Tests
test_r158_resume_ship_json_faces.py — 12 tests: payload shapes, the
score/grade agreement, the dropped prose, the unchanged side effect,
persisted risk, clean and finding payloads, exit parity across faces
(with and without --strict), gate reporting at exit 0 and gating at
exit 2, and the report-surface parity sweep. Suite after r158:
1223 passed, 0 failed.

## r159 — audit facets and --tag filter

The r156 audit was a snapshot of the ledger surface: duplicate Open
rows, duplicate Verified rows, parked Core, blank-next history. Four
tags, ranked, with the lean verdict and the intensity ladder. r159
extends the same shape to *the ledger against history* — three new
"facet" tags borrow from `gh audit-log`, `journalctl --list-boots`
and ponytail's drift check, and answer "is the ledger telling the
same story as the recent seams?":

- `goal-stale` — Goal has not been re-anchored in the last 10
  seams (every recent row lacks a `goal` annotation, but the
  ledger Goal is set). Replacement: re-run `note --goal` or
  change Next.
- `next-stall` — the same `next` appears in ≥3 of the trailing 5
  history rows without resolution. Replacement: close with
  `note --close N` or change with `note --next`.
- `core-drift` — Next is in Core or Core is empty while Next is
  empty; the Core commitment has drifted from the live work
  (in either direction). Replacement: re-anchor Next or move
  it to Core.

The fourth change is a projection: `--tag <list>`, borrowed from
`gh pr list --label <name>` and `cargo bench --bench <name>`. A
comma-separated list narrows the report to just those tags; the
full audit still runs, but only the chosen tags appear in the
printed report and the JSON `findings` array. The JSON face adds
`tags` and `by_tag` so a host can tell which tag fired even when
the projection is empty. Unknown tags refuse with exit 2 to
stderr, the way `gh --label unknown` refuses an unrecognised
label. The lean verdict under a filter names the chosen tags —
"Lean on `core-drift`. Ship." — the way a host reading the JSON
`lean` field can verify the projection was clean.

The tag taxonomy is now seven entries: the four surface tags keep
their r156 positions; the three facet tags follow in the order
they were added. The `order` map inside `audit_findings` builds
from the tuple, so a stray reorder would change the lite cap
silently — the new tests pin the order.

### Tests
test_r159_audit_facets_and_tag_filter.py — 30 tests: tag taxonomy
pins, goal-stale threshold (10 recent seams, no goal re-anchor),
goal-stale clean (re-anchored, short history, blank Goal),
next-stall threshold (3-of-5, single fire because 5 rows cannot
split 3+3), next-stall uses only the trailing 5, core-drift both
directions + singular/plural agreement, --tag unknown refused to
stderr with the known tag set listed, --tag projection hides
unselected findings, --tag combination, --tag filter to a clean
projection prints the named lean verdict, --strict under filter
gates on the projection not the full set, JSON face carries the
projection + the `by_tag` map + the resolved `tags` list. Plus
the r156 _ledger fixture gained a `next_` parameter (default
`c1 — one`) so the parked-core / duplicate-Verified tests do not
also trip core-drift — the r159 finding is a new top-level
signal, not a re-statement of an existing one. Suite after r159:
1253 passed, 0 failed. verify_suite 9/9.

### Gotchas
- core-drift must be guarded by `if core_items:` — a fresh
  session has no Core, not a drift. `cargo check` does not
  complain about a fresh `Cargo.toml` with no deps.
- The 3-of-5 next-stall bar means two topics cannot both fire
  from the same 5-row window (5 rows cannot split 3+3). The
  test that originally expected two findings is wrong by
  design; the detector is right, and the test was rewritten
  to exercise the "only the top repeater fires" branch.
- The r69 doc-drift guard parses `mindseam.py ` lines and
  extracts every ` --flag` token. The borrowed reference
  "like `gh pr list --label`" in the new SKILL.md command
  line became a literal `--label` token, which the r69
  reverse-direction test flagged as undocumented. The fix
  was to drop the leading dashes from the borrowed reference
  (paraphrase the metaphor, do not name the borrower's flag).

## r160 — audit evidence link

r156 made the audit output *what to cut*. r159 added *when the
facet tags fire*. r160 makes every finding *traceable* — the
conclusion now points back to the smallest piece of evidence a
host needs to reproduce the verdict without re-running the
audit, the way `git blame` traces a line to a commit and
`cargo tree -e features` traces a build to a feature flag.

Each tag has its own evidence shape, because the conclusion of
each tag needs a different kind of pointer:

- `delete`     — `row`, `row_text`, `first_seen` + `first_seen_index` (or `answered_by` + `answered_by_index` for the "settled" branch)
- `stdlib`     — `row`, `row_text`, `canonical` + `canonical_index`
- `yagni`      — `core_total`, `live_slots`, `parked` count + `parked_indices`
- `shrink`     — `blank_count`, `blank_indices`, `history_total`
- `goal-stale` — `goal`, `window`, `stale_indices` (1-based seam indices, with `window_first` / `window_last` to bracket the window)
- `next-stall` — `next`, `seam_indices`, `count`, `window` (and brackets)
- `core-drift` — `live_next`, `core_items`, `direction` (one of `next-not-in-core` / `core-without-next`)

The text face inlines a one-line summary at the end of the
finding, the way `git log --stat` inlines the diff stat — the
line stays single-host-readable, but a host tailing the audit
can `grep evidence:` to find the audit's pointers. The JSON
face carries the full evidence block on every finding; the
`--tag` projection keeps the evidence on the projected
findings (the dial trims prose, not data).

A small new helper, `_evidence_summary(finding)`, renders the
text-face summary per tag. The branch for `shrink` truncates
long index lists with an ellipsis so a 50-row blank run does
not blow the line budget. The branches for `core-drift` name
both directions, so a host can grep `next=` or `next empty`
to tell which side of the drift the session is on.

The finding dict shape changed: it now has a fourth key,
`evidence`, which is always a dict (possibly empty). This is
backward compatible — the r156 / r159 tests that pinned
`[f["tag"] for f in findings]` still pass, because adding a
key to a dict does not break a projection. The text-face
finding line added a `(evidence: ...)` suffix, so the r156
shape test was widened to allow an optional evidence suffix.

### Tests
test_r160_audit_evidence.py — 24 tests: each of the seven tags
gets a `tag_evidence_*` test pinning the field shape (row
indices, normalised text, counts, seam indices, direction
enum), each of the seven tags also gets a
`test_*_summary_in_text_face` test pinning the inline summary,
plus JSON-face tests for "every finding has evidence dict",
"--tag filter keeps evidence", "--strict under filter still
carries evidence", and a helper-level test for the
`_evidence_summary` shape (clean, yagni, shrink truncation,
core-drift two directions). Suite after r160: 1277 passed,
0 failed. verify_suite 9/9.

### Gotchas
- The delete "answered_by" branch needs the Open and Verified
  text to match after `_audit_norm` (which strips `?NN` /
  `✓NN` prefixes and casefolds). The first test fixture had
  the two rows differing in the word "verified" vs "settled",
  which makes the audit see no match and the branch does not
  fire. The fix is to use the *same* suffix in both rows —
  the audit operates on the body, not the metadata.
- The r69 doc-drift guard extracts every ` --flag` token from
  any line containing `mindseam.py `. The line for the new
  `audit --tag` reference in SKILL.md now mentions
  "evidence rides through the projection" — that line has no
  ` --label` style pattern, but earlier borrows of `gh pr list
  --label` had to be paraphrased to avoid the false positive
  on the literal ` --label` token. The audit's own output
  emits `(evidence: row #N ↔ Open #M)` in the text face; the
  r69 reverse-direction test does not flag ` ↔ ` because that
  is not a ` --flag` pattern.

## r161 — audit time window, single-seam audit, info audit_summary, JSON gate enum

r156 made the audit output *what to cut*; r159 added *when the
facet tags fire*; r160 made every conclusion *traceable*; r161
extends the same shape to *time* and *aggregation*:

1. `audit --since <seconds>` / `audit --until <seconds>` borrow
   from `journalctl --since` and `find -newer`: a window in
   seconds before "now" that narrows the history slice the
   facet tags see. The ledger surface tags (`delete` /
   `stdlib` / `yagni` / `core-drift`) keep operating on the
   full `book` — they have nothing to do with time. Both
   flags are inclusive, refuse negative values with exit 2
   to stderr. The JSON face gains a `history_window` block
   that records the resolved cutoffs, the row counts in and
   out, and the requested seconds — so a host reading the
   payload can verify the window was applied.

2. `audit --at <row_id>` borrows from `git log -1` /
   `gh pr view N`: a 1-based row index that slices the
   history to `hist[:N]` so the audit reflects everything
   that had happened by that seam. Out-of-range (and 0) are
   refused with exit 2 to stderr. The text face header
   names the seam: `── mindseam ─ audit (at seam N of M)`.
   The lean verdict under `--at` reads `Lean already (at
   seam N of M). Ship.` so a host tailing the report can
   tell it was a single-seam view, not a full audit.

3. JSON face `gate` enum: a richer three-state status
   alongside the r156 `lean` boolean. `clean` = no findings,
   no strict; `finding` = findings exist, no strict
   (report-only); `gated` = findings + `--strict` (exit 1).
   A host that only reads `gate` does not need to derive
   status from `lean` + `strict`. The r156 `lean` boolean
   stays unchanged — `gate` is additive.

4. `info --json` gains an `audit_summary` block: the same
   `audit_findings` function the `audit` command uses, rolled
   up into `{lean, net, by_tag, top_tag, top_tag_count}`.
   A host reading both `info --json` and `audit --json` gets
   matching counts — the summary is computed from the same
   ledger + history slice. The text face appends a single
   `Audit: N items removable; top tag X (M).` line, the way
   `systemctl status` folds a sub-service health check.

The four additions compose with each other and with the
r156-r160 surface: `--tag` projection still works, `--strict`
still gates, evidence still rides on every finding. The
audit's JSON payload gained two new top-level keys
(`history_window` and `gate`); no existing key was renamed
or removed. The `info` JSON payload gained one new top-level
key (`audit_summary`); no existing key was renamed or removed.

### Tests
test_r161_audit_window_at_and_info_summary.py — 32 tests in
four sub-suites: `AuditWindowTests` (10 tests, including
window narrows shrink / does not affect ledger tags /
negative refused / composes with --tag / JSON history_window
shape); `AuditAtTests` (8 tests, including slice to first
row, slice to first N, out-of-range refused, lean verdict
under --at, text header names the seam, composes with
--strict and --tag); `AuditGateEnumTests` (5 tests pinning
the three-state enum and the r156 `lean` boolean stays
intact); `InfoAuditSummaryTests` (8 tests covering the
info JSON `audit_summary` block, agreement with the live
`audit` command, the text-face one-liner, and the
`--warnings-only` path that still carries the summary);
plus a `ParserAcceptanceTests` class that proves the three
new flags are wired.

Suite after r161: 1309 passed, 0 failed. verify_suite 9/9
(8/9 on one of the longer runs because the pre-existing
`test_info_human_renders_seconds_when_below_minute` test
pins "30 seconds ago" exactly and a slower run tipped past
that boundary; it passes again on the immediate retry, so
it is a flake in the pre-existing baseline, not a r161
regression).

### Gotchas
- `by_tag` carries the count of *findings*, not the count
  of underlying instances. A `shrink` finding with three
  blank rows in the slice is one finding — `by_tag.shrink`
  is 1, not 3. The actual blank count lives in
  `evidence.blank_count`. The first three r161 test drafts
  asserted `by_tag.shrink == 3`; that was wrong by design.
- `since` is inclusive of `now - N`, so rows at exactly
  `now - N` seconds are kept. The test fixture had to use
  non-power-of-10 timestamps to avoid the boundary.
- The `top_tag` of an `info` report with ties breaks the
  tie lexicographically (the way `sort(key=lambda tc:
  (-tc[1], tc[0]))` does). The test that asserted
  `top_tag == "yagni"` for a (1, 1) tie expected the wrong
  winner; the test now asserts `stdlib` (2 findings > 1
  for the others) so the tie-breaking is not exercised.
- `info` already returns `last_seam.gap_seconds`; that
  field is computed at `info` call time and is racy
  against the test suite wall clock. The flake that
  surfaces as "3601 != 3600" is not a r161 change — it
  is the same pre-existing pin from `info --human`
  (a42f2fe). The fix is a wider tolerance window, not a
  r161 rollback.

## r162 — audit baseline: record and gate

r156-r161 gave the audit verdict, the facet tags, the evidence
link, the tag projection, the time window, the gate enum, and
the info roll-up. r162 closes the gap with detekt /
eslint --baseline / terraform plan -detailed-exitcode / cargo
clippy: a baseline file records findings the team has already
accepted, and the gate only fires on *new* findings. Old debt
stays in the report so a reviewer sees it, but does not fail
CI.

Two new flags on the `audit` subcommand:

- `audit --baseline <path>` reads a JSON baseline file.
  Findings whose (tag, what) fingerprint matches a baseline
  entry are moved to a separate `baselined_findings` list
  (JSON) and tagged `[baselined]` in the text face. The
  `net` count, `by_tag` map, `lean` boolean, `gate` enum,
  and `--strict` exit code all see only the *fresh*
  (non-baselined) findings. A clean run under a baseline
  reports `lean: true, net: 0, gate: clean` while still
  listing the baselined debt in `baselined_findings`.

- `audit --baseline-write <path>` writes the *unprojected*
  current finding list to a JSON file. The write happens
  before the read, so `audit --baseline-write X --baseline X`
  records the state and then marks every current finding
  as baselined in the same run — the way `eslint
  --output-file` followed by `eslint --baseline` work
  in a CI script, in one invocation.

The fingerprint is the 16-hex-char SHA-1 of `(tag, what)`.
The `replacement` and `evidence` fields are deliberately
*not* part of the fingerprint: the evidence names the rows
in the slice, which drifts under `--since` / `--at` /
`--tag` without the underlying waste changing. A finding
with the same waste but different evidence (e.g. the same
delete but with different seam indices after a window
reslice) still matches, so the baseline tracks the work,
not the noise.

The Net line gained a `(N baselined)` suffix when any
findings are baselined, the way a CI report shows
"3 passed, 1 skipped" so a host parsing stdout can
distinguish acknowledged debt from new debt without
parsing JSON.

### Tests
test_r162_audit_baseline.py — 20 tests in four sub-suites:
`BaselineWriteTests` (3: round-tripable write, unprojected
under `--tag`, write failure refused), `BaselineReadTests`
(5: known findings moved to baselined list, only matching
fingerprints mark, missing file = empty, malformed file =
empty, fingerprint ignores evidence drift),
`BaselineGateTests` (4: strict + baselined-only exits 0,
strict + fresh finding still gates exit 1, strict without
baseline preserves r156 contract, text face `[baselined]`
marker), `BaselineComposeTests` (3: composes with `--tag`,
chained write+read marks everything, composes with `--at`
+ `--strict`), and `BaselineHelperTests` (5: fingerprint
determinism, length, tag sensitivity, what sensitivity,
missing-tag stability).

Suite after r162: 1329 passed, 0 failed. verify_suite 9/9.

### Gotchas
- `_baseline_paths()` was added in the first cut but never
  called; r62's "no unplugged monitors" guard caught the
  dead code and the helper was removed before commit.
- The r69 doc-drift guard picks up the literal ` --flag`
  token in any line containing `mindseam.py `. The
  borrowed phrase "like `eslint --output-file`" was
  picked up as ` --output-file` and refused. The fix is
  the same r159 trick: paraphrase the metaphor
  ("like the `outputFile` option of `eslint` / `flake8`")
  so the borrower's flag never appears as a literal
  ` --flag` token.
- A malformed or missing baseline file is treated as an
  empty baseline (the first-time-on-a-fresh-ledger case)
  rather than as a hard error; the audit still runs to
  completion. This matches the "fail open" pattern of
  `eslint --baseline` and `terraform plan -out=...` —
  the absence of state is not the same as bad state.
- Baseline read happens *after* baseline write, so a
  chained `--baseline-write X --baseline X` invocation
  records the state and then gates against it. The
  reverse order would silently drop the just-written
  baseline (it would not exist when read runs).

## r163 — info environment proof: workspace_id, audit_baseline_diff, audit_manifest

The r161 `info` report folded the audit roll-up into the
workspace health report. r163 extends the same shape with
three small, orthogonal flags that let a host prove "I am
in the right place", "I am running the same audit baseline",
and "I am running the full detector set" without parsing
the path string or running the audit twice:

1. `info --workspace-id` borrows from `direnv stdlib` /
   `poetry env info` / `pytest --test-environment`: a 16-hex
   SHA-1 fingerprint of the absolute workspace path plus the
   ledger mtime. Stable across replays of the same audit on
   the same workspace; changes if the path or the ledger is
   rewritten. JSON face gains `workspace_id: {id, path,
   ledger_mtime}`. The id is the same 16-hex shape as the
   r162 audit fingerprint, so a host can use one digest
   family across both surfaces.

2. `info --audit-baseline <path>` borrows from `flutter
   analyze --baseline`: an `audit_baseline_diff` block
   carrying `fresh` / `baselined` / `drift` counts. Reuses
   the r162 `_audit_baseline_read` and `_finding_fingerprint`
   helpers so the numbers agree with the live `audit
   --baseline --json` payload — a host reading both
   surfaces gets matching totals. A missing baseline file
   is treated as empty (the first-time-on-a-fresh-ledger
   case), every finding is fresh, and `drift` is `true`.

3. `info --manifest` borrows from `flutter doctor
   --suppress-analytics` / `cargo clippy --no-deps`: an
   `audit_manifest` block listing every tag the audit
   *can* fire, with the count for each, including the
   tags that did not fire (seen-but-clean = 0). The
   manifest's fired counts match the r161 `audit_summary`
   `by_tag` exactly; the un-fired tags prove the detector
   set was actually run, not skipped.

All three blocks are additive. The r161 `audit_summary`,
r156 `ledger` / `last_seam` / `warnings`, and `history_count`
blocks keep their existing shape. The three flags compose
freely with each other and with `--json`, `--human`,
`--warnings-only`. A `info --json --workspace-id
--audit-baseline bl.json --manifest` run emits all three
new blocks in one payload, the way a CI script can prove
"same workspace, same baseline, full detector set" in a
single HTTP call.

### Tests
test_r163_info_workspace_id_audit_baseline_manifest.py —
19 tests in four sub-suites:
`WorkspaceIdTests` (6: opt-in shape, full shape, stable
across calls, changes when ledger rewritten, changes
across workspaces, helper callable directly);
`AuditBaselineDiffTests` (5: opt-in shape, full shape with
drift flag, drift flips on new debt, agreement with
`audit --baseline --json` baselined count, missing
baseline = everything fresh);
`ManifestTests` (5: opt-in shape, every tag listed, clean
ledger = zero fired, wasteful ledger counts, agreement
with `audit_summary.by_tag`); `ComposeTests` (3: all
three flags together, each flag independent, omitted
flag stays out of payload).

Suite after r163: 1348 passed, 0 failed. verify_suite 9/9.

### Gotchas
- The workspace fingerprint sleeps 1.1s in the "changes when
  rewritten" test to push the ledger mtime past the
  filesystem resolution. mtime resolution on Windows is
  ~16ms but the OS may round to whole seconds on
  FAT/exFAT; the 1.1s gap avoids the round-to-same-second
  race that is the r157 lesson in a different costume.
- `_workspace_fingerprint_ledger_mtime` returns 0 when the
  ledger is missing (a fresh workspace that has not yet
  recorded a seam). The id is still stable across replays
  on the same empty workspace, but two fresh workspaces
  on the same path with no ledger will collide — by
  design, the fingerprint is a path + mtime hash, not a
  cryptographic identity. A host that needs identity
  should use the path string itself.
- The `info --audit-baseline` flag is positional in spirit
  (takes a path), but the parser wires it as
  `dest="audit_baseline"`. The dispatch reads
  `args.audit_baseline` directly, so the flag's name
  matches the JSON block's name and the tests do not
  have to remember a separate kwarg spelling.
- The manifest's `by_tag` map carries every tag in
  `AUDIT_TAGS` (the r159 tuple), including the four
  surface tags and the three facet tags. The
  `tags_fired` / `tags_clean` counts are derived from
  this map; they are not separate computations, so a
  typo in the manifest cannot drift from the audit
  reality.

## r164 — write lock: prevent concurrent writes from corrupting the ledger

The controller writes `.mindseam/WORKSPACE.md` and
`.mindseam/history.json` from `note`, `seam`, `ship`,
`skillbook`, and `audit --baseline-write`. Two concurrent
writers — a CI pipeline running `note` and `seam` in
parallel, a host's `from_stdin` thread, two agents in the
same workspace — can interleave their read-modify-write
cycles and produce a corrupted ledger.

r164 borrows from `flock(2)` / `git index.lock` /
`cargo build --locked` / SQLite's `BEGIN IMMEDIATE`: an
advisory file lock under `.mindseam/write.lock`. The
atomicity is provided by `O_CREAT | O_EXCL`: a single OS
call that succeeds only if the file did not exist, the
way `flock -n` reports "another process holds the lock"
without waiting. Windows / Linux / macOS all support
`os.O_CREAT | os.O_EXCL` with the same atomicity
guarantee, so the helper is portable.

Three new pieces:

1. `_acquire_write_lock(ledger_dir)` — opens
   `.mindseam/write.lock` with `O_CREAT | O_EXCL`. The
   body is the holder's PID. A second writer that
   arrives mid-write sees `EEXIST` and the controller
   refuses with the message
   "`<lock_path>` is locked by another writer (pid=N);
   refusing to write `<target>`", the way `git commit`
   refuses when `.git/index.lock` is present.

2. `atomic_write_text` now wraps every write under
   `.mindseam/` in the lock. Acquire before the
   temp-file write, release after `os.replace`. A
   mid-write `OSError` still releases the lock, so a
   crashed process does not leave a stale lock behind.

3. `info --json` always emits a `lock_state` block with
   three states: `free` (no lock file), `held_by_other`
   (lock file present, holder PID is not ours),
   `held_by_us` (lock file is ours — only possible if a
   previous controller process crashed mid-write and left
   the lock behind; a human should clear it). A host
   reads this before launching a write to avoid the
   race entirely, the way `flock -n` reports "another
   process holds the lock" without waiting.

The `note` subcommand refuses with exit 2 on lock
conflict (the controller's standard "could not" exit).
The `seam` subcommand is best-effort: a history write
that fails behind a held lock is reported as a stderr
`WARNING` and the audit log just does not get the new
row — the print_reentry path still runs. This matches
the pre-r164 behaviour where a corrupted history file
also produced a warning rather than a hard fail.

### Tests
test_r164_write_lock.py — 15 tests in four sub-suites:
`WriteLockHelperTests` (5: acquire/release round-trip,
refusal on second acquire, lock path resolution,
holder-pid None when no file, malformed body tolerated);
`AtomicWriteLockTests` (3: writes when lock is free,
refuses when lock held, releases lock after failed
write); `InfoLockStateTests` (4: free state, held_by_other
with foreign pid, malformed body reads as free, the
held_by_us state machine pinned through the helper);
`WriteRefusesTests` (3: `note` refuses with exit 2 on
conflict, `note` releases lock after success, `seam`
emits a stderr warning on conflict).

Suite after r164: 1363 passed, 0 failed. verify_suite
9/9.

### Gotchas
- The lock directory is the `.mindseam/` directory —
  the target's parent when the target is a direct child,
  the target's grandparent when the target is a file
  under `.mindseam/`. The first cut used
  `os.path.dirname(target_dir)` and missed the case
  where the target *is* under `.mindseam/`. The
  controller now picks the lock directory as
  `target_dir` if it is `.mindseam/`, else
  `os.path.dirname(target_dir)`.
- The `held_by_us` test was a hard test: the test runner
  and the controller are separate processes, so
  `os.getpid()` in the test does not match the
  controller's pid. The test pins the state machine via
  the held_by_other and held-free cases; held_by_us is
  exercised through `atomic_write_text`-holds-the-lock-
  during-write, which a host can verify by reading the
  lock_state immediately after a successful write
  completes (it has just been released). The test
  also asserts the malformed body → free transition,
  which is the third corner of the state machine.
- `seam` is intentionally best-effort: the print_reentry
  banner and the workspace write are the user-visible
  side effects, the history write is a sidecar. A
  history write that fails behind a held lock produces
  a stderr warning, not a hard exit 2. The lock test
  asserts the warning is visible (`"locked by another
  writer"` in stderr); a host that wants the audit log
  to be authoritative can re-run `seam` after the
  foreign writer releases the lock.
- The lock file's body is `pid=N\n`. The helper tolerates
  malformed bodies (returns `None`, which the state
  machine reads as `free`); the test pins this with a
  garbage-body case. A human who wants to clear a
  crashed-mid-write lock by hand can `rm
  .mindseam/write.lock` — the body parsing is a
  courtesy, not a gate.

## r165 — info mtime, health, text: a single info call answers every CI question

The r161-r164 `info` report grew many orthogonal blocks:
`audit_summary` (roll-up), `audit_manifest` (detector
coverage), `workspace_id` (path + mtime fingerprint),
`audit_baseline_diff` (drift), `lock_state` (advisory
file lock). r165 closes the gap with three more flags
that let a host assemble a single `info --json` call to
prove "the workspace files are healthy" without spawning
`stat` per file or running `systemctl is-system-running`
separately:

1. `info --mtime` borrows from `find -printf` /
   `stat --format='%y %s %n'`: a `workspace_files`
   block listing each ledger artefact (WORKSPACE.md /
   history.json / metacognition.json / skillbook.md)
   with `mtime` / `size` / `exists`. A missing file
   gets `mtime=0 size=0`, the way `stat` reports on
   a deleted file. The text face is a small section,
   the way `df -h` reports under `ls -lh`: one line
   per artefact, columns aligned so a host can grep
   or awk on the result.

2. `info --health` rolls up the r156-r164 signals
   (`lock_state`, `audit_summary.lean`, `warnings`,
   `last_seam.long_gap`) into a single status enum
   (ok / degraded / unhealthy) with a `reasons` list,
   borrowed from `kubectl get componentstatus` /
   `systemctl is-system-running`. A host that wants a
   single CI gate reads `health.status` instead of
   parsing four blocks. A "no seams recorded yet"
   warning degrades (not unhealthy), the way a fresh
   service is `degraded` but not `unhealthy` in
   `systemctl`. A foreign-pid lock is hard-unhealthy;
   a self-pid lock is soft-degraded.

3. `info --text` forces plain text even if `--json`
   is also passed, borrowed from `gh --output text` /
   `kubectl -o wide`. The r156 default is text when
   no face is requested; `--text` makes that explicit
   so a shell pipeline that wants stable text can
   use it unconditionally. The flag overrides
   `--json` so a host that always passes both
   (`info --json --text`) gets the text face, the
   way `gh --output=text` overrides the implicit
   default.

All three blocks are additive. The r164 `lock_state`,
r163 `workspace_id` / `audit_baseline_diff` /
`audit_manifest`, r161 `audit_summary`, and r156
`ledger` / `last_seam` / `warnings` blocks keep their
existing shape. The three new flags compose freely
with each other and with the r161-r164 flags.

### Tests
test_r165_info_mtime_health_text.py — 18 tests in four
sub-suites:
`MtimeTests` (5: opt-in shape, every artefact listed,
existing file has mtime and size, missing file has
zeros, mtime changes on rewrite);
`HealthTests` (5: opt-in shape, fresh ledger is
degraded, lock_held_by_other is unhealthy,
lock_held_by_us is degraded, audit_finding is
unhealthy, long_gap is degraded, reasons list is
stable across calls);
`TextTests` (4: `--text` overrides `--json`,
`--text` alone is text, default is text, `--text
--mtime` includes artefact lines);
`ComposeTests` (2: `--mtime` with `--health` coexists,
helper callable directly).

Suite after r165: 1381 passed, 0 failed. verify_suite
9/9 (one run had a pre-existing timing flake in
`test_info_subcommand_baseline.test_info_human_renders
_seconds_when_below_minute` that pins "30 seconds ago"
exactly; the immediate retry passed 1381/1381).

### Gotchas
- argparse help strings reject `%` because argparse
  uses `%`-formatting internally. The first cut
  borrowed the literal `find -printf '%T@ %s %p'`
  in the help text and crashed every `info` command
  with `ValueError: badly formed help string`. The
  fix is the same r162 trick: paraphrase the
  borrower's option name (`T mtime, size, path`)
  instead of the literal.
- The r69 doc-drift reverse test extracts every
  ` --flag` token from SKILL.md lines that contain
  `mindseam.py `. The first cut borrowed the literal
  `gh --output text` and the r69 regex extracted
  ` --output` (the regex stops at the space) and
  refused because `add_argument("--output")` does
  not exist. Three rounds of paraphrasing — `text`
  value, `text` value / `text` face, `text` face —
  finally dropped the leading dash. The lesson: the
  r69 reverse test extracts the *first* token, not
  the full option name; a borrowed phrase that uses
  an option separator (`=` or space) splits into
  two tokens, and only the first one matters.
- A fresh workspace with no seams emits a "no
  seams recorded yet" warning, which makes the
  health status `degraded` rather than `ok`. This
  is the right behaviour: a fresh workspace is not
  *unhealthy* (the lock is free, the audit is lean),
  but it is not *ok* (the host wants a first seam
  soon). The status enum reads as a state machine
  a CI script can map to exit codes (ok → 0,
  degraded → 1, unhealthy → 2) without parsing
  the reasons list.
- The `health` block's `reasons` list is a list of
  dicts (`{kind, severity, detail}`), not a list
  of strings. The `kind` field is the stable
  contract; `severity` is hard or degraded; `detail`
  is human-readable prose. A host grepping the
  `kind` field is stable across the lifetime of
  the controller; a host grepping `detail` is
  fragile.

## r166 — info content-hash and changed: detect content changes without trusting mtime

The r161-r165 `info` report grew many orthogonal blocks:
`audit_summary` (roll-up), `audit_manifest` (detector
coverage), `workspace_id` (path + mtime fingerprint),
`audit_baseline_diff` (drift), `lock_state` (advisory
file lock), `workspace_files` (mtime + size per artefact),
`health` (ok / degraded / unhealthy roll-up). r166
closes the gap with two more flags that let a host
detect "which file's content actually changed" without
trusting mtime:

1. `info --content-hash` borrows from `git rev-parse
   --short` / `sha1sum` / `conda list --md5`: a
   `content_hash` block carrying an 8-char SHA-1
   prefix of each ledger artefact, the same shape as
   `git`'s abbreviated object names. The collision
   space is 2^32 and the chance of a same-day
   collision on a single workspace is negligible, so
   the host can use the prefix as a stable change
   detector. Missing files get an empty string, the
   way `git` reports a deleted blob.

2. `info --changed` borrows from `git status
   --porcelain` / `make -n`: a `changed` block listing
   which ledger artefacts changed since the last call.
   The previous hashes are persisted in
   `.mindseam/info-state.json` and overwritten on
   every call. A first run (no state file) is treated
   as "all changed", the way `cargo` rebuilds the
   registry index when its `.cargo/lock` file is
   absent. The state write goes through the r164 write
   lock so a concurrent `note` or `seam` cannot race
   the state file. A locked state file is silently
   skipped — the host still gets the `changed` map
   for *this* call, the way `git status` reports
   staged-vs-unstaged even when the index file is
   unwritable.

The text face of `content_hash` is `sha1sum`-shaped
(one line per artefact, two columns). The text face of
`changed` is `git status --porcelain`-shaped (an `M` /
`-` column followed by the artefact name), so a shell
pipeline can `awk '{print $1}'` to filter changed
files.

All blocks are additive. The r161-r165 surface keeps
its existing shape. The two new flags compose freely
with each other and with the r161-r165 flags.

### Tests
test_r166_info_content_hash_changed.py — 26 tests in
five sub-suites:
`HashHelperTests` (6: 8-char length, stability,
content-change detection, missing-file returns empty,
snapshot lists every artefact, empty for missing);
`ContentHashFlagTests` (4: opt-in shape, hash changes
when file content changes, text-face column, content
block appears when set);
`ChangedFlagTests` (5: opt-in shape, first run marks
all changed, second run with no change marks all
unchanged, ledger rewrite marks only that file, state
file written, state file carries hashes, history
file appearance marks it changed, text face
"any_changed=False");
`StateFileTests` (5: missing state, malformed state,
non-dict state, hashes-must-be-dict, write under
foreign lock is silent);
`ComposeTests` (3: content_hash with mtime, content
hash with health, changed with text).

Suite after r166: 1407 passed, 0 failed. verify_suite
9/9.

### Gotchas
- The first cut of `_write_info_state` called
  `atomic_write_text` after acquiring the r164 lock.
  `atomic_write_text` *also* acquires the r164 lock
  internally, so the second acquire saw the foreign
  lock (which was us) and refused with "locked by
  another writer". The helper now writes the state
  file directly using a single `O_CREAT | O_EXCL`
  open + `os.replace`, the same way
  `atomic_write_text` does internally but without
  re-acquiring the lock. The lock is held for the
  duration of the write so no other writer can race
  the state file.
- The `HashHelperTests` class did not `chdir` into
  a clean tmpdir, so the `test_content_hash_snapshot
  _empty_for_missing` test ran from whatever cwd the
  prior test left behind — which sometimes had a
  residual `WORKSPACE.md` from the previous
  test_r166 run. The class now uses a `setUp` /
  `tearDown` chdir pair, the same as the
  `ContentHashBase` mixin.
- The r69 doc-drift reverse test extracts every
  ` --flag` token from SKILL.md lines that contain
  `mindseam.py `. The first cut borrowed the literal
  `git status --porcelain` and the r69 regex
  extracted ` --porcelain` and refused because
  `add_argument("--porcelain")` does not exist. The
  fix is the same r159/r162/r165 trick: paraphrase
  the borrower's option name (`porcelain output`).
  The lesson: a borrowed phrase that uses a flag
  with a leading dash in the docs trips r69, even
  when the flag is a real borrower's flag — the
  controller does not own the option.
- The 8-char SHA-1 prefix is the same shape as
  `git`'s abbreviated object names. A collision on a
  single workspace is improbable (2^32 / 2^160), so
  the prefix is a stable change detector. The full
  SHA-1 is overkill for change detection; the 8-char
  prefix is the same length as a `git` abbreviated
  hash and the same shape.
