"""Terminal view of the backlog: every work item, its step and who that step is waiting on."""
from dataclasses import dataclass

from rich.text import Text
from textual.app import App
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Markdown, Static, Tree

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


def rows(repository):
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
            names = list(repository.workflow(record.metadata["workflow"]).steps)
            row.step, row.step_order = step.name, names.index(step.name)
            row.transitions = tuple(step.transitions.items())
            if not step.terminal:
                row.needs_you = step.role is None
                row.waiting_on = "YOU" if row.needs_you else step.role
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
    return Text.assemble(("* " if row.needs_you else "  ", YOU), (f"{row.label:<10}", "bold"), " ",
                         (f"{row.step:<10}", row.style), " ", row.title)


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
        text.append("\nNext        ")
        text.append("   ".join(f"{name} -> {target}" for name, target in row.transitions) or "-", "dim")
    if row.parent:
        text.append(f"\nPart of     {row.parent}")
    return text


class Backlog(App):
    TITLE = "devteam"
    CSS = """
    #summary { height: 1; padding: 0 1; background: $panel; }
    #items { width: 1fr; min-width: 40; border: round $primary; padding: 0 1; overflow-x: hidden; }
    #items:focus-within { border: round $accent; }
    #detail { width: 1fr; border: round $primary; padding: 0 1; }
    #detail:focus { border: round $accent; }
    #card { padding: 1 1 0 1; }
    #body { padding: 0 0 1 0; }
    """
    BINDINGS = [
        ("y", "toggle_mine", "Only waiting on you"),
        ("g", "toggle_group", "Group by step / epic"),
        ("tab", "switch_pane", "Switch pane"),
        ("r", "reload", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, repository):
        super().__init__()
        self.repository = repository
        self.sub_title = repository.root.parent.name
        self.only_mine = False
        self.by_step = False
        self.data = []
        self.selected = None
        self.shown = None
        self.signature = None

    def compose(self):
        yield Header()
        yield Static(id="summary")
        with Horizontal():
            yield Tree("Backlog", id="items")
            with VerticalScroll(id="detail"):
                yield Static(id="card")
                yield Markdown(id="body")
        yield Footer()

    def on_mount(self):
        tree = self.query_one("#items", Tree)
        tree.show_root = False
        tree.guide_depth = 3
        tree.focus()
        self.action_reload()
        self.set_interval(REFRESH_SECONDS, self.action_reload)

    def action_reload(self):
        try:
            data, error = rows(self.repository), None
        except (InvalidRecord, InvalidWorkflow, OSError) as exc:
            data, error = [], str(exc)
        signature = (data, error, self.only_mine, self.by_step)
        if signature == self.signature:
            return
        self.signature, self.data = signature, data
        self.query_one("#summary", Static).update(Text(f"ERROR: {error}", INVALID) if error else summary(data))
        self.rebuild()

    def rebuild(self):
        tree = self.query_one("#items", Tree)
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
            self.call_after_refresh(tree.move_cursor, target)

    def show(self, row):
        if row == self.shown:
            return
        self.shown = row
        self.query_one("#card", Static).update(card(row) if row else Text("Nothing to show.", "dim"))
        self.query_one("#body", Markdown).update(row.body if row and not row.errors else "")

    def on_tree_node_highlighted(self, event):
        if isinstance(event.node.data, Row):
            self.selected = event.node.data.key
            self.show(event.node.data)

    def action_toggle_mine(self):
        self.only_mine = not self.only_mine
        self.action_reload()

    def action_toggle_group(self):
        self.by_step = not self.by_step
        self.action_reload()

    def action_switch_pane(self):
        tree, detail = self.query_one("#items", Tree), self.query_one("#detail", VerticalScroll)
        (detail if tree.has_focus else tree).focus()


def run(repository):
    Backlog(repository).run()
