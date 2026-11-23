"""Structured result of the AMAC installation check."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ICONS = {"ok": "✔", "warn": "⚠", "fail": "✘", "skip": "–"}
STATUSES = tuple(ICONS)


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

    def render(self) -> str:
        """Return the human-readable table, one line per check."""
        if not self.checks:
            return "no checks"
        scope_width = max(len(check.scope) for check in self.checks)
        name_width = max(len(check.name) for check in self.checks)
        lines = [
            (
                f"{check.scope:<{scope_width}}  {ICONS[check.status]}  "
                f"{check.name:<{name_width}}  {check.message}"
            ).rstrip()
            for check in self.checks
        ]
        return "\n".join(lines)
