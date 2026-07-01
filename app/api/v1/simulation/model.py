from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SimulationState(Base):
    __tablename__ = "simulation_state"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True)
    current_turn = Column(Integer, nullable=False, server_default=text("1"))
    current_year = Column(Integer, nullable=False)
    current_month = Column(Integer, nullable=False)
    cash_balance = Column(Integer, nullable=False)
    credit_score = Column(Integer, nullable=False, server_default=text("50"))
    consume_score = Column(Integer, nullable=False, server_default=text("50"))
    status = Column(Enum("active", "completed"), nullable=False, server_default="active")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="simulation_state")


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("user_id", "turn_number", name="uq_turns_user_turn"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    salary_received = Column(Integer, nullable=False)
    fixed_expense_total = Column(Integer, nullable=False)
    variable_expense_total = Column(Integer, nullable=False)
    food_choice = Column(Enum("save", "normal", "some", "much"), nullable=False)
    shopping_choice = Column(Enum("save", "normal", "some", "much"), nullable=False)
    leisure_choice = Column(Enum("save", "normal", "some", "much"), nullable=False)
    consume_score_delta = Column(Integer, nullable=False)
    credit_score_delta = Column(Integer, nullable=False, server_default=text("0"))
    loan_repayment_amount = Column(Integer, nullable=False, server_default=text("0"))
    is_overdue = Column(Boolean, nullable=False, server_default=text("0"))
    cash_balance_after = Column(Integer, nullable=False)
    total_asset_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="turns")
