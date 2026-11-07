"""The strict YAML loader that work items, workflows and submissions are read with, and work-item IDs."""
import re

import yaml


class InvalidRecord(ValueError):
    pass


class StrictLoader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise InvalidRecord("mapping keys must be strings")
            if key in result:
                raise InvalidRecord(f"duplicate key {key!r}; keep one value")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


ID = re.compile(r"[A-Z][A-Z0-9]*-[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def valid_id(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None
