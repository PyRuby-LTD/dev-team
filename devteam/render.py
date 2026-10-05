"""Display agent streams without changing their raw transcripts or replies."""
import json


def text(line: str) -> str:
    line = line.rstrip("\r\n")
    return line if len(line) <= 200 else line[:197] + "..."


def event(line):
    try:
        value = json.loads(line)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def blocks(value):
    message = value.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def claude_json(line: str) -> str | None:
    try:
        value = json.loads(line)
        if not isinstance(value, dict) or value.get("type") != "assistant":
            return None
        rendered = []
        for block in blocks(value):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                rendered.extend(text(part) for part in block["text"].splitlines())
            elif block.get("type") == "tool_use":
                name = " ".join(str(block.get("name", "")).split())
                args = block.get("input")
                arg = next((args[key] for key in ("file_path", "path", "command", "pattern", "url", "description")
                            if key in args), "") if isinstance(args, dict) else ""
                arg = " ".join(str(arg).split())
                rendered.append(text(f"tool: {name} {arg}".rstrip()))
        return "\n".join(rendered) or None
    except Exception:
        return text(line)


def text_reply(code: int, stdout: str) -> tuple[int, str]:
    return code, stdout


def claude_reply(code: int, stdout: str) -> tuple[int, str]:
    result = None
    assistant = []
    for line in stdout.splitlines():
        value = event(line)
        if value.get("type") == "result" and isinstance(value.get("result"), str):
            result = value["result"]
        elif value.get("type") == "assistant":
            assistant.extend(block["text"] for block in blocks(value)
                             if block.get("type") == "text" and isinstance(block.get("text"), str))
    if result is not None:
        return code, result
    reply = "".join(assistant)
    return (code if code or reply else 1), reply


STREAMS = {
    "text": (text, text_reply),
    "claude-json": (claude_json, claude_reply),
}
