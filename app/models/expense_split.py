from sqlalchemy import Column, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id = Column(Integer, primary_key=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("group_members.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    expense = relationship("Expense", back_populates="splits")