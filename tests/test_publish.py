"""STORY-013: the publisher instructions reuse open PRs and permit their gh calls."""
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublisherInstructions(unittest.TestCase):
    def setUp(self):
        self.prompt = (ROOT / "prompts" / "publish.md").read_text()
        self.prose = " ".join(self.prompt.split())
        self.config = tomllib.loads((ROOT / "config" / "roles.toml").read_text())

    def test_lookup_precedes_creation_and_handles_lookup_failure(self):
        lookup = "gh pr list --head {{branch}} --state open --json url"
        self.assertIn(lookup, self.prompt)
        self.assertLess(self.prompt.index(lookup), self.prompt.index("gh pr create"))
        self.assertIn("If the lookup fails, report the failure", self.prose)
        self.assertIn("only a successful empty result means none exists", self.prose)

    def test_open_pr_is_edited_and_only_absent_open_pr_is_created(self):
        self.assertIn("If an open PR exists, do not run `gh pr create`", self.prose)
        self.assertIn("gh pr edit <existing-url> --body-file <body-file>", self.prose)
        self.assertIn("leaving its title and URL unchanged", self.prose)
        self.assertIn("Only when no open PR exists for the branch, run `gh pr create", self.prose)

    def test_url_replaces_existing_section_content(self):
        self.assertIn("Record the pull request URL under `## Pull request`", self.prose)
        self.assertIn("Replace that section's content rather than adding a second heading", self.prose)
        self.assertIn("The section must hold exactly one URL", self.prose)
        self.assertIn("when updating an open PR, record the same URL as before", self.prose)

    def test_all_prompt_gh_commands_are_allowed_without_merge(self):
        command = self.config["engines"]["claude"]["command"]
        allowed = command[command.index("--allowedTools") + 1]
        gh_commands = set(re.findall(r"\bgh pr (\w+)", self.prompt))
        self.assertEqual({"list", "edit", "create"}, gh_commands)
        allowed_gh = set(re.findall(r"Bash\(gh pr (\w+) \*\)", allowed))
        self.assertEqual(gh_commands, allowed_gh)
        self.assertNotIn("gh pr merge", allowed)
        self.assertTrue(self.config["roles"]["publisher"]["push"])
        self.assertIn("Do not run `git push` or `git commit` yourself", self.prose)


if __name__ == "__main__":
    unittest.main()
