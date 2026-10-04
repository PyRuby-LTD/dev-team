import shlex
import subprocess
from pathlib import Path

from .config import Role
from .workitem import WorkItem, now


def build_argv(role: Role, prompt: str, cwd: Path, extra_dir: Path, access: str) -> list[str]:
    values = {
        "prompt": prompt,
        "model": role.model,
        "brief": role.brief(),
        "cwd": str(cwd),
        "extra_dir": str(extra_dir),
        "permission": role.permissions[access],
        "max_turns": str(role.max_turns),
    }
    return [arg.format_map(values) if "{" in arg else arg for arg in role.command]


def run(role: Role, item: WorkItem, stage: str, prompt: str, cwd: Path, access: str) -> int:
    """Invoke the role's CLI. The agent writes its own artifacts; we keep the transcript."""
    argv = build_argv(role, prompt, cwd, item.path, access)
    log = item.path / "log" / f"{stage}-{now().replace(':', '')}.log"
    header = f"# {role.name} via {role.engine} ({role.model})\n# cwd: {cwd}\n# {shlex.join(argv)}\n\n"

    with log.open("w") as fh:
        fh.write(header)
        fh.flush()
        proc = subprocess.run(argv, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT)

    item.record(stage=stage, role=role.name, engine=role.engine, model=role.model,
                exit_code=proc.returncode, log=log.name)
    return proc.returncode
