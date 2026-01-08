from sqlalchemy import Column, ForeignKey, Integer, DateTime, func, String, UniqueConstraint, Boolean
from app.db.session import Base
from sqlalchemy.orm import relationship

class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    is_admin = Column(Boolean, default=False)

    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group", back_populates="members")


    __table_args__ = (
        UniqueConstraint("group_id", "email", name="uq_group_member_email"),
        UniqueConstraint("group_id", "phone", name="uq_group_member_phone"),
    )