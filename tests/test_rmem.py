#!/usr/bin/env python3
"""Test suite for rmem.

Stdlib only, matching the tool itself -- no pytest, no fixtures library.

Run from the repo root:

    python3 run_tests.py
    python3 -m unittest discover -s tests -v

Each test builds a throwaway git repo in a temp directory. Every assertion is made
against real process output and real exit codes, because most of the bugs this suite
exists to prevent were invisible from the inside: a check that passed when it should
have failed, or a heading that kept asserting a condition its own commit had removed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "rmem"

BASE_FILES = {
    "src/billing/charge.py": "def charge():\n    return 1\n",
    "src/billing/gateway.py": "def gateway():\n    return 2\n",
    "src/api/handlers/users.py": "def users():\n    return []\n",
    ".github/CODEOWNERS": "*            @default-owner\n/src/billing/**  @payments-team\n",
}


class Fixture:
    """A throwaway git repo with rmem running against it."""

    def __init__(self, files=None):
        self.dir = Path(tempfile.mkdtemp(prefix="rmem-test-"))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        for name, content in (files or BASE_FILES).items():
            self.write(name, content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init", "--allow-empty")

    # ---------------------------------------------------------------- plumbing

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir,
                              capture_output=True, text=True)

    def write(self, name, content):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def read(self, name):
        return (self.dir / name).read_text()

    def commit(self, message="change"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def rmem(self, *args, cwd=None):
        r = subprocess.run([sys.executable, str(TOOL), *args],
                           cwd=(self.dir / cwd) if cwd else self.dir,
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    # ------------------------------------------------------------------- verbs

    def init(self):
        code, out = self.rmem("init")
        assert code == 0, "rmem init failed:\n" + out
        return out

    def add(self, *args):
        """Returns the new memory id (asserting the write succeeded)."""
        code, out = self.rmem("add", *args)
        m = re.search(r"added (\S+) \(", out)
        assert code == 0 and m, "rmem add failed:\n" + out
        return m.group(1)

    def health(self):
        """Parse `check --brief` into a dict. Never raises on BROKEN."""
        code, out = self.rmem("check", "--brief")
        first = out.strip().splitlines()[0]
        m = re.match(r"MEMORY-HEALTH: (\d+)/(\d+) (GREEN|BROKEN)(?: -- (.*))?$", first)
        assert m, "unparseable health line: %r" % first
        return {
            "code": code,
            "passed": int(m.group(1)),
            "total": int(m.group(2)),
            "green": m.group(3) == "GREEN",
            "failed": [s.strip() for s in (m.group(4) or "").split(",") if s.strip()],
            "brief": first,
            "out": out,
        }

    def check_full(self):
        return self.rmem("check")

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Base(unittest.TestCase):
    files = BASE_FILES
    seed_convention = True

    def setUp(self):
        self.f = Fixture(self.files)
        self.f.init()
        self.conv = None
        if self.seed_convention:
            self.conv = self.f.add(
                "--type", "convention", "--title", "Billing goes through the gateway",
                "--body", "Never import the provider outside gateway.py.",
                "--anchor", "src/billing/**", "--author", "test")
        self.f.commit("seed memory")

    def tearDown(self):
        self.f.cleanup()

    def assertGreen(self, h=None):
        h = h or self.f.health()
        self.assertTrue(h["green"], "expected GREEN, got %s\n%s" % (h["brief"], h["out"]))
        self.assertEqual(h["code"], 0)

    def assertFails(self, check, h=None):
        h = h or self.f.health()
        self.assertIn(check, h["failed"],
                      "expected %s to fail; failing were %s" % (check, h["failed"]))
        self.assertEqual(h["code"], 1, "a broken gate must exit 1")


# --------------------------------------------------------------- the happy path

class TestBaseline(Base):
    def test_fresh_repo_is_green(self):
        h = self.f.health()
        self.assertEqual(h["total"], 14)
        self.assertGreen(h)

    def test_unstamped_repo_fails_index_checks(self):
        f = Fixture(BASE_FILES)
        try:
            code, out = f.rmem("check", "--brief")
            self.assertEqual(code, 1)
            self.assertIn("no .memory/", out)
        finally:
            f.cleanup()


# ------------------------------------------------------- fail-closed behaviour

class TestFailClosed(Base):
    """A memory system that can fail open is worse than none."""

    def test_missing_fingerprint_is_an_error_not_a_pass(self):
        text = self.f.read(".memory/conventions.md")
        text = re.sub(r"(?m)^anchor_hash:.*\n", "", text)
        self.f.write(".memory/conventions.md", text)
        self.f.rmem("index")
        self.assertFails("anchors-stamped")

    def test_index_stale_when_markdown_edited_without_rebuild(self):
        self.f.write(".memory/conventions.md",
                     self.f.read(".memory/conventions.md") + "\n<!-- edited -->\n")
        self.assertFails("index-fresh")

    def test_state_is_decided_by_content_not_commit_sha(self):
        """Squash-merge and rebase rewrite history. Drift must survive that.

        Point verified_at at a commit that does not exist, then change the anchored
        code: a history-based check would go quiet here. Content-based must still fail.
        """
        text = self.f.read(".memory/conventions.md")
        text = re.sub(r"(?m)^verified_at:.*$", "verified_at: 0000000", text)
        self.f.write(".memory/conventions.md", text)
        self.f.rmem("index")
        self.assertGreen()

        self.f.write("src/billing/charge.py", "def charge():\n    return 99\n")
        self.f.rmem("index")
        self.assertFails("anchors-not-stale")


# ------------------------------------------------------------ anchors resolve

class TestAnchorsResolve(Base):
    def test_anchor_to_vanished_code_fails(self):
        self.f.add("--type", "decision", "--title", "Users API shape",
                   "--anchor", "src/api/**", "--author", "test")
        (self.f.dir / "src/api/handlers/users.py").unlink()
        self.f.rmem("index")
        self.assertFails("anchors-resolve")

    def test_empty_leftover_directory_does_not_satisfy_an_anchor(self):
        """The false negative: a deleted file leaves its directory behind, and an
        earlier version happily reported 'the code still exists' about nothing."""
        self.f.add("--type", "decision", "--title", "Users API shape",
                   "--anchor", "src/api/**", "--author", "test")
        (self.f.dir / "src/api/handlers/users.py").unlink()
        self.assertTrue((self.f.dir / "src/api/handlers").is_dir(), "fixture assumption")
        self.f.rmem("index")
        self.assertFails("anchors-resolve")

    def test_live_anchors_are_not_flagged(self):
        """The over-correction: a naive '**' expansion flagged live anchors as dead."""
        self.assertGreen()

    def test_broad_scope_can_be_narrowed(self):
        wide = self.f.add("--type", "convention", "--title", "Anything anywhere",
                          "--anchor", "**", "--author", "test")
        self.f.commit("wide")
        # a change anywhere now marks the broad memory stale
        self.f.write("src/api/handlers/users.py", "def users():\n    return [1]\n")
        self.f.rmem("index")
        self.assertFails("anchors-not-stale")

        code, out = self.f.rmem("verify", wide, "--anchor", "src/api/**")
        self.assertEqual(code, 0, out)
        self.f.rmem("index")
        self.assertNotIn("anchors-not-stale", self.f.health()["failed"])


# ------------------------------------------------------- formatting vs real change

class TestNormalization(Base):
    """The stripped view may only ever downgrade a detection. It must never excuse one."""

    def test_reformatting_is_a_notice_not_a_failure(self):
        self.f.write("src/billing/charge.py",
                     "# a reformatting pass\n\n\ndef charge():\n    return 1\n")
        h = self.f.health()
        self.assertGreen(h)

        code, out = self.f.check_full()
        self.assertEqual(code, 0, out)
        self.assertIn("reformatted", out.lower())

    def test_a_real_change_to_the_same_file_still_fails(self):
        self.f.write("src/billing/charge.py",
                     "def charge():\n    return 1\n\n\ndef new_thing():\n    return 42\n")
        self.assertFails("anchors-not-stale")


# ------------------------------------------------------------- supersession

class TestSupersede(Base):
    def test_supersede_marks_the_entry_not_the_file_header(self):
        """The original bug: supersede patched the file header, so the old memory was
        never retired and health could never go green again."""
        old = self.f.add("--type", "decision", "--title", "Billing goes through the gateway",
                         "--anchor", "src/billing/**", "--author", "test")
        new = self.f.add("--type", "decision", "--title", "Billing goes through the ledger",
                         "--anchor", "src/billing/**", "--author", "test")
        self.f.commit("two decisions")

        code, out = self.f.rmem("supersede", old, new)
        self.assertEqual(code, 0, out)
        self.f.rmem("index")

        text = self.f.read(".memory/decisions.md")
        self.assertIn("(superseded)", text)
        self.assertIn("## Billing goes through the gateway (superseded)", text)
        # the file header is not a memory and must not be rewritten
        self.assertTrue(text.startswith("# Decisions"), text[:40])
        self.assertNotIn("# Decisions (superseded)", text)
        self.assertGreen()

    def test_supersession_pointing_at_a_missing_id_fails(self):
        self.f.add("--type", "decision", "--title", "Replaced thing",
                   "--anchor", "src/billing/**", "--author", "test",
                   "--supersedes", "DEC-1970-01-01-dead")
        self.assertFails("supersedes-resolve")


# ------------------------------------------------------------- dead ends

class TestDeadEnds(Base):
    def test_dead_end_without_evidence_fails(self):
        self.f.add("--type", "dead-end", "--title", "Redis queue did not work",
                   "--body", "It dropped messages under load.",
                   "--anchor", "src/billing/**", "--author", "test")
        self.assertFails("dead-ends-evidenced")

    def test_dead_end_riding_the_change_that_settled_it_fails(self):
        """The accuracy gate. This is the observed failure: an agent fixes a problem
        and records the problem as though it were still live."""
        self.f.write("src/billing/charge.py", "def charge():\n    return 77\n")
        self.f.add("--type", "dead-end",
                   "--title", "The refund window rejects credit notes too",
                   "--body", "credit_note ran the same window check as refund.",
                   "--anchor", "src/billing/**",
                   "--evidence", "ProviderError(409, 'beyond the 90 day refund window')",
                   "--author", "test")
        self.assertFails("dead-ends-settled")

    def test_resolved_by_clears_it(self):
        self.f.write("src/billing/charge.py", "def charge():\n    return 77\n")
        mem = self.f.add("--type", "dead-end",
                         "--title", "The refund window rejects credit notes too",
                         "--body", "credit_note ran the same window check as refund.",
                         "--anchor", "src/billing/**",
                         "--evidence", "ProviderError(409, 'beyond the refund window')",
                         "--resolved-by", "this change un-windowed credit_note",
                         "--author", "test")
        self.f.rmem("index")
        self.assertNotIn("dead-ends-settled", self.f.health()["failed"])

        # and the heading itself carries the fact, because agents read the markdown
        self.assertIn("## The refund window rejects credit notes too (settled)",
                      self.f.read(".memory/dead-ends.md"))

    def test_settled_marker_is_idempotent(self):
        self.f.write("src/billing/charge.py", "def charge():\n    return 77\n")
        mem = self.f.add("--type", "dead-end", "--title", "Same wall twice",
                         "--anchor", "src/billing/**", "--evidence", "boom",
                         "--author", "test")
        self.f.rmem("index")
        self.f.rmem("verify", mem, "--resolved-by", "first")
        self.f.rmem("verify", mem, "--resolved-by", "second")
        text = self.f.read(".memory/dead-ends.md")
        self.assertEqual(text.count("(settled)"), 1, text)
        self.assertNotIn("(settled) (settled)", text)

    def test_silent_when_the_memory_is_not_part_of_this_change(self):
        """A long-lived dead end must not be dragged into unrelated work."""
        self.f.write("src/billing/charge.py", "def charge():\n    return 77\n")
        self.f.add("--type", "dead-end", "--title", "Redis queue did not work",
                   "--anchor", "src/billing/**", "--evidence", "dropped under load",
                   "--author", "test")
        self.f.commit("recorded the dead end")
        self.f.rmem("index")

        self.f.write("src/billing/charge.py", "def charge():\n    return 78\n")
        self.f.rmem("index")
        h = self.f.health()
        self.assertFails("anchors-not-stale", h)
        self.assertNotIn("dead-ends-settled", h["failed"])


# ------------------------------------------------------------------- hazards

class TestHazards(Base):
    """A hazard is a pointer to a control, never the control."""

    def test_hazard_without_enforcement_is_a_wish(self):
        self.f.add("--type", "hazard", "--title", "Do not touch billing",
                   "--body", "Frozen.", "--anchor", "src/billing/**",
                   "--owner", "@payments-team", "--author", "test")
        self.assertFails("hazards-enforced")

    def test_hazard_without_owner_fails(self):
        self.f.add("--type", "hazard", "--title", "Do not touch billing",
                   "--body", "Frozen.", "--anchor", "src/billing/**",
                   "--enforcement", "branch protection", "--author", "test")
        self.assertFails("hazards-enforced")

    def test_hazard_naming_a_control_we_cannot_verify_passes(self):
        """Honest limit: branch protection is real but unreadable from the repo. We do
        not pretend to verify what we cannot see."""
        self.f.add("--type", "hazard", "--title", "Release tags are protected",
                   "--body", "Only the release bot may tag.",
                   "--anchor", "src/billing/**", "--owner", "@release",
                   "--enforcement", "branch protection on main", "--author", "test")
        self.assertGreen()

    def test_codeowners_claim_is_verified_against_the_file(self):
        self.f.add("--type", "hazard", "--title", "Auth internals are frozen",
                   "--body", "Security review required.", "--anchor", "src/api/**",
                   "--owner", "@security-team",
                   "--enforcement", "CODEOWNERS", "--author", "test")
        self.assertFails("hazards-enforced")
        # --brief names the failing check but not the reason; the reason is the point
        code, out = self.f.check_full()
        self.assertEqual(code, 1)
        self.assertIn("CODEOWNERS", out)

    def test_a_catch_all_rule_is_not_proof_of_ownership(self):
        """`* @someone` nominally covers every path. Path coverage alone therefore
        proves nothing -- the claimed owner must be the one actually assigned."""
        self.f.add("--type", "hazard", "--title", "Auth internals are frozen",
                   "--body", "Security review required.", "--anchor", "src/api/**",
                   "--owner", "@security-team",
                   "--enforcement", "CODEOWNERS", "--author", "test")
        code, out = self.f.check_full()
        self.assertEqual(code, 1)
        self.assertIn("@default-owner", out, "should name the actual assigned owner")

    def test_the_fix_is_to_create_the_control(self):
        self.f.add("--type", "hazard", "--title", "Auth internals are frozen",
                   "--body", "Security review required.", "--anchor", "src/api/**",
                   "--owner", "@security-team", "--enforcement", "CODEOWNERS",
                   "--author", "test")
        self.assertFails("hazards-enforced")

        self.f.write(".github/CODEOWNERS",
                     self.f.read(".github/CODEOWNERS") + "/src/api/**  @security-team\n")
        self.f.rmem("index")
        self.assertGreen()

    def test_hazard_passes_when_owner_and_rule_agree(self):
        self.f.add("--type", "hazard", "--title", "Billing ledger is frozen",
                   "--body", "Audit pending.", "--anchor", "src/billing/**",
                   "--owner", "@payments-team", "--enforcement", "CODEOWNERS",
                   "--author", "test")
        self.assertGreen()


# ------------------------------------------------------------------- compile

class TestCompile(Base):
    def test_compile_is_idempotent(self):
        code, out = self.f.rmem("compile")
        self.assertEqual(code, 0, out)
        first = self.f.read("AGENTS.md")
        self.f.rmem("compile")
        self.assertEqual(first, self.f.read("AGENTS.md"))

    def test_conventions_land_in_agents_md(self):
        self.f.rmem("compile")
        text = self.f.read("AGENTS.md")
        self.assertIn("## House rules", text)
        self.assertIn("Billing goes through the gateway", text)
        self.assertIn("<!-- rmem:begin", text)
        self.assertIn("<!-- rmem:end -->", text)

    def test_hazards_compile_as_frozen_areas_naming_the_control(self):
        self.f.add("--type", "hazard", "--title", "Billing ledger is frozen",
                   "--body", "Audit pending.", "--anchor", "src/billing/**",
                   "--owner", "@payments-team", "--enforcement", "CODEOWNERS",
                   "--author", "test")
        self.f.rmem("compile")
        text = self.f.read("AGENTS.md")
        self.assertIn("### Frozen areas", text)
        self.assertIn("@payments-team", text)
        self.assertIn("enforced by: CODEOWNERS", text)

    def test_compile_preserves_surrounding_agents_md_content(self):
        self.f.write("AGENTS.md", "# AGENTS.md\n\n## Dev environment\n\n- Run: `python3 run_tests.py`\n")
        self.f.rmem("compile")
        text = self.f.read("AGENTS.md")
        self.assertIn("## Dev environment", text)
        self.assertIn("## House rules", text)


# ---------------------------------------------------------------- other checks

class TestOtherChecks(Base):
    def test_expired_review_by_fails(self):
        self.f.add("--type", "convention", "--title", "Old rule",
                   "--anchor", "src/billing/**", "--review-by", "2020-01-01",
                   "--author", "test")
        self.assertFails("reviews-current")

    def test_duplicate_ids_fail(self):
        text = self.f.read(".memory/conventions.md")
        entry = text[text.index("## "):]        # the whole entry, heading and fence
        self.f.write(".memory/conventions.md", text + "\n" + entry)
        self.f.rmem("index")
        self.assertFails("ids-unique")


class TestSupersededAreHistory(Base):
    def test_superseded_entries_are_excluded_from_live_checks(self):
        """Otherwise the health score can never go green again."""
        old = self.f.add("--type", "decision", "--title", "Old billing rule",
                         "--anchor", "src/nonexistent/**", "--author", "test")
        new = self.f.add("--type", "decision", "--title", "New billing rule",
                         "--anchor", "src/billing/**", "--author", "test")
        self.f.rmem("index")
        self.assertFails("anchors-resolve")

        self.f.rmem("supersede", old, new)
        self.f.rmem("index")
        self.assertGreen()


class TestRetractAndRm(Base):
    """Two different situations that both used to require hand-editing the markdown:

    `retract` -- this was never true. Keep the text so a reviewer sees what was removed.
    `rm`      -- this must not be in the repo at all. Delete it, and say out loud that
                 deleting a file is not unpublishing.
    """

    def three_decisions(self):
        ids = []
        for name in ("Alpha rule", "Bravo rule", "Charlie rule"):
            ids.append(self.f.add("--type", "decision", "--title", name,
                                  "--body", "body of " + name,
                                  "--anchor", "src/billing/**", "--author", "test"))
        self.f.commit("three decisions")
        return ids

    def headings(self, name=".memory/decisions.md"):
        return re.findall(r"(?m)^## (.+)$", self.f.read(name))

    # -------------------------------------------------------------- retract

    def test_retract_keeps_the_text_and_labels_the_heading(self):
        _, b, _ = self.three_decisions()
        code, out = self.f.rmem("retract", b, "--reason", "the agent inferred this")
        self.assertEqual(code, 0, out)

        text = self.f.read(".memory/decisions.md")
        self.assertIn("## Bravo rule (retracted)", text)
        self.assertIn("status: retracted", text)
        self.assertIn("retracted_reason: the agent inferred this", text)
        # the body survives: that is the entire point of retracting rather than deleting
        self.assertIn("body of Bravo rule", text)

    def test_retract_without_a_reason_is_refused(self):
        _, b, _ = self.three_decisions()
        code, out = self.f.rmem("retract", b)
        self.assertNotEqual(code, 0, "a silent disappearance must not be possible")
        self.assertIn("reason", out.lower())

    def test_retract_is_idempotent_and_replaces_the_reason(self):
        _, b, _ = self.three_decisions()
        self.f.rmem("retract", b, "--reason", "first")
        self.f.rmem("retract", b, "--reason", "corrected")
        text = self.f.read(".memory/decisions.md")
        self.assertEqual(text.count("(retracted)"), 1, text)
        self.assertIn("retracted_reason: corrected", text)
        self.assertNotIn("retracted_reason: first", text)

    def test_retracted_entries_are_excluded_from_live_checks(self):
        """Prove it in both directions: while live the entry is an obligation, and once
        retracted it is history -- even though its anchored code has gone."""
        mem = self.f.add("--type", "decision", "--title", "Users API shape",
                         "--body", "handlers are one-per-resource",
                         "--anchor", "src/api/**", "--author", "test")
        self.f.commit("api decision")
        self.f.rmem("index")
        self.assertGreen()

        (self.f.dir / "src/api/handlers/users.py").unlink()
        self.f.rmem("index")
        self.assertFails("anchors-resolve")          # it really is a live obligation

        self.f.rmem("retract", mem, "--reason", "wrong from the start")
        self.f.rmem("index")
        self.assertGreen()                           # and now it is not

    # ------------------------------------------------------------------- rm

    def test_rm_removes_only_the_target_and_never_the_file_header(self):
        a, b, c = self.three_decisions()
        code, out = self.f.rmem("rm", a)          # the FIRST entry: the header-eating case
        self.assertEqual(code, 0, out)

        text = self.f.read(".memory/decisions.md")
        self.assertTrue(text.startswith("# Decisions"), text[:60])
        self.assertIn("one entry per '## ' heading", text)
        self.assertNotIn("Alpha rule", text)
        self.assertIn("Bravo rule", text)
        self.assertIn("Charlie rule", text)
        self.assertNotIn(a, text)
        self.assertEqual(len(self.headings()), 2)

    def test_rm_leaves_a_parseable_file(self):
        a, _, _ = self.three_decisions()
        self.f.rmem("rm", a)
        self.f.rmem("index")
        self.assertGreen()                       # index rebuilt and consistent
        code, out = self.f.rmem("list")
        self.assertEqual(code, 0)
        self.assertNotIn("Alpha rule", out)
        self.assertIn("Bravo rule", out)

    def test_rm_reports_that_history_is_untouched(self):
        a, _, _ = self.three_decisions()
        code, out = self.f.rmem("rm", a)
        self.assertEqual(code, 0)
        low = out.lower()
        self.assertTrue("git log" in low or "clone" in low,
                        "rm must not imply the text is gone from history:\n" + out)
        self.assertIn("retract", low, "should point at the safer verb")

    def test_rm_of_an_unknown_id_fails_loudly(self):
        self.three_decisions()
        code, out = self.f.rmem("rm", "DEC-1970-01-01-nope")
        self.assertEqual(code, 1)
        self.assertIn("no memory with id", out)


class TestContradictions(Base):
    """Two live memories that claim the same thing must not disagree about it.

    This is the only contradiction decidable without natural-language inference, so it is
    the only one the tool asserts. These tests also pin the deliberate refusals: no
    guessing at prose, no picking a winner, and no silencing a conflict anonymously.
    """

    def claim(self, title, value, key="refund.window_days"):
        return self.f.add("--type", "convention", "--title", title, "--body", "b",
                          "--anchor", "src/billing/**", "--key", key,
                          "--value", value, "--author", "test")

    def decision(self, title):
        return self.f.add("--type", "decision", "--title", title, "--body", "b",
                          "--anchor", "src/billing/**", "--author", "test")

    def test_same_key_different_value_is_a_contradiction(self):
        a = self.claim("Refunds close at 90 days", "90")
        b = self.claim("Refunds close at 30 days", "30")
        self.f.commit()
        self.assertFails("claims-agree")
        # both sides get named, and the tool refuses to choose for the reader
        code, out = self.f.rmem("check")
        self.assertIn(a, out)
        self.assertIn(b, out)
        self.assertIn("will not pick a winner", out)

    def test_same_key_same_value_agrees(self):
        self.claim("Window is 90 days", "90")
        self.claim("Refund window, restated", "90")
        self.f.commit()
        self.assertGreen()

    def test_different_keys_do_not_collide(self):
        self.claim("Window is 90 days", "90", key="refund.window_days")
        self.claim("Provider retries are 3", "3", key="provider.retries")
        self.f.commit()
        self.assertGreen()

    def test_supersede_to_a_missing_id_fails_the_chain_check(self):
        """Retiring a memory in favour of something that does not exist points nowhere.

        Note what supersede does NOT do: it retires the target even when the replacement id
        is fiction, so the entry does leave the live set. What is then broken is the
        retirement itself -- which is exactly what supersedes-acyclic is for.
        """
        a = self.claim("Refunds close at 90 days", "90")
        self.claim("Refunds close at 30 days", "30")
        self.f.commit()
        self.f.rmem("supersede", a, "DEC-does-not-exist")
        self.f.rmem("index")
        h = self.f.health()
        self.assertFails("supersedes-acyclic", h)
        self.assertNotIn("claims-agree", h["failed"], "the entry did get retired")

    def test_add_refuses_a_key_without_a_value_and_vice_versa(self):
        code, out = self.f.rmem("add", "--type", "convention", "--title", "x",
                                "--key", "refund.window_days", "--author", "test")
        self.assertEqual(code, 1)
        self.assertIn("--value", out)
        code, out = self.f.rmem("add", "--type", "convention", "--title", "x",
                                "--value", "90", "--author", "test")
        self.assertEqual(code, 1)
        self.assertIn("--key", out)

    def test_declaring_coexistence_requires_a_reason(self):
        """Silencing a conflict has to be attributable -- same rule as retract."""
        a = self.claim("Refunds close at 90 days", "90")
        code, out = self.f.rmem("verify", a, "--coexists-with", "DEC-whatever")
        self.assertEqual(code, 1)
        self.assertIn("--coexists-why", out)
        code, out = self.f.rmem("add", "--type", "convention", "--title", "y",
                                "--coexists-with", a, "--author", "test")
        self.assertEqual(code, 1)
        self.assertIn("--coexists-why", out)

    def test_declaring_coexistence_on_an_existing_entry_clears_it(self):
        """The resolution has to work on an existing entry: re-adding would duplicate it."""
        a = self.claim("Refunds close at 90 days", "90")
        b = self.claim("Refunds close at 30 days", "30")
        self.f.commit()
        self.assertFails("claims-agree")

        code, out = self.f.rmem("verify", b, "--coexists-with", a,
                                "--coexists-why", "partner-tier contracts override it")
        self.assertEqual(code, 0, out)
        self.f.rmem("index")
        self.assertGreen()
        # resolved, but NOT hidden: the deliberate disagreement stays visible
        code, out = self.f.rmem("check")
        self.assertIn("declared coexistence", out)
        self.assertIn("partner-tier contracts override it", out)

    def test_superseding_the_wrong_one_clears_it(self):
        a = self.claim("Refunds close at 90 days", "90")
        b = self.claim("Refunds close at 30 days", "30")
        self.f.commit()
        self.f.rmem("supersede", a, b)
        self.f.rmem("index")
        self.assertGreen()

    def test_retracting_the_one_that_was_never_true_clears_it(self):
        a = self.claim("Refunds close at 90 days", "90")
        self.claim("Refunds close at 30 days", "30")
        self.f.commit()
        self.f.rmem("retract", a, "--reason", "the window was never 90 days")
        self.f.rmem("index")
        self.assertGreen()

    def test_key_without_a_value_is_a_notice_not_a_failure(self):
        """Incomplete metadata must never break the build: abstain, do not punish."""
        eid = self.f.add("--type", "convention", "--title", "Hand edited later",
                         "--anchor", "src/billing/**", "--author", "test")
        p = self.f.dir / ".memory/conventions.md"
        p.write_text(p.read_text().replace("id: " + eid,
                                           "id: " + eid + "\nkey: orphan.key", 1))
        self.f.rmem("index")
        self.assertGreen()
        code, out = self.f.rmem("check")
        self.assertIn("no value", out)


class TestRetirementChains(Base):
    """Following a replacement pointer must terminate at something live.

    The reviewer who reads "replaced by X" and then finds X retracted has no rule at all
    and no signal that anything is wrong. Hand-edits and retract-after-supersede are how
    this actually happens.
    """

    def decision(self, title):
        return self.f.add("--type", "decision", "--title", title, "--body", "b",
                          "--anchor", "src/billing/**", "--author", "test")

    def test_a_normal_supersession_chain_is_fine(self):
        a = self.decision("First rule")
        b = self.decision("Second rule")
        self.f.commit()
        self.f.rmem("supersede", a, b)
        self.f.rmem("index")
        self.assertGreen()

    def test_a_chain_ending_on_a_retracted_memory_fails(self):
        a = self.decision("First rule")
        b = self.decision("Second rule")
        self.f.commit()
        self.f.rmem("supersede", a, b)
        self.f.rmem("retract", b, "--reason", "the second rule was wrong too")
        self.f.rmem("index")
        h = self.f.health()
        self.assertFails("supersedes-acyclic", h)
        code, out = self.f.rmem("check")
        self.assertIn("itself retired", out)

    def test_a_cycle_fails_and_is_reported_once(self):
        a = self.decision("First rule")
        b = self.decision("Second rule")
        self.f.commit()
        p = self.f.dir / ".memory/decisions.md"
        t = p.read_text()
        t = t.replace("id: " + a, "id: " + a + "\nsuperseded_by: " + b, 1)
        t = t.replace("id: " + b, "id: " + b + "\nsuperseded_by: " + a, 1)
        p.write_text(t)
        self.f.rmem("index")

        h = self.f.health()
        self.assertFails("supersedes-acyclic", h)
        code, out = self.f.rmem("check")
        self.assertEqual(out.count("a cycle"), 1, "a 2-cycle must be reported once:\n" + out)


class TestSinceBoundary(Base):
    """`--since` is the CI boundary, and an unresolvable one must fail closed.

    An unresolvable ref produces an empty `git diff`, which silently disables
    dead-ends-settled. That is the same fail-open shape as trusting commit SHAs: a shallow
    clone that never fetched the base sha would quietly switch off the check that catches a
    dead end recorded by the change that settled it.
    """

    def test_an_unresolvable_since_fails_closed(self):
        code, out = self.f.rmem("check", "--brief", "--since", "deadbeef")
        self.assertEqual(code, 1, "an unresolvable boundary must not go quiet:\n" + out)
        self.assertIn("dead-ends-settled", out)

    def test_an_all_zero_since_fails_closed(self):
        """`github.event.before` on a new branch push is 40 zeros -- a real-world input."""
        code, out = self.f.rmem("check", "--brief", "--since", "0" * 40)
        self.assertEqual(code, 1, out)

    def test_a_resolvable_since_is_green(self):
        code, out = self.f.rmem("check", "--brief", "--since", "HEAD")
        self.assertEqual(code, 0, out)

    def test_no_since_at_all_is_still_green(self):
        code, out = self.f.rmem("check", "--brief")
        self.assertEqual(code, 0, out)

    def test_the_message_says_how_to_fix_it(self):
        code, out = self.f.rmem("check", "--since", "deadbeef")
        self.assertIn("does not resolve", out)
        self.assertIn("fetch-depth", out, "must name the actual CI fix:\n" + out)

    def test_the_check_fires_on_a_real_boundary(self):
        """The arm-4 shape end to end: fix the code and record the problem you just fixed.

        This is the scenario observed twice from independent agent runs, here driven through
        the real CI path (--since <base-sha>) rather than by direct construction.
        """
        base = self.f.git("rev-parse", "HEAD").stdout.strip()
        self.f.write("src/billing/charge.py", "def charge():\n    return 99\n")
        eid = self.f.add("--type", "dead-end",
                         "--title", "The refund window rejects credit notes",
                         "--body", "Settled by this change.",
                         "--anchor", "src/billing/**", "--evidence", "observed in prod",
                         "--author", "test")
        self.f.commit("fix it and record it")
        self.f.rmem("index")

        code, out = self.f.rmem("check", "--brief", "--since", base)
        self.assertEqual(code, 1, "the gate must catch this:\n" + out)
        self.assertIn("dead-ends-settled", out)
        # the same change also staled the seeded convention: two different checks, two
        # different reasons, both of which a reviewer has to resolve in this PR
        self.assertIn("anchors-not-stale", out)

        # The in-PR resolution: the convention is still true, the dead end was settled here.
        self.f.rmem("verify", self.conv)
        self.f.rmem("verify", eid, "--resolved-by", "this change")
        self.f.rmem("index")
        code, out = self.f.rmem("check", "--brief", "--since", base)
        self.assertEqual(code, 0, out)


class TestSubdirectoryLayout(Base):
    """A memory root that is NOT the git root must still be checked.

    git reports changed paths relative to the REPO ROOT, while .memory/ and anchors are
    written relative to the WORKING DIRECTORY. Comparing the two never matches, so every
    change-scoped check -- dead-ends-settled above all -- goes silent in exactly the layout a
    monorepo or a service subdirectory uses. Silent is the worst outcome: the gate reports
    GREEN while checking nothing.
    """

    def setUp(self):
        super().setUp()
        self.f.write("svc/src/billing/charge.py", "def charge():\n    return 1\n")
        self.f.commit("add the service")
        code, out = self.f.rmem("init", cwd="svc")
        self.assertEqual(code, 0, out)
        self.f.commit("init memory inside the service")

    def test_dead_ends_settled_fires_from_a_subdirectory(self):
        base = self.f.git("rev-parse", "HEAD").stdout.strip()
        self.f.write("svc/src/billing/charge.py", "def charge():\n    return 2\n")
        code, out = self.f.rmem("add", "--type", "dead-end",
                                "--title", "The window rejects credit notes too",
                                "--body", "b", "--anchor", "src/billing/**",
                                "--evidence", "observed in prod", "--author", "test",
                                cwd="svc")
        self.assertEqual(code, 0, out)
        self.f.commit("fix it and record it in the same change")
        self.f.rmem("index", cwd="svc")

        code, out = self.f.rmem("check", "--brief", "--since", base, cwd="svc")
        self.assertEqual(code, 1,
                         "dead-ends-settled went quiet: git paths are repo-root relative "
                         "while anchors are cwd relative.\n" + out)
        self.assertIn("dead-ends-settled", out)

    def test_the_stale_report_names_the_file_from_a_subdirectory(self):
        self.f.rmem("add", "--type", "decision", "--title", "Gateway only",
                    "--anchor", "src/billing/**", "--author", "test", cwd="svc")
        self.f.rmem("index", cwd="svc")
        self.f.commit("record the decision")
        self.f.write("svc/src/billing/charge.py", "def charge():\n    return 3\n")
        self.f.commit("move the code")
        self.f.rmem("index", cwd="svc")

        code, out = self.f.rmem("check", cwd="svc")
        self.assertEqual(code, 1, out)
        self.assertIn("src/billing/charge.py", out,
                      "the stale report should name the file, not fall back to "
                      "'its anchored files':\n" + out)


class TestCliRobustness(Base):
    def test_version_is_reported(self):
        code, out = self.f.rmem("--version")
        self.assertEqual(code, 0)
        self.assertIn("rmem", out)

    def test_readme_version_matches_the_tool(self):
        """Docs drift silently. The README states a version; the tool must agree."""
        readme = (TOOL.parent / "README.md").read_text()
        m = re.search(r"Prototype v(\d+\.\d+\.\d+)", readme)
        self.assertIsNotNone(m, "README should state a version")
        assert m is not None
        version = m.group(1)
        code, out = self.f.rmem("--version")
        self.assertIn(version, out,
                      "README says v%s but the tool reports %r" % (version, out.strip()))

    def test_piping_into_head_does_not_traceback(self):
        """`rmem list | head` is normal usage and must not dump a stack trace."""
        r = subprocess.run("python3 %s list | head -1" % TOOL, shell=True,
                           cwd=self.f.dir, capture_output=True, text=True)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        self.assertNotIn("BrokenPipeError", r.stderr, r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCompileCarriesDeadEnds(Base):
    """AGENTS.md is the file agents actually read. A memory that is not in it is a memory
    nothing delivers -- measured, not assumed: a full agent trial run had the agent solve
    the task without ever opening .memory/, because nothing pointed it there."""

    def _add_dead_end(self, title="Keying on (order, amount) swallows a refund"):
        self.f.write("src/a.py", "x = 1\n")
        self.f.commit("code")
        code, out = self.f.rmem("add", "--type", "dead-end", "--title", title,
                                "--body", "Tried and rejected. Use instead: request_id",
                                "--anchor", "src/**", "--evidence", "prod #412",
                                "--author", "t")
        self.assertEqual(code, 0, out)
        self.f.rmem("index")

    def test_a_live_dead_end_reaches_agents_md(self):
        self._add_dead_end()
        code, out = self.f.rmem("compile")
        self.assertEqual(code, 0, out)
        agents = (self.f.dir / "AGENTS.md").read_text()
        self.assertIn("Rejected approaches", agents)
        self.assertIn("Keying on (order, amount) swallows a refund", agents)
        # the actionable half, not just the warning
        self.assertIn("Use instead: request_id", agents)

    def test_a_settled_dead_end_is_history_and_is_not_compiled(self):
        """Re-warning about a condition that no longer holds is a different bug."""
        self._add_dead_end("Settled thing")
        self.f.commit("record")
        # a UNIQUE prefix is a feature; an ambiguous one is refused (see TestIdResolution)
        mem = (self.f.dir / ".memory" / "dead-ends.md").read_text()
        eid = mem.split("id: ")[1].split("\n")[0].strip()
        code, out = self.f.rmem("verify", eid, "--resolved-by", "PR #1")
        self.assertEqual(code, 0, out)
        self.f.rmem("index")
        self.f.rmem("compile")
        agents = (self.f.dir / "AGENTS.md").read_text()
        self.assertNotIn("Settled thing", agents)


class TestIdResolution(Base):
    """An id must name exactly one memory.

    Matching was a substring test with no ambiguity check, so `verify 2026` re-stamped
    every memory created in 2026 -- and a re-stamp resets the staleness clock, so a loose
    match silently certified memories nobody named. That is the exact failure this tool
    exists to prevent, committed by the tool.
    """

    def setUp(self):
        super().setUp()
        self.f.write("src/a.py", "x = 1\n")
        self.f.write("src/b.py", "y = 1\n")
        self.f.commit("code")
        self.f.rmem("add", "--type", "decision", "--title", "A rule",
                    "--anchor", "src/a.py", "--author", "t")
        self.f.rmem("add", "--type", "decision", "--title", "B rule",
                    "--anchor", "src/b.py", "--author", "t")
        self.f.rmem("index")

    def test_an_ambiguous_prefix_is_refused_and_touches_nothing(self):
        code, out = self.f.rmem("verify", "DEC-", "--resolved-by", "PR #9")
        self.assertEqual(code, 1, "an ambiguous prefix must fail closed:\n" + out)
        self.assertIn("ambiguous", out.lower())
        self.assertNotIn("PR #9", (self.f.dir / ".memory" / "decisions.md").read_text(),
                         "an ambiguous id must not modify anything")

    def test_a_unique_prefix_resolves(self):
        mem = (self.f.dir / ".memory" / "decisions.md").read_text()
        first = mem.split("id: ")[1].split("\n")[0].strip()
        # a prefix longer than the shared date part is unique to one entry
        code, out = self.f.rmem("verify", first[:-2], "--resolved-by", "PR #9")
        self.assertEqual(code, 0, out)
        self.assertIn(first, out + (self.f.dir / ".memory" / "decisions.md").read_text())

    def test_an_unknown_id_refuses(self):
        code, out = self.f.rmem("verify", "NOPE-123", "--resolved-by", "PR #1")
        self.assertEqual(code, 1, out)
        self.assertIn("no memory with id", out)
