"""The customer's view of the YAML backlog: where each item stands, and the outcomes, feedback and requests only they give."""
from dataclasses import dataclass
import threading

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, Markdown, OptionList, RichLog, TextArea, Tree
from textual.widgets.option_list import Option

from .harness import record_customer
from .template import InvalidTemplate, Templates
from .steps import REQUIREMENTS, InvalidStep
from .work_item import InvalidWorkItem

REFRESH_SECONDS = 2
YOU, AGENT, DONE, INVALID = "bold yellow", "cyan", "green", "bold red"


@dataclass(frozen=True)
class Row:
    key: str
    label: str
    title: str
    depth: int = 0
    step: str = ""
    waiting_on: str = ""
    needs_you: bool = False
    errors: tuple = ()
    failure: str = ""
    waiting: str = ""

    @property
    def style(self):
        if self.errors or self.failure:
            return INVALID
        if self.needs_you:
            return YOU
        return AGENT if self.waiting_on else DONE


def rows(backlog, failed=None, waiting=None):
    """Epics with their descendants, then items outside any epic, then files that failed to load."""
    snapshot = backlog.scan()
    items = snapshot.valid
    children = {}
    for item in items.values():
        children.setdefault(item.parent if item.parent in items else None, []).append(item)
    result = []

    def add(item, depth):
        if item.workflow is None:
            result.append(Row(item.id, item.id, item.title, depth))
        else:
            step = backlog.step(item)
            result.append(Row(item.id, item.id, item.title, depth, step.name,
                              "" if step.terminal else step.label(), step.needs_you,
                              failure=(failed or {}).get(item.id, ""), waiting=(waiting or {}).get(item.id, "")))
        for child in sorted(children.get(item.id, []), key=lambda child: child.id):
            add(child, depth + 1)

    for item in sorted(children.get(None, []), key=lambda item: (item.type != "epic", item.id)):
        add(item, 0)
    for path, errors in sorted(snapshot.errors.items()):
        try:
            name = str(path.relative_to(backlog.root))
        except ValueError:
            name = str(path)
        result.append(Row(str(path), name, "; ".join(errors), errors=tuple(errors)))
    return result


def visible(data, only_mine):
    """With the filter on: the items waiting on the customer and invalid files, with the ancestors that place them."""
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


def item_label(row):
    if row.errors:
        return Text.assemble(("! ", INVALID), (row.label, INVALID), "  ", (row.title, "dim"))
    if not row.step:
        return Text.assemble((row.label, "bold"), "  ", row.title)
    text = Text.assemble(("* " if row.needs_you else "  ", YOU), (f"{row.label:<12}", "bold"), " ",
                         (f"{row.step:<12}", row.style), " ", (f"{row.waiting_on or 'finished':<16}", row.style), " ")
    if row.failure:
        text.append("FAILED  ", INVALID)
    text.append(row.title)
    if row.waiting:
        text.append(f"  ({row.waiting})", "dim")
    return text


def takes_feedback(step):
    return isinstance(step.output, dict) and "feedback" in step.output.get("properties", {})


def takes_answers(step):
    return step.output == REQUIREMENTS or (isinstance(step.output, dict) and "questions" in step.output.get("properties", {}))


def unanswered(item):
    return [question.question for question in item.questions or [] if not question.answer]


class Outcomes(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, item, step):
        super().__init__()
        self.item, self.step = item, step

    def compose(self):
        options = [Option(Text.assemble((outcome.name, "bold"), f"  ->  {outcome.next}\n", (outcome.means, "dim")),
                          id=outcome.name)
                   for outcome in self.step.outcomes.values()]
        with Vertical(classes="dialog"):
            yield Label(Text.assemble((self.item.id, "bold"), "  ", self.item.title, f"\nAt {self.step.name}."))
            yield OptionList(*options)
            yield Label(Text("enter: choose    esc: cancel", "dim"))

    def on_option_list_option_selected(self, event):
        self.dismiss(event.option.id)


class Answers(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "Cancel"), ("ctrl+s", "save", "Save")]

    def __init__(self, heading, questions):
        super().__init__()
        self.heading, self.questions = heading, questions

    def compose(self):
        with Vertical(classes="dialog wide"):
            yield Label(self.heading)
            with VerticalScroll(classes="answers"):
                for number, question in enumerate(self.questions, 1):
                    yield Label(Text(f"{number}. {question}", "bold"), shrink=True, classes="question")
                    yield TextArea(soft_wrap=True)
            with Horizontal(classes="buttons"):
                yield Button("Save answers (ctrl+s)", variant="primary", id="save")
                yield Button("Cancel (esc)", id="cancel")
            yield Label(Text("tab: next answer    every question needs an answer; write n/a to pass on one", "dim"))

    def on_mount(self):
        self.query(TextArea).first().focus()

    def action_save(self):
        answers = [area.text.strip() for area in self.query(TextArea)]
        if not all(answers):
            self.notify("Answer every question first; write n/a for any you will not answer.", severity="error")
            return
        self.dismiss([{"question": question, "answer": answer} for question, answer in zip(self.questions, answers)])

    def on_button_pressed(self, event):
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


class FreeText(ModalScreen):
    BINDINGS = [("escape", "dismiss(None)", "Cancel"), ("ctrl+s", "save", "Save")]

    def __init__(self, heading, action, hint="", required=False):
        super().__init__()
        self.heading, self.action, self.hint, self.required = heading, action, hint, required

    def compose(self):
        with Vertical(classes="dialog wide"):
            yield Label(self.heading)
            yield TextArea(soft_wrap=True)
            with Horizontal(classes="buttons"):
                yield Button(f"{self.action} (ctrl+s)", variant="primary", id="save")
                yield Button("Cancel (esc)", id="cancel")
            if self.hint:
                yield Label(Text(self.hint, "dim"))

    def on_mount(self):
        self.query_one(TextArea).focus()

    def action_save(self):
        text = self.query_one(TextArea).text
        if self.required and not text.strip():
            self.notify("Write something first.", severity="error")
            return
        self.dismiss(text)

    def on_button_pressed(self, event):
        if event.button.id == "save":
            self.action_save()
        else:
            self.dismiss(None)


class ItemTree(Tree):
    BINDINGS = [Binding("enter", "select_cursor", "Choose an outcome")]


class Console(App):
    TITLE = "dev-team"
    CSS = """
    #items { width: 1fr; min-width: 40; border: round $primary; padding: 0 1; overflow-x: hidden; }
    #items:focus-within { border: round $accent; }
    #detail { width: 1fr; border: round $primary; padding: 0 1; }
    #detail:focus { border: round $accent; }
    #stream { height: 10; border: round $primary; padding: 0 1; }
    #activity { height: 7; border: round $primary; padding: 0 1; }
    ModalScreen { align: center middle; }
    .dialog { width: 80; max-width: 90%; height: auto; max-height: 85%; border: thick $accent;
              background: $surface; padding: 1 2; }
    .dialog.wide { width: 100; }
    .dialog Label { margin-bottom: 1; }
    .dialog OptionList { height: auto; max-height: 20; margin-bottom: 1; }
    .dialog TextArea { height: 8; margin-bottom: 1; }
    .dialog .answers { height: auto; max-height: 24; }
    .dialog .answers TextArea { height: 4; }
    .dialog .question { margin-bottom: 0; }
    .buttons { height: auto; margin-bottom: 1; }
    .buttons Button { margin-right: 2; }
    """
    BINDINGS = [
        ("n", "new_request", "New request"),
        ("y", "toggle_mine", "Only waiting on you"),
        ("tab", "switch_pane", "Switch pane"),
        ("r", "reload", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, backlog, harness=None, templates=None):
        super().__init__()
        self.backlog = backlog
        self.harness = harness
        self.templates = templates or (harness.templates if harness else Templates())
        self.stop = threading.Event()
        self.only_mine = False
        self.data = []
        self.shown_rows = []
        self.selected = None
        self.signature = None
        self.restoring = False
        self.detail_text = None

    def compose(self):
        yield Header()
        with Horizontal():
            yield ItemTree("Backlog", id="items")
            with VerticalScroll(id="detail"):
                yield Markdown(id="detail-body")
        yield RichLog(id="stream", wrap=True, markup=False, max_lines=2000)
        yield RichLog(id="activity", wrap=True, markup=False)
        yield Footer()

    def on_mount(self):
        # Looked up once: while a dialog is open, queries run against the dialog instead.
        self.item_tree = self.query_one("#items", Tree)
        self.detail_pane = self.query_one("#detail", VerticalScroll)
        self.detail_view = self.query_one("#detail-body", Markdown)
        self.activity = self.query_one("#activity", RichLog)
        self.activity.can_focus = False
        self.agent_stream = self.query_one("#stream", RichLog)
        self.agent_stream.border_title = "Agent stream"
        self.item_tree.show_root = False
        self.item_tree.guide_depth = 3
        self.item_tree.focus()
        self.backlog.notice = self.notify
        self.action_reload()
        self.set_interval(REFRESH_SECONDS, self.action_reload)
        if self.harness is None:
            self.activity.border_title = "Harness: not running"
        else:
            self.activity.border_title = "Harness"
            self.harness.report = lambda message: self.from_harness(self.reported, message)
            self.harness.backlog.notice = lambda message: self.from_harness(self.notify, message)
            self.harness.on_line = lambda item_id, line: self.from_harness(self.agent_stream.write, f"{item_id} | {line}")
            threading.Thread(target=self.harness.run, kwargs={"interval": REFRESH_SECONDS, "stop": self.stop},
                             daemon=True).start()

    def on_unmount(self):
        self.stop.set()

    def from_harness(self, callback, *args):
        # The harness thread can outlive the screen; a report after shutdown has nowhere to go.
        if self.is_running:
            try:
                self.call_from_thread(callback, *args)
            except RuntimeError:
                pass

    def reported(self, message):
        self.activity.write(message)
        self.action_reload()

    def action_reload(self):
        try:
            data, error = rows(self.backlog, *((dict(self.harness.failed), dict(self.harness.waiting))
                                               if self.harness else ())), None
        except (InvalidWorkItem, OSError) as exc:
            data, error = [], str(exc)
        signature = (data, error, self.only_mine)
        if signature == self.signature:
            self.show(self.selected)
            return
        self.signature, self.data = signature, data
        if error:
            self.notify(error, severity="error")
        self.rebuild()

    def rebuild(self):
        tree = self.item_tree
        tree.clear()
        self.shown_rows = visible(self.data, self.only_mine)
        nodes = {}
        stack = [tree.root]
        for index, row in enumerate(self.shown_rows):
            del stack[row.depth + 1:]
            parent = index + 1 < len(self.shown_rows) and self.shown_rows[index + 1].depth > row.depth
            node = stack[-1].add(item_label(row), data=row, expand=True) if parent \
                else stack[-1].add_leaf(item_label(row), data=row)
            nodes[row.key] = node
            stack.append(node)
        self.nodes = nodes
        target = nodes.get(self.selected) or next(iter(nodes.values()), None)
        self.selected = target.data.key if target else None
        self.show(self.selected)
        if target is not None:
            self.restoring = True
            self.call_after_refresh(self.restore_cursor, target)

    def restore_cursor(self, node):
        self.item_tree.move_cursor(node)
        self.restoring = False

    def select(self, key):
        """Move the cursor to the row and show it, as the customer would with the arrow keys."""
        node = self.nodes[key]
        self.selected = key
        self.item_tree.move_cursor(node)
        self.show(key)

    def row(self, key):
        return next((row for row in self.shown_rows if row.key == key), None)

    def show(self, key):
        text = self.detail(self.row(key))
        # Updating the Markdown on every refresh would throw away the customer's scroll position.
        if text != self.detail_text:
            self.detail_text = text
            self.detail_view.update(text)

    def detail(self, row):
        if row is None:
            return "_Nothing to show._"
        if row.errors:
            return f"# {row.label}\n\n" + "\n".join(f"- {error}" for error in row.errors)
        try:
            item = self.backlog.get(row.key)
            step = self.backlog.step(item) if item.workflow else None
            return self.templates.detail(item, step, self.backlog)
        except (InvalidWorkItem, InvalidTemplate, OSError) as exc:
            return f"# {row.label}\n\nCannot show this item: {exc}"

    def on_tree_node_highlighted(self, event):
        # Rebuilding the tree highlights its first node; that must not replace the customer's selection.
        if self.restoring or event.node is not self.item_tree.cursor_node or not isinstance(event.node.data, Row):
            return
        self.selected = event.node.data.key
        self.show(self.selected)

    def check_action(self, action, parameters):
        # Keys typed into a dialog must not reach the main screen's actions.
        return len(self.screen_stack) == 1 or action not in {name for _, name, _ in self.BINDINGS}

    def on_tree_node_selected(self, event):
        row = event.node.data
        if not isinstance(row, Row) or not row.step:
            return
        if not row.needs_you:
            self.notify(f"{row.label} is finished." if not row.waiting_on
                        else f"{row.label} is waiting on {row.waiting_on}, not you.")
            return
        try:
            item = self.backlog.get(row.key)
            step = self.backlog.step(item)
        except InvalidWorkItem as exc:
            self.notify(str(exc), severity="error")
            return
        questions = unanswered(item) if takes_answers(step) else []
        if questions:
            heading = Text.assemble((item.id, "bold"), "  ", item.title, f"\nAnswer the questions at {step.name}.")
            self.push_screen(Answers(heading, questions), lambda answers: self.answered(item, step, answers))
        else:
            self.answered(item, step, [])

    def answered(self, item, step, answers):
        if answers is None:
            return
        output = {"questions": answers} if answers else {}
        self.push_screen(Outcomes(item, step), lambda outcome: self.chosen(item, step, outcome, output))

    def chosen(self, item, step, outcome, output):
        if outcome is None:
            return
        if not takes_feedback(step):
            self.record(item, step, outcome, output)
            return
        heading = Text.assemble((item.id, "bold"), f"  {outcome}  ->  {step.outcomes[outcome].next}\n\n",
                                ("Feedback for the next step (optional)", "bold"))

        def given(text):
            if text is not None:
                self.record(item, step, outcome, {**output, "feedback": text.strip()} if text.strip() else output)
        self.push_screen(FreeText(heading, "Record", "Leave it blank to just move on."), given)

    def record(self, item, step, outcome, output):
        try:
            if self.backlog.get(item.id).step != step.name:
                raise InvalidStep(f"{item.id} moved on while you were choosing; nothing was recorded")
            updated = record_customer(self.backlog, item.id, outcome, output)
        except (InvalidWorkItem, InvalidStep, OSError) as exc:
            self.notify(str(exc), severity="error")
        else:
            self.activity.write(f"{item.id} {step.name}: {outcome} -> {updated.step}")
        self.action_reload()

    def action_new_request(self):
        heading = "New request: describe your idea, feature or change"
        self.push_screen(FreeText(heading, "Capture request", required=True), self.capture)

    def capture(self, text):
        if text is None or not text.strip():
            return
        title = text.strip().splitlines()[0].strip()[:80]
        try:
            item = self.backlog.create("request", title, {"overview": text.strip()})
        except (InvalidWorkItem, InvalidStep, OSError) as exc:
            self.notify(str(exc), severity="error")
        else:
            self.activity.write(f"{item.id}: captured at {item.step}")
            self.selected = item.id
        self.action_reload()

    def action_toggle_mine(self):
        self.only_mine = not self.only_mine
        self.action_reload()

    def action_switch_pane(self):
        (self.detail_pane if self.item_tree.has_focus else self.item_tree).focus()


def run(backlog, harness=None):
    Console(backlog, harness).run()
