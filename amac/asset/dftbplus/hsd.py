from typing import Any, Mapping


def format_value(value: Any) -> str:
    """Return a scalar value in HSD syntax."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (list, tuple)):
        return " ".join(format_value(item) for item in value)
    return str(value)


def to_hsd(tree: Mapping[str, Any], indent: int = 0) -> str:
    """Write a nested parameter dict as HSD text.

      A node holding a single sub-node is a method choice
      (``{"Hamiltonian": {"DFTB": {...}}}`` -> ``Hamiltonian = DFTB {...}``);
      any other node is a plain block. The key ``<<<`` includes a file.

      Args:
          tree: Nested parameter dict.
          indent: Indentation level of the first line.

      Returns:
          The HSD text.
    """
    pad = "  " * indent
    lines = []
    for key, value in tree.items():
        if key == "<<<":
            lines.append(f'{pad}<<< "{value}"')
        elif isinstance(value, Mapping):
            children = list(value.items())
            if len(children) == 1 and isinstance(children[0][1], Mapping):
                name, body = children[0]
                lines.append(f"{pad}{key} = {name} {{")
            else:
                body = value
                lines.append(f"{pad}{key} {{")
            if body:
                lines.append(to_hsd(body, indent + 1))
            lines.append(f"{pad}}}")
        else:
            lines.append(f"{pad}{key} = {format_value(value)}")
    return "\n".join(lines)



