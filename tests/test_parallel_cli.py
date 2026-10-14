"""STORY-020: agent steps for roles without their own branch run at the same time.

The real `dev-team run --once` command is started against a product repository. The engine is a stand-in
executable that only finishes a step once the other items' steps have started, so the run can succeed only
if those steps overlapped; a serial runner makes the first one time out and fail.
"""
import json
import shutil

from tests.test_run_evidence import STUBS, Product

ANALYSED = {"reply": "analysed"}
SOUND = {"reply": "sound"}


class ParallelAgentsFromTheCommandLine(Product):
    def setUp(self):
        super().setUp()
        for engine in ("claude", "codex"):
            shutil.copy(STUBS / "rendezvous", self.bin / engine)
            (self.bin / engine).chmod(0o755)
        self.markers = self.base / "markers"
        self.script = self.base / "script.json"

    def story(self, number, *transitions):
        item = f"STORY-{number:03d}"
        if number != 1:
            self.devteam("backlog", "capture", "story", f"Story {number}", "--id", item, "--parent", "EPIC-001")
        for transition in transitions:
            self.devteam("backlog", "move", item, transition)

    def steps(self):
        listing = self.devteam("backlog", "list").stdout
        return {line.split()[0]: line.split()[1] for line in listing.splitlines() if line.startswith("STORY-")}

    def run_with(self, script):
        self.script.write_text(json.dumps(script))
        return self.devteam("run", "--once", ok=False, STUB_SCRIPT=str(self.script), STUB_MARKERS=str(self.markers))

    def test_analysts_for_several_stories_work_at_the_same_time(self):
        for number in (1, 2, 3):
            self.story(number, "analyse")
        ids = ["STORY-001", "STORY-002", "STORY-003"]
        script = {item: [{"wait_for": [other for other in ids if other != item], **ANALYSED}, SOUND] for item in ids}

        result = self.run_with(script)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({item: "ready" for item in ids}, self.steps())
        for item in ids:
            self.assertEqual(2, len(list(self.markers.glob(f"{item}.*"))))

    def test_analysis_runs_alongside_a_branch_step_and_the_other_branch_step_waits_for_the_checkout(self):
        self.story(1, "analyse", "analysed", "sound", "play")
        self.story(2, "analyse", "analysed", "sound", "play")
        self.story(3, "analyse")
        script = {"STORY-001": [{"wait_for": ["STORY-003"], "reply": "implemented"}],
                  "STORY-002": [{"wait_for": ["STORY-003"], "reply": "implemented"}],
                  "STORY-003": [{"wait_for_any": ["STORY-001", "STORY-002"], **ANALYSED}, SOUND]}

        result = self.run_with(script)

        output = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, output)
        self.assertEqual("ready", self.steps()["STORY-003"], output)
        self.assertIn("which is using the checkout", output)
