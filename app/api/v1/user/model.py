from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, Integer, SmallInteger, String, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=True)
    nickname = Column(String(50), nullable=False, unique=True)
    profile_image_seed = Column(String(50), nullable=False)
    job_type = Column(Enum("employee", "freelancer", "other"), nullable=False)
    monthly_salary = Column(Integer, nullable=False)
    is_email_verified = Column(Boolean, nullable=False, server_default=text("0"))
    provider = Column(Enum("local", "kakao", "google"), nullable=False, server_default="local")
    social_id = Column(String(255), nullable=True)
    onboarding_step = Column(SmallInteger, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    fixed_expenses = relationship("FixedExpense", back_populates="user")
    simulation_state = relationship("SimulationState", back_populates="user", uselist=False)
    turns = relationship("Turn", back_populates="user")
    expenses = relationship("Expense", back_populates="user")
    stock_holdings = relationship("StockHolding", back_populates="user")
    loans = relationship("Loan", back_populates="user")
    credit_histories = relationship("CreditHistory", back_populates="user")
