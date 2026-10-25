"""A customer's checkout claim and the product process it owns."""
import os
import signal
import subprocess
import threading
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from . import git
from .config import ROOT
from .initialise import has_target

STOP_SECONDS = 5


def load_command():
    return list(tomllib.loads((ROOT / "config" / "roles.toml").read_text())["run"]["command"])


def group_alive(pgid):
    # On Linux an orphaned zombie can retain its process group until init reaps
    # it. It cannot run or hold a port, and must not keep the checkout claimed.
    proc = Path("/proc")
    if proc.is_dir():
        for path in proc.glob("[0-9]*/stat"):
            try:
                fields = path.read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == pgid and fields[0] != "Z":
                    return True
            except (OSError, ValueError, IndexError):
                continue
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


class Tryout:
    def __init__(self, runner, command=None):
        self.runner = runner
        self.command = command
        self.item_id = None
        self.step = None
        self.status = ""
        self.process = None
        self.stopping = None
        self.interrupted = None
        self.exited = False
        self.dirty_release = False

    def say(self, message):
        self.runner.report(message)

    def request(self, item_id):
        with self.runner.lock:
            if self.item_id:
                self.say(f"Already trying out or waiting to try out {self.item_id}; release it first.")
                return False
            record = self.runner.repository.scan().valid.get(item_id)
            if record is None or record.metadata.get("step") not in {"accept", "pull-request"}:
                self.say("Try-out is available only at accept or pull-request.")
                return False
            self.item_id, self.step = item_id, record.metadata["step"]
            self.exited = False
            self.status = f"{item_id}: try-out requested; waiting for the checkout"
            self.tick()
            return True

    def tick(self):
        # Runner owns these errors and imports Tryout during module loading.
        from .runner import StepFailed, Waiting

        with self.runner.lock:
            if not self.item_id:
                if self.dirty_release and git.clean(self.runner.checkout):
                    self.dirty_release = False
                    self.status = ""
                return
            if self.stopping is not None:
                return
            record = self.runner.repository.scan().valid.get(self.item_id)
            if record is None or record.metadata.get("step") != self.step:
                self.release()
                return
            if self.process is not None:
                code = self.process.poll()
                if code is not None and not self.exited:
                    self.exited = True
                    self.status = f"{self.item_id}: product exited ({code}); checkout claimed until release"
                    self.say(self.status)
                return
            if self.runner.checkout_user is not None:
                return
            if self.runner.checkout is None:
                self.cannot_run("try-out needs a git repository")
                return
            if not git.clean(self.runner.checkout):
                self.status = f"{self.item_id}: try-out waiting because the checkout has uncommitted changes"
                return
            try:
                current = git.current_branch(self.runner.checkout)
                holder = self.runner.checkout_holder(current)
                self.interrupted = (holder.id if holder is not None
                                    and holder.id not in self.runner._failed
                                    and self.runner._runs.get(holder.id, 0) < self.runner.max_runs else None)
                self.runner.take_checkout(record, tryout=True)
                command = self.command if self.command is not None else load_command()
                if not command:
                    raise ValueError("empty run command")
                if command[0] == "make" and len(command) == 2:
                    makefile = self.runner.checkout / "Makefile"
                    if not makefile.is_file() or not has_target(makefile.read_text(), command[1]):
                        raise ValueError(f"Makefile has no {command[1]} target")
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                log = self.runner.repository.root / "log" / self.item_id / f"run-{stamp}.log"
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("w") as output:
                    output.write(f"# {' '.join(command)}\n# cwd: {self.runner.checkout}\n\n")
                    output.flush()
                    self.process = subprocess.Popen(command, cwd=self.runner.checkout, stdout=output,
                                                    stderr=subprocess.STDOUT, start_new_session=True)
                self.status = f"Trying out {self.item_id}; output: {log}"
                self.say(self.status)
            except Waiting as exc:
                self.status = f"{self.item_id}: try-out {exc}"
            except (StepFailed, OSError, ValueError, KeyError, git.GitError) as exc:
                self.cannot_run(str(exc))

    def cannot_run(self, reason):
        self.say(f"{self.item_id}: cannot run product: {reason}; checkout released")
        self.finish()

    def release(self):
        with self.runner.lock:
            if self.item_id is None:
                return None
            if self.stopping is not None:
                return self.stopping
            if self.process is None:
                self.finish()
                return None
            self.status = f"{self.item_id}: product stopping"
            self.say(self.status)
            self.stopping = threading.Thread(target=self.stop_group, daemon=True)
            self.stopping.start()
            return self.stopping

    def stop_group(self):
        pgid = self.process.pid
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + STOP_SECONDS
        while group_alive(pgid):
            self.process.poll()
            if time.monotonic() >= deadline:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(0.02)
        self.process.wait()
        with self.runner.lock:
            self.finish()

    def finish(self):
        if self.interrupted:
            self.runner.checkout_priority = self.interrupted
        self.interrupted = None
        self.item_id = self.step = self.process = self.stopping = None
        self.dirty_release = self.runner.checkout is not None and not git.clean(self.runner.checkout)
        self.status = ("Checkout has uncommitted changes; checkout steps wait until it is clean."
                       if self.dirty_release else "")
        if self.status:
            self.say(self.status)
