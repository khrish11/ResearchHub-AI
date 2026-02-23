from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    google_id = Column(String, unique=True, nullable=True)
    google_email = Column(String, nullable=True)
    name = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)
    
    workspaces = relationship("Workspace", back_populates="owner")

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="workspaces")
    papers = relationship("Paper", back_populates="workspace")
    chats = relationship("Chat", back_populates="workspace")

class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    authors = Column(String)
    abstract = Column(Text)
    url = Column(String, nullable=True)
    doi = Column(String, nullable=True)
    bibcode = Column(String, nullable=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    
    workspace = relationship("Workspace", back_populates="papers")

class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text)
    response = Column(Text)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    workspace = relationship("Workspace", back_populates="chats")
