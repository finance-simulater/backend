from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class CreditGradePolicy(Base):
    __tablename__ = "credit_grade_policy"

    grade = Column(String(2), primary_key=True)
    grade_rank = Column(Integer, nullable=False, unique=True)
    min_score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)
    credit_limit = Column(Integer, nullable=False)
    base_interest_rate = Column(Numeric(4, 2), nullable=False)

    loans = relationship("Loan", back_populates="credit_grade")


class CreditHistory(Base):
    __tablename__ = "credit_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(
        Enum("loan_payment", "overdue", "loan_complete", "loan_default"),
        nullable=False,
    )
    score_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="credit_histories")
