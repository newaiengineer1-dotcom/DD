from dataclasses import dataclass, asdict, field


@dataclass
class QAResult:
    check_id: str
    agent: str
    status: str            # pass | warn | fail
    detail: str
    workstream: str = "ALL"
    refs: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
