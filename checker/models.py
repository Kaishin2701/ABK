from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class CheckIssue:
    code: str
    severity: str
    case_name: str
    title: str
    found: str
    expected: str
    explanation: str

    @property
    def detail(self) -> str:
        return f"Found: {self.found}\nExpected: {self.expected}\nExplanation: {self.explanation}"

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["detail"] = self.detail
        return data


def make_issue(
    code: str,
    severity: str,
    case_name: str,
    title: str,
    found: str,
    expected: str,
    explanation: str,
) -> dict[str, str]:
    return CheckIssue(
        code=code,
        severity=severity,
        case_name=case_name,
        title=title,
        found=found,
        expected=expected,
        explanation=explanation,
    ).to_dict()
