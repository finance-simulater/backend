from dataclasses import dataclass


@dataclass(frozen=True)
class Loan:
    id: int
    user_id: int
    amount: int
    status: str
