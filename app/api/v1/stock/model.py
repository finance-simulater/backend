from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class StockHolding(Base):
    __tablename__ = "stock_holdings"
    __table_args__ = (UniqueConstraint("user_id", "stock_type", name="uq_stock_holdings_user_type"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    stock_type = Column(Enum("high_vol", "low_vol", "index"), nullable=False)
    principal = Column(Integer, nullable=False)
    current_value = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="stock_holdings")
