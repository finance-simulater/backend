from sqlalchemy import (
    BigInteger,
    Column,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (UniqueConstraint("active_user_id", name="uq_loans_one_active_per_user"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    applied_credit_grade = Column(String(2), ForeignKey("credit_grade_policy.grade"), nullable=False)
    applied_credit_score = Column(Integer, nullable=False)
    applied_limit = Column(Integer, nullable=False)
    interest_rate = Column(Numeric(4, 2), nullable=False)
    principal = Column(Integer, nullable=False)
    duration_months = Column(Integer, nullable=False)
    monthly_payment = Column(Integer, nullable=False)
    total_repayment = Column(Integer, nullable=False)
    remaining_balance = Column(Integer, nullable=False)
    status = Column(Enum("active", "completed"), nullable=False, server_default="active")
    started_turn = Column(Integer, nullable=False)
    active_user_id = Column(
        BigInteger,
        Computed("CASE WHEN status = 'active' THEN user_id ELSE NULL END", persisted=True),
        nullable=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="loans")
    credit_grade = relationship("CreditGradePolicy", back_populates="loans")
    repayment_schedules = relationship("RepaymentSchedule", back_populates="loan")


class RepaymentSchedule(Base):
    __tablename__ = "repayment_schedule"
    __table_args__ = (
        UniqueConstraint("loan_id", "installment_number", name="uq_repayment_loan_installment"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    loan_id = Column(BigInteger, ForeignKey("loans.id"), nullable=False)
    installment_number = Column(Integer, nullable=False)
    due_turn = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(Enum("pending", "paid", "overdue"), nullable=False, server_default="pending")
    paid_at_turn = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    loan = relationship("Loan", back_populates="repayment_schedules")
