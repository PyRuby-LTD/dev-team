"""Questions an agent leaves for the customer in an item body, and the answers written beneath them."""
import re
from dataclasses import dataclass

SECTION = re.compile(r"##\s+Questions\s*$", re.IGNORECASE)
HEADING = re.compile(r"#{1,2}\s")
QUESTION = re.compile(r"\s{0,3}(?:\d+[.)]|[-*])\s+(\S.*)")
ANSWER = re.compile(r"\s*>?\s*\**\s*Answer\b", re.IGNORECASE)


@dataclass
class Question:
    text: str
    answered: bool
    last_line: int


def parse(body):
    """Each list item under a '## Questions' heading; answered once an 'Answer' line follows it."""
    lines = body.splitlines()
    found, inside, current = [], False, None
    for number, line in enumerate(lines):
        if SECTION.match(line):
            inside, current = True, None
        elif inside and HEADING.match(line):
            inside, current = False, None
        elif inside:
            match = QUESTION.match(line)
            if match:
                current = Question(match.group(1).strip(), False, number)
                found.append(current)
            elif current is not None and line.strip():
                current.last_line = number
                if ANSWER.match(line):
                    current.answered = True
                else:
                    current.text += " " + line.strip()
    return found


def answer(body, answers):
    """Write each answer (keyed by its index in parse(body)) beneath its question."""
    newline = "\r\n" if "\r\n" in body else "\n"
    lines = body.splitlines()
    questions = parse(body)
    for index in sorted(answers, reverse=True):
        text = answers[index].strip()
        if not text or questions[index].answered:
            continue
        first, *rest = text.splitlines()
        block = ["", f"   **Answer:** {first}"] + [f"   {line}".rstrip() for line in rest]
        at = questions[index].last_line + 1
        lines[at:at] = block
    return newline.join(lines) + (newline if body.endswith(("\n", "\r")) else "")
