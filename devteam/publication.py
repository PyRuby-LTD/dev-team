"""The requirements-only body of a published work item."""
import re

from .questions import HEADING

PUBLISHED_SECTIONS = ("context", "acceptance criteria")
SECTION = re.compile(r"##\s+(.+?)\s*$")


def requirements(body):
    """Keep the preamble and allowed sections in item order, normalising seams."""
    blocks = []
    current = []
    keep = True

    def finish():
        while current and not current[-1].strip():
            current.pop()
        while current and not current[0].strip():
            current.pop(0)
        if keep and current:
            blocks.append("\n".join(current))

    for line in body.splitlines():
        if HEADING.match(line):
            finish()
            current = []
            heading = SECTION.fullmatch(line)
            keep = heading is not None and heading.group(1).casefold() in PUBLISHED_SECTIONS
        current.append(line)
    finish()
    return "\n" + "\n\n".join(blocks) + "\n" if blocks else ""
