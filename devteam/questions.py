"""What the customer and agents say to each other in an item body: questions, answers and feedback."""
import re
from dataclasses import dataclass

FEEDBACK = re.compile(r"##\s+Feedback\s*$", re.IGNORECASE)
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


def add_feedback(body, label, text):
    """Append the customer's note to the '## Feedback' section, creating it at the end if needed."""
    text = text.strip()
    if not text:
        return body
    newline = "\r\n" if "\r\n" in body else "\n"
    first, *rest = text.splitlines()
    entry = [f"- **{label}:** {first}"] + [f"  {line}".rstrip() for line in rest]
    lines = body.splitlines()
    start = next((number for number, line in enumerate(lines) if FEEDBACK.match(line)), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", "## Feedback", ""] + entry
    else:
        end = next((number for number in range(start + 1, len(lines)) if HEADING.match(lines[number])), len(lines))
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = ([""] if end == start + 1 else []) + entry
    return newline.join(lines) + newline
