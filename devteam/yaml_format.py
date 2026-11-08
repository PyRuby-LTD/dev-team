"""The YAML the harness reads and writes: work items, workflows, submissions and standards alike.

Reading is strict, refusing duplicate and non-string keys; writing keeps the house style the examples are written in.
"""
from pydantic import BaseModel
import yaml


class InvalidYaml(ValueError):
    pass


class _Loader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise InvalidYaml("mapping keys must be strings")
            if key in result:
                raise InvalidYaml(f"duplicate key {key!r}; keep one value")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse(text):
    """The document's data; an empty document is an empty mapping."""
    try:
        return yaml.load(text, Loader=_Loader) or {}
    except yaml.YAMLError as exc:
        raise InvalidYaml(str(exc)) from None


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True

    def increase_indent(self, flow=False, indentless=False):
        # Indent lists under their key, as the examples are written.
        return super().increase_indent(flow, False)


def _text(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


_Dumper.add_representer(str, _text)


def to_yaml(value):
    """Models and plain data alike, as the work-item files write them."""
    if isinstance(value, BaseModel):
        value = value.model_dump(exclude_none=True, exclude_defaults=True)
    elif isinstance(value, list):
        value = [v.model_dump(exclude_none=True, exclude_defaults=True) if isinstance(v, BaseModel) else v
                 for v in value]
    return yaml.dump(value, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=float("inf"))
