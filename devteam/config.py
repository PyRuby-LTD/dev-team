import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def harness_command() -> str:
    path = str(ROOT)
    if any(char.isspace() or char in "*?[]()\"'\\" for char in path):
        raise ValueError("Harness checkout path cannot contain whitespace or * ? [ ] ( ) \" ' \\")
    return f"uv run --project {path} python -P -m devteam"


@dataclass
class Role:
    name: str
    engine: str
    model: str
    max_turns: int
    command: list[str]
    permission: str
    branch: bool = False
    record: bool = False
    push: bool = False
    stream: str = "text"

    def brief(self) -> str:
        text = (ROOT / "roles" / f"{self.name}.md").read_text()
        return text.replace("{{harness_command}}", harness_command()) if "{{harness_command}}" in text else text


def load_roles(path: Path | None = None) -> dict[str, Role]:
    data = tomllib.loads((path or ROOT / "config" / "roles.toml").read_text())
    roles = {}
    for name, spec in data["roles"].items():
        engine = data["engines"][spec["engine"]]
        roles[name] = Role(
            name=name,
            engine=spec["engine"],
            model=spec["model"],
            max_turns=spec.get("max_turns", 30),
            command=engine["command"],
            permission=engine["permission"],
            stream=engine.get("stream", "text"),
            branch=spec.get("branch", False),
            record=spec.get("record", False),
            push=spec.get("push", False),
        )
    return roles
