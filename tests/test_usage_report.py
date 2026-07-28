import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EMULO = ROOT / "emulo.py"
sys.path.insert(0, str(ROOT))

import emulo  # noqa: E402


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def codex_turn(text, minute=0):
    return {
        "timestamp": f"2026-07-08T10:{minute:02d}:00Z",
        "payload": {"type": "message", "role": "user", "content": [{"text": text}]},
    }


def record(*texts, session_id="s1", source="codex", date="2026-07-08"):
    return {
        "session_id": session_id,
        "source": source,
        "messages": [
            {"date": date, "text": text, "ordinal": index}
            for index, text in enumerate(texts)
        ],
    }


def by_key(report, key):
    for item in report["findings"]:
        if item["key"] == key:
            return item
    return None


def clean_keys(report):
    return {item["title"] for item in report["clean"]}


class RepeatSendTest(unittest.TestCase):
    def test_three_identical_substantive_sends_are_flagged(self):
        ask = "what MCP tools do you have from the gateway"
        report = emulo.usage_report([record(ask, ask, ask)])
        finding = by_key(report, "repeat_sends")
        self.assertIsNotNone(finding)
        self.assertEqual(finding["occurrences"], 3)
        self.assertEqual(finding["receipts"][0]["count"], 3)

    def test_case_and_punctuation_differences_still_count_as_the_same_send(self):
        report = emulo.usage_report([record(
            "run the migration now",
            "Run the migration now.",
            "run  the migration now!",
        )])
        self.assertIsNotNone(by_key(report, "repeat_sends"))

    def test_repeated_approvals_are_not_a_finding(self):
        # Measured on the real corpus: without the word floor this check is
        # almost entirely "ok"/"yes" sent three times, which is approval.
        for filler in ("ok", "yes", "ok do it"):
            report = emulo.usage_report([record(filler, filler, filler)])
            self.assertIsNone(by_key(report, "repeat_sends"), filler)

    def test_two_sends_are_a_retry_not_a_loop(self):
        ask = "please regenerate the release notes"
        self.assertIsNone(by_key(emulo.usage_report([record(ask, ask)]), "repeat_sends"))

    def test_identical_asks_far_apart_are_not_a_loop(self):
        ask = "please regenerate the release notes"
        report = emulo.usage_report([record(
            ask, "unrelated work here", "more unrelated work", ask, "and again", ask,
        )])
        self.assertIsNone(by_key(report, "repeat_sends"))

    def test_a_run_inside_one_session_does_not_span_sessions(self):
        ask = "please regenerate the release notes"
        report = emulo.usage_report([
            record(ask, session_id="a"),
            record(ask, session_id="b"),
            record(ask, session_id="c"),
        ])
        self.assertIsNone(by_key(report, "repeat_sends"))


class CorrectionTest(unittest.TestCase):
    def test_correction_openers_are_counted(self):
        messages = ["no that is wrong, use the other file"] * 2 + ["ok"] * 2
        report = emulo.usage_report([record(*messages)])
        self.assertEqual(report["correction_rate"], 50)

    def test_no_need_is_not_a_correction(self):
        report = emulo.usage_report([record(
            "no need for the repo i think",
            "no worries about the lint",
            "no problem",
        )])
        self.assertEqual(report["correction_rate"], 0)

    def test_correction_below_the_rate_bar_is_reported_but_not_flagged(self):
        messages = ["no this is wrong"] + ["ordinary work message here"] * 99
        report = emulo.usage_report([record(*messages)])
        self.assertEqual(report["correction_rate"], 1)
        self.assertIsNone(by_key(report, "corrections"))
        self.assertIn("You open turns by correcting the last answer.", clean_keys(report))

    def test_correction_above_the_rate_bar_is_flagged(self):
        messages = ["no this is wrong"] * 10 + ["ordinary work message here"] * 40
        report = emulo.usage_report([record(*messages)])
        self.assertEqual(report["correction_rate"], 20)
        self.assertIsNotNone(by_key(report, "corrections"))

    def test_a_correction_mid_sentence_is_not_an_opener(self):
        report = emulo.usage_report([record(
            "the test asserts the wrong column so it never fails",
        )])
        self.assertEqual(report["correction_rate"], 0)


class RestatedContextTest(unittest.TestCase):
    def test_restated_context_needs_repetition_before_it_is_flagged(self):
        two = emulo.usage_report([record("i told you to keep the dark theme"),
                                  record("as i said, keep the dark theme")])
        self.assertIsNone(by_key(two, "restated_context"))

    def test_restated_context_is_flagged_with_its_marker(self):
        report = emulo.usage_report([record(
            "i told you to keep the dark theme",
            "as i said, the header stays fixed",
            "like i said, no new dependencies",
        )])
        finding = by_key(report, "restated_context")
        self.assertIsNotNone(finding)
        self.assertEqual(finding["occurrences"], 3)
        self.assertEqual(
            {receipt["marker"] for receipt in finding["receipts"]},
            {"i told you", "as i said", "like i said"},
        )

    def test_quote_is_windowed_onto_a_buried_marker(self):
        buried = ("x" * 400) + " i already told you the header stays fixed " + ("y" * 400)
        report = emulo.usage_report([record(buried, buried + "!", buried + "?")])
        finding = by_key(report, "restated_context")
        self.assertIsNotNone(finding)
        # A receipt whose quote does not contain the evidence cannot be checked.
        for receipt in finding["receipts"]:
            self.assertIn("i already told you", receipt["text"])


class RewordLoopTest(unittest.TestCase):
    def test_near_identical_consecutive_asks_are_flagged(self):
        report = emulo.usage_report([record(
            "make the release notes shorter and drop the roadmap section",
            "make the release notes shorter and drop the roadmap part",
            "make the release notes much shorter and drop the roadmap part",
        )])
        self.assertIsNotNone(by_key(report, "reword_loops"))

    def test_a_repasted_block_is_not_a_reworded_ask(self):
        # The only thing this check caught on a real corpus was a pasted
        # pygame banner sent three times, not a person rephrasing anything.
        block = "pygame 2.6.1 (SDL 2.28.4, Python 3.11.4)\n" + "\n".join(
            f"[hud] line {index} of the same pasted banner" for index in range(8)
        )
        report = emulo.usage_report([record(block, block + "\nx", block + "\ny")])
        self.assertIsNone(by_key(report, "reword_loops"))

    def test_unrelated_consecutive_asks_are_not_a_loop(self):
        report = emulo.usage_report([record(
            "make the release notes shorter and drop the roadmap section",
            "now bump the version and tag it for the public release",
            "write a migration guide for the storage layer change",
        )])
        self.assertIsNone(by_key(report, "reword_loops"))


class ReportShapeTest(unittest.TestCase):
    def test_receipts_do_not_repeat_the_same_quote(self):
        report = emulo.usage_report([record(
            *["i told you to keep the dark theme"] * 8, session_id="a"
        )])
        finding = by_key(report, "restated_context")
        quotes = [receipt["text"] for receipt in finding["receipts"]]
        self.assertEqual(len(quotes), len(set(quotes)))

    def test_every_flagged_finding_carries_receipts(self):
        report = emulo.usage_report([record(
            "i told you to keep the dark theme",
            "as i said, the header stays fixed",
            "like i said, no new dependencies",
        )])
        self.assertTrue(report["findings"])
        for finding in report["findings"]:
            self.assertTrue(finding["receipts"], finding["key"])

    def test_empty_corpus_does_not_crash(self):
        report = emulo.usage_report([])
        self.assertEqual(report["sessions"], 0)
        self.assertEqual(report["messages"], 0)
        self.assertEqual(report["findings"], [])

    def test_stats_describe_the_corpus(self):
        report = emulo.usage_report([record("one two three four five six", "ok")])
        self.assertEqual(report["messages"], 2)
        self.assertEqual(report["short_prompts"], 1)
        self.assertEqual(report["sources"], {"codex": 1})


class InjectedContextTest(unittest.TestCase):
    """The IDE's own preamble is not something the user typed.

    Found by running --coach over a real corpus: 743 of these blocks were being
    read as user messages, and their near-verbatim repetition made them the
    loudest finding in the report. They pollute mining the same way.
    """

    def test_ide_setup_preamble_is_treated_as_injected(self):
        self.assertTrue(emulo.is_injected_context(
            "# Context from my IDE setup:\n\n## Active file: docs/plan.md"
        ))
        self.assertTrue(emulo.is_injected_context(
            "# Context from my IDE setup:\n\n## Open tabs:\n- a.py\n- b.py"
        ))

    def test_files_mentioned_preamble_is_treated_as_injected(self):
        self.assertTrue(emulo.is_injected_context(
            "# Files mentioned by the user:\n\n## clipboard-1.png: C:/tmp/clipboard-1.png"
        ))

    def test_a_user_writing_about_their_ide_is_not_injected(self):
        self.assertFalse(emulo.is_injected_context(
            "the context from my IDE setup keeps leaking into the prompt"
        ))

    def test_injected_preamble_never_reaches_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            block = "# Context from my IDE setup:\n\n## Active file: docs/plan.md"
            write_jsonl(logs / "session.jsonl", [
                codex_turn(block, 0), codex_turn(block, 1), codex_turn(block, 2),
                codex_turn("ship the release notes when the suite is green", 3),
            ])
            proc = subprocess.run(
                [sys.executable, str(EMULO), "--coach", "--path", str(logs), "--json"],
                capture_output=True, text=True, cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["messages"], 1)
            self.assertEqual(report["findings"], [])


class CoachCliTest(unittest.TestCase):
    def _run(self, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            ask = "what MCP tools do you have from the gateway"
            write_jsonl(logs / "session.jsonl", [
                codex_turn(ask, 0),
                codex_turn(ask, 1),
                codex_turn(ask, 2),
                codex_turn("i told you the header stays fixed", 3),
            ])
            proc = subprocess.run(
                [sys.executable, str(EMULO), "--coach", "--path", str(logs), *extra],
                capture_output=True, text=True, cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return proc.stdout, Path(tmp)

    def test_coach_reports_the_loop_and_writes_nothing(self):
        stdout, tmp = self._run()
        self.assertIn("emulo usage report", stdout)
        self.assertIn("You resend the same message instead of changing it.", stdout)
        self.assertIn("what MCP tools do you have from the gateway", stdout)
        # The report is a read: it must never leave a corpus behind.
        self.assertFalse((tmp / "emulo-out").exists())

    def test_coach_states_what_it_cannot_see(self):
        stdout, _ = self._run()
        self.assertIn("cost, tokens, tool calls", stdout)

    def test_coach_json_is_machine_readable(self):
        stdout, _ = self._run("--json")
        report = json.loads(stdout)
        self.assertEqual(report["sessions"], 1)
        self.assertTrue(any(item["key"] == "repeat_sends" for item in report["findings"]))

    def test_coach_redacts_receipts_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            # Assembled at runtime on purpose. Written inline this matches the
            # same REDACTIONS pattern it is testing, and a repo secret scanner
            # cannot tell a fixture key from a real one that leaked.
            fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz012345"
            secret = f"i told you the key is {fake_key}"
            write_jsonl(logs / "session.jsonl", [codex_turn(secret, 0)])
            proc = subprocess.run(
                [sys.executable, str(EMULO), "--coach", "--path", str(logs), "--json"],
                capture_output=True, text=True, cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn(fake_key, proc.stdout)


if __name__ == "__main__":
    unittest.main()
