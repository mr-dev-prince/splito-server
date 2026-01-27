from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    clerk_user_id = Column(String, unique=True, nullable=False)

    email = Column(String, nullable=False)
    name = Column(String, default="Splito User")
    avatar_url = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    security_pin = Column(String, nullable=True)
    security_pin_active = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)
