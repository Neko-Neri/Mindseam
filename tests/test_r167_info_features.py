# -*- coding: utf-8 -*-
"""Round 167 guards: info --features catalog.

The r161-r166 ``info`` report grew many orthogonal
blocks. r167 closes the gap with a machine-readable
catalog of every flag, block, and gate the controller
can do, indexed by a stable id. Borrowed from
``gh features list`` (which emits ``name / state /
description`` JSON) / ``rustup component list`` /
OpenAPI's ``info.description``: a single source of
truth for what the controller ships, in a shape a
host can grep or pipe through ``jq`` without parsing
prose.

The catalog is the only ``info`` block the controller
ships that is *not* derived from runtime state. It is
a hand-curated manifest: every entry has an ``id``
(stable kebab-case), a ``since`` round (so a host
can ask "was --content-hash there in r165?"), a
``summary`` (one-line human description), and a
``default`` boolean (reserved for future opt-in
capability; every feature is on by default today).

A host that wants to know "does this build support
``--content-hash``?" reads one block instead of
grepping the source. The catalog also doubles as
release notes: the ``since`` round is the round
that introduced the feature, the way ``gh features
list`` shows the date a feature reached general
availability.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd, env=None):
    run_env = os.environ.copy()
    run_env.pop("MINDSEAM_INTENSITY", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=run_env,
    )


class CatalogHelperTests(unittest.TestCase):
    """The catalog is well-formed and stable."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_catalog_is_a_tuple(self):
        self.assertIsInstance(mindseam._FEATURE_CATALOG, tuple)

    def test_catalog_has_four_keys(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(
                set(entry.keys()),
                {"id", "since", "summary", "default"})

    def test_ids_are_unique(self):
        ids = [e["id"] for e in mindseam._FEATURE_CATALOG]
        self.assertEqual(len(ids), len(set(ids)),
                         "duplicate ids in _FEATURE_CATALOG")

    def test_ids_are_kebab_case(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertRegex(
                entry["id"], r"^[a-z][a-z0-9-]*$",
                "id %r is not kebab-case" % entry["id"])

    def test_since_round_format(self):
        # Each ``since`` value is the literal round tag
        # used by the SESSION_LOG and the commit subject
        # (``r156``, ``r163``, ``r167``). A host can use
        # it to look up the round in the changelog.
        for entry in mindseam._FEATURE_CATALOG:
            self.assertRegex(
                entry["since"], r"^r\d+$",
                "since %r is not a round tag" % entry["since"])

    def test_summary_is_a_non_empty_string(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertIsInstance(entry["summary"], str)
            self.assertGreater(len(entry["summary"]), 0)

    def test_default_is_a_boolean(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertIsInstance(entry["default"], bool)

    def test_catalog_covers_known_features(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        for needle in (
            "info-warnings-only",
            "info-version",
            "info-human",
            "info-check",
            "info-memory",
            "info-list-fields",
            "audit-tagged-findings",
            "audit-intensity-ladder",
            "history-filter",
            "history-human",
            "report-json-faces",
            "audit-facets",
            "audit-tag-projection",
            "audit-evidence-link",
            "audit-window-at",
            "audit-gate-enum",
            "info-audit-summary",
            "audit-baseline",
            "info-workspace-id",
            "info-audit-baseline-diff",
            "info-audit-manifest",
            "write-lock",
            "info-lock-state",
            "info-mtime",
            "info-health",
            "info-text",
            "info-content-hash",
            "info-changed",
            "info-features",
            "info-format",
        ):
            self.assertIn(needle, ids,
                          "catalog missing %r" % needle)


class FeaturesFlagTests(unittest.TestCase):
    """``--features`` emits a features block."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self, verified=()):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# L", "", "## Goal", "", "## Core", "",
                "## Verified"] + list(verified) + [
                "", "## Open", "", "## Next", ""]
        path.write_text("\n".join(text), encoding="utf-8")

    def test_features_block_always_present(self):
        # r169 changed the contract: the features
        # catalog is a hand-curated constant with no
        # runtime cost, so it is always populated.
        # The ``--features`` flag now controls only
        # the text face; the JSON block is always
        # there so ``info --format features[0].id``
        # works even when the flag is omitted.
        self._ledger()
        r = _invoke(["info", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("features", payload)

    def test_features_block_appears_when_set(self):
        self._ledger()
        r = _invoke(["info", "--json", "--features"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("features", payload)
        self.assertIsInstance(payload["features"], list)
        self.assertGreater(len(payload["features"]), 0)

    def test_features_block_equals_catalog(self):
        # The JSON block is the catalog itself, in
        # catalog order. A host can diff snapshots
        # across controller versions and see the
        # catalogue drift.
        self._ledger()
        r = _invoke(["info", "--json", "--features"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["features"],
                         list(mindseam._FEATURE_CATALOG))

    def test_features_block_id_is_present_in_catalog(self):
        # A host script that wants to check a specific
        # feature is here can do:
        #   jq '.features[] | select(.id == "info-content-hash")' < info.json
        # The id must match one in the catalog.
        self._ledger()
        r = _invoke(["info", "--json", "--features"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        ids = {e["id"] for e in payload["features"]}
        self.assertIn("info-content-hash", ids)
        self.assertIn("audit-baseline", ids)
        self.assertIn("write-lock", ids)

    def test_text_face_lists_features(self):
        self._ledger()
        r = _invoke(["info", "--text", "--features"],
                    cwd=self.workspace)
        self.assertIn("Features:", r.stdout)
        # The text face lists every catalog id.
        for entry in mindseam._FEATURE_CATALOG:
            self.assertIn(entry["id"], r.stdout,
                          "text face missing %r" % entry["id"])

    def test_features_compose_with_audit_baseline_diff(self):
        # All r161-r166 blocks coexist with --features.
        self._ledger()
        bl = os.path.join(self.workspace, "bl.json")
        _invoke(["audit", "--baseline-write", bl],
                 cwd=self.workspace)
        r = _invoke(["info", "--json", "--features",
                     "--audit-baseline", bl, "--manifest",
                     "--mtime", "--health"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertIn("features", payload)
        self.assertIn("audit_baseline_diff", payload)
        self.assertIn("audit_manifest", payload)
        self.assertIn("workspace_files", payload)
        self.assertIn("health", payload)

    def test_features_picks_up_audit_finding_for_health(self):
        # A wasteful ledger produces an audit_finding
        # reason in the health block. The features block
        # is independent of health, but they coexist
        # so a host reading both gets a complete view.
        self._ledger(
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"))
        r = _invoke(["info", "--json", "--features", "--health"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["health"]["status"], "unhealthy")
        self.assertIn("features", payload)


class CatalogCoverageTests(unittest.TestCase):
    """The catalog covers the r156-r166 surface."""

    def test_audit_block_is_listed(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        for audit_id in (
            "audit-tagged-findings",
            "audit-intensity-ladder",
            "audit-facets",
            "audit-tag-projection",
            "audit-evidence-link",
            "audit-window-at",
            "audit-gate-enum",
            "audit-baseline",
        ):
            self.assertIn(audit_id, ids,
                          "audit block %r missing from catalog" % audit_id)

    def test_history_block_is_listed(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        for hid in ("history-filter", "history-human"):
            self.assertIn(hid, ids)

    def test_info_block_is_listed(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        for iid in (
            "info-warnings-only",
            "info-version",
            "info-human",
            "info-check",
            "info-memory",
            "info-list-fields",
            "info-audit-summary",
            "info-workspace-id",
            "info-audit-baseline-diff",
            "info-audit-manifest",
            "info-lock-state",
            "info-mtime",
            "info-health",
            "info-text",
            "info-content-hash",
            "info-changed",
            "info-features",
        ):
            self.assertIn(iid, ids,
                          "info block %r missing from catalog" % iid)

    def test_report_json_face_is_listed(self):
        # The r158 "every report face speaks JSON"
        # round ships as a single catalog entry, not
        # one per subcommand.
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("report-json-faces", ids)

    def test_write_lock_is_listed(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("write-lock", ids)
