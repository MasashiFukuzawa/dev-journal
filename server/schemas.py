from pydantic import BaseModel


class DayMeta(BaseModel):
    date: str
    issue_count: int
    phase_count: int


class Decision(BaseModel):
    kind: str
    title: str
    reason: str


class DeepDive(BaseModel):
    background: str
    decisions: list[Decision]
    constraints: list[str]
    future: list[str]


class IssueItem(BaseModel):
    issue_number: int
    repo: str
    title: str
    url: str
    closed_at: str
    labels: list[str]
    deep_dive: DeepDive | None
    is_confirmed: bool = False


class IssueComment(BaseModel):
    author: str
    body: str
    created_at: str


class IssueItemFull(BaseModel):
    issue_number: int
    repo: str
    title: str
    body: str | None
    url: str
    closed_at: str
    labels: list[str]
    deep_dive: DeepDive | None
    comments: list[IssueComment]


class PhaseGroup(BaseModel):
    name: str | None
    order: int
    issues: list[IssueItem]


class DayDetail(BaseModel):
    date: str
    phases: list[PhaseGroup]
