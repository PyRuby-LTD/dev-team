import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def workspace() -> Path:
    """Where this team's output for the current product goes. See config/workspace."""
    conf = ROOT / "config" / "workspace"
    for line in conf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            path = Path(line)
            return path if path.is_absolute() else (ROOT / path).resolve()
    raise SystemExit(f"no workspace path set in {conf}")


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

    def brief(self) -> str:
        return (ROOT / "roles" / f"{self.name}.md").read_text()


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
            branch=spec.get("branch", False),
            record=spec.get("record", False),
        )
    return roles
