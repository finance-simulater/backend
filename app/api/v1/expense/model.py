from sqlalchemy import BigInteger, Column, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    name = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)
    expense_type = Column(Enum("fixed", "variable"), nullable=False)
    expense_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="expenses")
