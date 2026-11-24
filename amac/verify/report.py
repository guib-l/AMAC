"""Structured result of the AMAC installation check."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ICONS = {"ok": "✔", "warn": "⚠", "fail": "✘", "skip": "–"}
STATUSES = tuple(ICONS)

# ANSI styles used by Report.render(color=True).
COLORS = {"ok": "\033[32m", "warn": "\033[33m", "fail": "\033[31m", "skip": "\033[2m"}
BOLD = "\033[1m"
RESET = "\033[0m"


def worst_status(checks: list[Check]) -> str:
    """Worst status of a group: ``fail`` > ``warn`` > ``ok`` > ``skip``."""
    statuses = {check.status for check in checks}
    for status in ("fail", "warn", "ok"):
        if status in statuses:
            return status
    return "skip"


@dataclass(frozen=True)
class Check:
    """One line of the report.

    Attributes:
        scope: What is checked: ``"core"``, or a software name.
        name: Short check name (``"python"``, ``"executable"``, ...).
        status: ``"ok"``, ``"warn"``, ``"fail"`` or ``"skip"``.
        message: Version, path, or reason; empty when nothing is useful to say.
    """

    scope: str
    name: str
    status: str
    message: str = ""


@dataclass
class Report:
    """Ordered list of checks, usable in tests and serialisable to JSON."""

    checks: list[Check] = field(default_factory=list)

    def add(self, scope: str, name: str, status: str, message: str = "") -> None:
        """Append one check; raise ``ValueError`` on an unknown status."""
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}; expected one of {STATUSES}")
        self.checks.append(Check(scope, name, status, message))

    @property
    def failed(self) -> bool:
        """True if at least one check is ``"fail"`` (warnings do not count)."""
        return any(check.status == "fail" for check in self.checks)

    def counts(self) -> dict[str, int]:
        """Number of checks per status."""
        return {status: sum(check.status == status for check in self.checks) for status in STATUSES}

    def scopes(self) -> dict[str, list[Check]]:
        """Checks grouped by scope, in the order they were added."""
        groups: dict[str, list[Check]] = {}
        for check in self.checks:
            groups.setdefault(check.scope, []).append(check)
        return groups

    def to_dict(self) -> dict:
        """Return a JSON-serialisable view (used by ``--json``)."""
        return {
            "ready": not self.failed,
            "summary": self.counts(),
            "software": {
                scope: worst_status(checks)
                for scope, checks in self.scopes().items()
                if scope != "core"
            },
            "checks": [asdict(check) for check in self.checks],
        }

    def render(self, *, color: bool = False, title: str | None = None) -> str:
        """Return the human-readable report: one block per scope, then a summary.

        Each block starts with the worst status of the scope and its name;
        its checks are indented below. A hint after `` → `` in a message
        (e.g. an install command) goes on its own line.

        Args:
            color: Use ANSI colors (only for a terminal).
            title: First line of the report, omitted when None.
        """
        if not self.checks:
            return "no checks"

        def paint(text: str, status: str) -> str:
            return f"{COLORS[status]}{text}{RESET}" if color else text

        def bold(text: str) -> str:
            return f"{BOLD}{text}{RESET}" if color else text

        name_width = max(len(check.name) for check in self.checks)
        indent = " " * (4 + 2 + name_width + 2)
        lines = [bold(title), ""] if title else []
        for scope, checks in self.scopes().items():
            status = worst_status(checks)
            lines.append(f"{paint(ICONS[status], status)} {bold(scope)}")
            for check in checks:
                message, _, hint = check.message.partition(" → ")
                lines.append(
                    f"    {paint(ICONS[check.status], check.status)} "
                    f"{check.name:<{name_width}}  {message}".rstrip()
                )
                if hint:
                    lines.append(f"{indent}{paint('→ ' + hint, 'skip')}")
            lines.append("")

        counts = self.counts()
        summary = "   ".join(
            paint(f"{counts[status]} {ICONS[status]}", status) for status in STATUSES
        )
        verdict = paint("not ready", "fail") if self.failed else paint("ready", "ok")
        lines.append("─" * 45)
        lines.append(f"{summary}     {verdict}")
        return "\n".join(lines)
