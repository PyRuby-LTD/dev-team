"""Terminal view of the backlog: every work item, its step and who that step is waiting on."""
import threading
from collections import deque
from dataclasses import dataclass

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, Markdown, OptionList, RichLog, Static, TextArea, Tree
from textual.widgets.option_list import Option

from . import questions
from .backlog import InvalidRecord
from .workflow import InvalidWorkflow

REFRESH_SECONDS = 2
YOU, AGENT, DONE, INVALID = "bold yellow", "cyan", "green", "bold red"


@dataclass
class Row:
    key: str
    label: str
    title: str
    step: str = ""
    step_order: int = 0
    waiting_on: str = ""
    needs_you: bool = False
    depth: int = 0
    body: str = ""
    parent: str = ""
    transitions: tuple = ()
    errors: tuple = ()
    unanswered: int = 0
    running: bool = False
    failure: str = ""
    held: str = ""

    @property
    def is_item(self):
        return bool(self.step) and not self.errors

    @property
    def style(self):
        if self.errors:
            return INVALID
        if self.needs_you:
            return YOU
        return AGENT if self.waiting_on else DONE


def owner_label(step):
    if step.terminal:
        return "finished"
    if step.check:
        return "checks"
    if step.harness:
        return "harness"
    return "YOU" if step.human else step.role


def rows(repository, runner=None):
    """Epics with their descendants, then items without an epic, then files that failed validation."""
    snapshot = repository.scan()
    children = {}
    for record in snapshot.valid.values():
        children.setdefault(record.metadata.get("parent"), []).append(record)
    result = []

    def add(record, depth):
        row = Row(record.id, record.id, record.metadata["title"], depth=depth, body=record.body,
                  parent=record.metadata.get("parent") or "")
        if record.metadata["type"] != "epic":
            step = repository.step(record)
            steps = repository.workflow(record.metadata["workflow"]).steps
            row.step, row.step_order = step.name, list(steps).index(step.name)
            row.transitions = tuple((name, target, owner_label(steps[target])) for name, target in step.transitions.items())
            if not step.terminal:
                row.needs_you = step.human
                row.waiting_on = owner_label(step)
            if row.needs_you:
                row.unanswered = sum(not question.answered for question in questions.parse(record.body))
            if runner is not None and not row.needs_you:
                row.running = runner.active == record.id
                row.failure = runner.failed.get(record.id, "")
                row.held = "" if row.running else runner.waiting.get(record.id, "")
        result.append(row)
        for child in sorted(children.get(record.id, []), key=lambda r: r.id):
            add(child, depth + 1)

    for record in sorted(children.get(None, []), key=lambda r: (r.metadata["type"] != "epic", r.id)):
        add(record, 0)
    for path, errors in sorted(snapshot.errors.items()):
        try:
            name = str(path.relative_to(repository.root))
        except ValueError:
            name = str(path)
        result.append(Row(str(path), name, "; ".join(errors), step="INVALID", errors=tuple(errors)))
    return result


def visible(data, only_mine):
    """With the filter on: the items waiting on the customer, plus the ancestors that give them context."""
    if not only_mine:
        return list(data)
    keep = set()
    for index, row in enumerate(data):
        if row.needs_you or row.errors:
            keep.add(index)
            depth = row.depth
            for above in range(index - 1, -1, -1):
                if data[above].depth < depth:
                    keep.add(above)
                    depth = data[above].depth
    return [row for index, row in enumerate(data) if index in keep]


def summary(data):
    items = [row for row in data if row.is_item]
    mine = sum(row.needs_you for row in items)
    agents = sum(bool(row.waiting_on) and not row.needs_you for row in items)
    text = Text.assemble(
        (f" {mine} waiting on you ", YOU if mine else "dim"), "  ",
        (f"{agents} with agents", AGENT if agents else "dim"), "  ",
        (f"{len(items) - mine - agents} finished", DONE), "  ",
        (f"{len(items)} items", "dim"))
    invalid = sum(bool(row.errors) for row in data)
    if invalid:
        text.append(f"  {invalid} invalid", INVALID)
    return text


def item_label(row, pending=0):
    if row.errors:
        return Text.assemble(("! ", INVALID), (row.label, INVALID), "  ", (row.title, "dim"))
    if not row.step:
        text = Text.assemble((row.label, "bold"), "  ", row.title)
        if pending:
            text.append(f"  ({pending} waiting on you)", YOU)
        return text
    text = Text.assemble(("* " if row.needs_you else "  ", YOU), (f"{row.label:<10}", "bold"), " ",
                         (f"{row.step:<10}", row.style), " ")
    if row.running:
        text.append("running  ", "bold " + AGENT)
    elif row.failure:
        text.append("FAILED  ", INVALID)
    return text.append(row.title)


def card(row):
    if row.errors:
        text = Text.assemble((row.label, INVALID), "\n")
        for error in row.errors:
            text.append(f"\nERROR: {error}", INVALID)
        return text
    text = Text.assemble((row.label, "bold"), "  ", (row.title, "bold"))
    if row.step:
        text.append("\n\nStep        ")
        text.append(row.step, row.style)
        text.append("\nWaiting on  ")
        text.append(row.waiting_on or "nobody; this item is finished", row.style)
        if row.running:
            text.append("  (running now)", "bold " + AGENT)
        text.append("\nNext        ")
        text.append("   ".join(f"{name} -> {target}" for name, target, _ in row.transitions) or "-", "dim")
        if row.failure:
            text.append(f"\n\nThe agent failed: {row.failure}\nPress t to try again.", INVALID)
        if row.held:
            text.append(f"\n\nOn hold: {row.held}", YOU)
        if row.unanswered:
            text.append(f"\n\n{row.unanswered} unanswered question{'s' if row.unanswered != 1 else ''}. Press enter to answer.", YOU)
        elif row.needs_you:
            text.append("\n\nPress enter to choose what happens next.", YOU)
    if row.parent:
        text.append(f"\nPart of     {row.parent}")
    return text


class Actions(ModalScreen):
    """What the customer can do with an item: answer, move it, or step in on a step that is not theirs."""
    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, row):
        super().__init__()
        self.row = row

    def compose(self):
        row = self.row
        options = []
        if row.unanswered:
            options.append(Option(f"Answer {row.unanswered} question{'s' if row.unanswered != 1 else ''}", id="answer"))
        if not row.needs_you and row.waiting_on != "checks":
            label = "Leave a note on the item" if row.waiting_on == "harness" else f"Leave a note for the {row.waiting_on}"
            options.append(Option(label, id="note"))
        for name, target, owner in row.transitions:
            who = {"finished": "it is finished", "YOU": "back to you", "checks": "the checks run", "harness": "the harness runs"}.get(owner, f"the {owner} takes over")
            label = Text.assemble(("" if row.needs_you else "override ", YOU), (name, "bold"), f"  ->  {target}  ", (who, "dim"))
            options.append(Option(label, id=f"move:{name}"))
        with Vertical(classes="dialog"):
            yield Label(Text.assemble((row.label, "bold"), "  ", row.title, f"\nNow at {row.step}."))
            if not row.needs_you:
                yield Label(Text(f"This step belongs to the {row.waiting_on}. You can leave a note for its next run, "
                                 "or override it by choosing the outcome yourself.", YOU))
            if row.unanswered and row.transitions:
                yield Label(Text("Unanswered questions remain; moving on now leaves them blank.", YOU))
            yield OptionList(*options)
            yield Label(Text("enter: choose    esc: cancel", "dim"))

    def on_option_list_option_selected(self, event):
        self.dismiss(event.option.id)


class Answers(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "Cancel"), ("ctrl+s", "save", "Save answers")]

    def __init__(self, row):
        super().__init__()
        self.row = row
        self.open = [(index, question) for index, question in enumerate(questions.parse(row.body)) if not question.answered]

    def compose(self):
        with Vertical(classes="dialog wide"):
            yield Label(Text.assemble((self.row.label, "bold"), "  ", self.row.title))
            with VerticalScroll():
                for number, (index, question) in enumerate(self.open, 1):
                    yield Label(Text(f"{number}. {question.text}", "bold"), shrink=True, classes="question")
                    yield TextArea(id=f"answer-{index}", soft_wrap=True)
            with Horizontal(classes="buttons"):
                yield Button("Save answers (ctrl+s)", variant="primary", id="save")
                yield Button("Cancel (esc)", id="cancel")
            yield Label(Text("tab: next answer    blank answers stay unanswered", "dim"))

    def on_mount(self):
        self.query(TextArea).first().focus()

    def on_resize(self):
        dialog = self.query_one(".dialog")
        # Keep auto height for fitting questions, reserving the title (2),
        # buttons (4), and hint (2) when the dialog reaches its height limit.
        limit = int(dialog.styles.max_height.resolve(self.size, self.app.size))
        self.query_one(VerticalScroll).styles.max_height = max(
            1, min(30, limit - dialog.styles.gutter.height - 8)
        )

    def action_save(self):
        self.dismiss({index: self.query_one(f"#answer-{index}", TextArea).text for index, _ in self.open})

    def on_button_pressed(self, event):
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


class Note(ModalScreen):
    """Feedback on a transition, or on its own (name is None)."""
    BINDINGS = [("escape", "dismiss(None)", "Cancel"), ("ctrl+s", "move", "Move")]

    def __init__(self, row, name, target, owner):
        super().__init__()
        self.row, self.move_name, self.target, self.next_owner = row, name, target, owner

    def compose(self):
        with Vertical(classes="dialog wide"):
            yield Label(Text.assemble((self.row.label, "bold"), "  ", self.row.title))
            moving = self.move_name is not None
            if self.next_owner == "harness":
                description = (f"{self.move_name}  ->  {self.target}; the harness runs." if moving
                               else f"The item stays at {self.row.step}; your note is saved on the item.")
                yield Label(Text(description))
            elif moving:
                yield Label(Text.assemble((self.move_name, "bold"), f"  ->  {self.target}; the {self.next_owner} takes over."))
            else:
                yield Label(Text(f"The item stays at {self.row.step}; the {self.next_owner} reads your note on its next run."))
            question = ("Anything to record for the next steps?" if self.next_owner == "harness"
                        else f"Anything the {self.next_owner} should know or change?")
            question += " (optional)" if moving else ""
            yield Label(Text(question, "bold"), classes="question")
            yield TextArea(id="note", soft_wrap=True)
            with Horizontal(classes="buttons"):
                yield Button("Move (ctrl+s)" if moving else "Save note (ctrl+s)", variant="primary", id="move")
                yield Button("Cancel (esc)", id="cancel")
            hint = "Your note is added to the item under Feedback." + (" Leave it blank to just move." if moving else "")
            yield Label(Text(hint, "dim"))

    def on_mount(self):
        self.query_one(TextArea).focus()

    def action_move(self):
        self.dismiss(self.query_one(TextArea).text)

    def on_button_pressed(self, event):
        if event.button.id == "move":
            self.action_move()
        else:
            self.dismiss(None)


class NewRequest(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "Cancel"), ("ctrl+s", "save", "Create request")]

    def compose(self):
        with Vertical(classes="dialog wide"):
            yield Label("New request: describe your idea, feature or change")
            yield TextArea(id="request-text", soft_wrap=True)
            with Horizontal(classes="buttons"):
                yield Button("Create request (ctrl+s)", variant="primary", id="save")
                yield Button("Cancel (esc)", id="cancel")

    def on_mount(self):
        self.query_one(TextArea).focus()

    def action_save(self):
        text = self.query_one(TextArea).text
        if not text.strip():
            self.notify("Enter some text for the request.", severity="error")
            return
        self.dismiss(text)

    def on_button_pressed(self, event):
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


class Confirm(ModalScreen):
    BINDINGS = [("escape", "dismiss(False)", "No"), ("y", "dismiss(True)", "Yes"), ("n", "dismiss(False)", "No")]

    def __init__(self, message):
        super().__init__()
        self.message = message

    def compose(self):
        with Vertical(classes="dialog"):
            yield Label(self.message)
            yield Label(Text("y: yes    n or esc: no", "dim"))


class ItemTree(Tree):
    BINDINGS = [Binding("enter", "select_cursor", "Answer / move item")]


class Backlog(App):
    TITLE = "devteam"
    CSS = """
    #summary { height: 1; padding: 0 1; background: $panel; }
    #items { width: 1fr; min-width: 40; border: round $primary; padding: 0 1; overflow-x: hidden; }
    #items:focus-within { border: round $accent; }
    #right { width: 1fr; }
    #detail { height: 1fr; border: round $primary; padding: 0 1; }
    #detail:focus { border: round $accent; }
    #output { height: 1fr; border: round $primary; padding: 0 1; }
    #card { padding: 1 1 0 1; }
    #body { padding: 0 0 1 0; }
    #activity { height: 7; border: round $primary; padding: 0 1; }
    ModalScreen { align: center middle; }
    .dialog { width: 70; max-width: 90%; height: auto; max-height: 85%; border: thick $accent; background: $surface; padding: 1 2; }
    .dialog.wide { width: 100; }
    .dialog Label { margin-bottom: 1; }
    .dialog OptionList { height: auto; max-height: 12; margin-bottom: 1; }
    .dialog VerticalScroll { height: auto; max-height: 30; }
    .dialog TextArea { height: 5; margin-bottom: 1; }
    .dialog #note { height: 8; }
    .dialog .question { margin-bottom: 0; }
    .buttons { height: auto; margin-bottom: 1; }
    .buttons Button { margin-right: 2; }
    """
    BINDINGS = [
        ("n", "new_request", "New request"),
        ("y", "toggle_mine", "Only waiting on you"),
        ("g", "toggle_group", "Group by step / epic"),
        ("s", "toggle_agents", "Start / stop agents"),
        ("l", "toggle_output", "Agent output"),
        ("t", "retry", "Retry failed"),
        ("tab", "switch_pane", "Switch pane"),
        ("r", "reload", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, repository, runner=None):
        super().__init__()
        self.repository = repository
        self.runner = runner
        self.stop = threading.Event()
        self.thread = None
        self.sub_title = repository.root.parent.name
        self.only_mine = False
        self.by_step = False
        self.data = []
        self.selected = None
        self.shown = None
        self.restoring = False
        self.signature = None
        self.output_buffer = deque(maxlen=2000)
        self.output_ready = False

    def compose(self):
        yield Header()
        yield Static(id="summary")
        with Horizontal():
            yield ItemTree("Backlog", id="items")
            with Vertical(id="right"):
                with VerticalScroll(id="detail"):
                    yield Static(id="card")
                    yield Markdown(id="body")
                output = RichLog(id="output", auto_scroll=True, max_lines=2000,
                                 markup=False, wrap=True, min_width=1)
                output.display = False
                yield output
        yield RichLog(id="activity", wrap=True, markup=False)
        yield Footer()

    def on_mount(self):
        # Looked up once: while a dialog is open, queries run against the dialog instead.
        self.item_tree = self.query_one("#items", Tree)
        self.summary_bar = self.query_one("#summary", Static)
        self.detail_pane = self.query_one("#detail", VerticalScroll)
        self.card_view = self.query_one("#card", Static)
        self.body_view = self.query_one("#body", Markdown)
        self.agent_log = self.query_one("#activity", RichLog)
        self.output_log = self.query_one("#output", RichLog)
        self.item_tree.show_root = False
        self.item_tree.guide_depth = 3
        self.item_tree.focus()
        if self.runner is not None:
            self.runner.report = lambda message: self.from_agents(self.agent_report, message)
            self.runner.on_line = lambda line: self.from_agents(self.agent_output, line)
        self.agent_log.can_focus = False
        self.output_log.can_focus = False
        self.agents_title()
        self.action_reload()
        self.set_interval(REFRESH_SECONDS, self.action_reload)

    def action_reload(self):
        try:
            data, error = rows(self.repository, self.runner), None
        except (InvalidRecord, InvalidWorkflow, OSError) as exc:
            data, error = [], str(exc)
        signature = (data, error, self.only_mine, self.by_step)
        if signature == self.signature:
            return
        self.signature, self.data = signature, data
        self.summary_bar.update(Text(f"ERROR: {error}", INVALID) if error else summary(data))
        self.rebuild()

    def rebuild(self):
        tree = self.item_tree
        tree.clear()
        shown = visible(self.data, self.only_mine)
        nodes = {}
        if self.by_step:
            groups = {}
            for row in shown:
                if row.step:
                    groups.setdefault((row.step_order if row.is_item else 999, row.step), []).append(row)
            for (_, step), members in sorted(groups.items()):
                who = members[0].waiting_on or ("" if members[0].errors else "finished")
                label = Text.assemble((step, "bold " + members[0].style), f"  ({len(members)})  ", (who, members[0].style))
                group = tree.root.add(label, expand=True)
                for row in members:
                    nodes[row.key] = group.add_leaf(item_label(row), data=row)
        else:
            stack = [tree.root]
            for index, row in enumerate(shown):
                del stack[row.depth + 1:]
                has_children = index + 1 < len(shown) and shown[index + 1].depth > row.depth
                pending = 0
                if not row.step:
                    for below in self.data[self.data.index(row) + 1:]:
                        if below.depth <= row.depth:
                            break
                        pending += below.needs_you
                label = item_label(row, pending)
                node = stack[-1].add(label, data=row, expand=True) if has_children else stack[-1].add_leaf(label, data=row)
                nodes[row.key] = node
                stack.append(node)
        target = nodes.get(self.selected) or next(iter(nodes.values()), None)
        if target is None:
            self.show(None)
        else:
            self.selected = target.data.key
            self.show(target.data)
            self.restoring = True
            self.call_after_refresh(self.restore_cursor, target)

    def restore_cursor(self, node):
        self.item_tree.move_cursor(node)
        self.restoring = False

    def show(self, row):
        if row == self.shown:
            return
        self.shown = row
        self.card_view.update(card(row) if row else Text("Nothing to show.", "dim"))
        self.body_view.update(row.body if row and not row.errors else "")

    def on_tree_node_highlighted(self, event):
        # Rebuilding the tree highlights its first node; that must not replace the user's selection.
        if self.restoring or event.node is not self.item_tree.cursor_node:
            return
        if isinstance(event.node.data, Row):
            self.selected = event.node.data.key
            self.show(event.node.data)

    def check_action(self, action, parameters):
        # Keys typed into a dialog must not reach the main screen's actions.
        return len(self.screen_stack) == 1 or action not in {name for _, name, _ in self.BINDINGS}

    def on_tree_node_selected(self, event):
        row = event.node.data
        if not isinstance(row, Row) or not row.is_item:
            return
        if not row.waiting_on:
            self.notify(f"{row.label} is finished; there is nothing for you to do.")
            return
        if row.running:
            self.notify(f"The {row.waiting_on} is working on {row.label} now. Wait for it to finish, or stop the agents first.")
            return
        self.push_screen(Actions(row), lambda choice: self.chosen(row, choice))

    def chosen(self, row, choice):
        if choice == "answer":
            self.push_screen(Answers(row), lambda answers: self.answered(row, answers))
        elif choice == "note":
            self.push_screen(Note(row, None, None, row.waiting_on), lambda note: self.noted(row, note))
        elif choice:
            name, target, owner = next(move for move in row.transitions if move[0] == choice.removeprefix("move:"))
            steps = self.repository.workflow(self.repository.scan().valid[row.key].metadata["workflow"]).steps
            # A merged PR leads to completion; a rejected PR keeps the feedback prompt.
            if owner in ("YOU", "finished", "checks") or steps[target].action == "merged":
                self.move(row, name, "")
            else:
                self.push_screen(Note(row, name, target, owner),
                                 lambda note: None if note is None else self.move(row, name, note))

    def noted(self, row, note):
        if not note or not note.strip():
            return
        current = self.repository.scan().valid.get(row.key)
        if current is None or current.body != row.body:
            self.notify(f"{row.label} changed while you were writing; nothing was saved.", severity="error")
            return
        body = questions.add_feedback(row.body, f"note at {row.step}", note)
        if self.attempt(lambda: self.repository.write_body(row.key, body, "note")):
            self.notify(f"Note saved for the {row.waiting_on}." + (" Press t to run it again." if row.failure else ""))

    def move(self, row, name, note):
        current = self.repository.scan().valid.get(row.key)
        if note.strip() and (current is None or current.body != row.body):
            self.notify(f"{row.label} changed while you were writing; nothing was moved.", severity="error")
            return
        self.attempt(lambda: self.repository.transition(row.key, name, note))

    def answered(self, row, answers):
        if not answers or not any(text.strip() for text in answers.values()):
            return
        current = self.repository.scan().valid.get(row.key)
        if current is None or current.body != row.body:
            self.notify(f"{row.label} changed while you were answering; nothing was saved.", severity="error")
            return
        if self.attempt(lambda: self.repository.write_body(row.key, questions.answer(row.body, answers), "answers")):
            fresh = next((item for item in self.data if item.key == row.key), None)
            if fresh is not None and fresh.needs_you:
                self.push_screen(Actions(fresh), lambda choice: self.chosen(fresh, choice))

    def attempt(self, change):
        try:
            change()
        except (InvalidRecord, InvalidWorkflow, OSError) as exc:
            self.notify(str(exc), severity="error")
            return False
        finally:
            self.action_reload()
        return True

    def agents_title(self):
        log = self.agent_log
        if self.runner is None:
            log.border_title = "Agents: not available"
        elif self.thread is not None and not self.stop.is_set():
            log.border_title = "Agents: running - s to stop"
        else:
            log.border_title = "Agents: stopped - s to start; agent-owned steps wait until then"

    def agent_report(self, message):
        self.agent_log.write(message)
        self.action_reload()

    def agent_output(self, line):
        if self.output_ready:
            self.output_log.write(line)
        else:
            self.output_buffer.append(line)

    def action_toggle_output(self):
        self.output_ready = False
        self.output_log.display = not self.output_log.display
        if self.output_log.display:
            self.call_after_refresh(self.flush_output)

    def flush_output(self):
        # Wait for the shown pane's layout before wrapping; arrivals meanwhile stay ordered.
        if not self.output_log.display:
            return
        while self.output_buffer:
            self.output_log.write(self.output_buffer.popleft())
        self.output_ready = True

    def agent_loop(self):
        while not self.stop.is_set():
            ran = 0
            try:
                for record, step in self.runner.pending():
                    if self.stop.is_set():
                        break
                    ran += self.runner.run_item(record, step)
            except Exception as exc:
                self.runner.report(f"agents stopped after an error: {exc}")
                self.stop.set()
            if not ran:
                self.stop.wait(REFRESH_SECONDS)
        self.thread = None
        self.from_agents(self.agents_title)

    def from_agents(self, callback, *args):
        # The agent thread can outlive the screen; a report after shutdown has nowhere to go.
        if self.is_running:
            try:
                self.call_from_thread(callback, *args)
            except RuntimeError:
                pass

    def on_unmount(self):
        self.stop.set()

    def action_toggle_agents(self):
        if self.runner is None:
            return
        if self.thread is not None:
            self.stop.set()
            if self.runner.active:
                self.notify(f"Stopping once the agent on {self.runner.active} finishes.")
        else:
            self.stop = threading.Event()
            self.thread = threading.Thread(target=self.agent_loop, daemon=True)
            self.thread.start()
        self.agents_title()

    def action_new_request(self):
        self.push_screen(NewRequest(), self.create_request)

    def create_request(self, text):
        if text is None or not text.strip():
            return
        title = text.lstrip().splitlines()[0].strip()[:80]
        self.attempt(lambda: self.repository.create("request", title, text))

    def action_retry(self):
        row = self.shown
        if self.runner is not None and row is not None and self.runner.failed.get(row.key):
            self.runner.retry(row.key)
            self.action_reload()

    def action_quit(self):
        if self.runner is not None and self.runner.active:
            message = f"An agent is still working on {self.runner.active}. Quit and abandon that run?"
            self.push_screen(Confirm(message), lambda yes: self.exit() if yes else None)
        else:
            self.exit()

    def action_toggle_mine(self):
        self.only_mine = not self.only_mine
        self.action_reload()

    def action_toggle_group(self):
        self.by_step = not self.by_step
        self.action_reload()

    def action_switch_pane(self):
        tree, detail = self.item_tree, self.detail_pane
        (detail if tree.has_focus else tree).focus()


def run(repository, runner=None):
    Backlog(repository, runner).run()
