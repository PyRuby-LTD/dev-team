import shlex
import subprocess
from pathlib import Path
from threading import Lock, Thread
from collections.abc import Callable

from .config import Role
from .render import STREAMS


def build_argv(role: Role, prompt: str, cwd: Path, extra_dir: Path) -> list[str]:
    brief = role.brief()
    # An engine with no system-prompt flag still needs the brief, so it leads the prompt.
    if not any("{brief}" in arg for arg in role.command):
        prompt = brief + "\n\n" + prompt
    values = {
        "prompt": prompt,
        "model": role.model,
        "brief": brief,
        "cwd": str(cwd),
        "extra_dir": str(extra_dir),
        "permission": role.permission,
        "max_turns": str(role.max_turns),
    }
    return [arg.format_map(values) if "{" in arg else arg for arg in role.command]


def run(role: Role, prompt: str, cwd: Path, extra_dir: Path, log: Path,
        *, on_line: Callable[[str], None] | None = None) -> tuple[int, str]:
    """Drain both pipes live, keeping raw output in log and stdout as the reply source."""
    argv = build_argv(role, prompt, cwd, extra_dir)
    header = f"# {role.name} via {role.engine} ({role.model})\n# cwd: {cwd}\n# {shlex.join(argv)}\n\n"
    renderer, extract_reply = STREAMS.get(role.stream, STREAMS["text"])
    stdout = []
    lock = Lock()
    with log.open("w") as transcript:
        transcript.write(header)
        transcript.flush()
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            transcript.write(f"could not start {argv[0]}: {exc}\n")
            return 127, ""

        def drain(pipe, reply_source):
            with pipe:
                for line in pipe:
                    # Serialize the log and listener so they observe the same arrival order.
                    with lock:
                        transcript.write(line)
                        transcript.flush()
                        if reply_source:
                            stdout.append(line)
                        if on_line is not None:
                            try:
                                rendered = renderer(line)
                            except Exception:
                                continue
                            for part in (rendered or "").splitlines():
                                try:
                                    on_line(part)
                                except Exception:
                                    pass

        readers = [Thread(target=drain, args=(proc.stdout, True)),
                   Thread(target=drain, args=(proc.stderr, False))]
        for reader in readers:
            reader.start()
        for reader in readers:
            reader.join()
        code = proc.wait()
    return extract_reply(code, "".join(stdout))
