from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base  # adaptez selon votre structure

class Preuve(Base):
    __tablename__ = "preuves"

    id = Column(Integer, primary_key=True, index=True)
    signalement_id = Column(Integer, ForeignKey("signalements.id"), nullable=False)
    type = Column(String(20), nullable=False)  # "avant" ou "apres"
    photo_base64 = Column(Text, nullable=False)  # image encodée en base64
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # agent ou gestionnaire

    # Relations (optionnel)
    signalement = relationship("Signalement", back_populates="preuves")
    uploader = relationship("User", back_populates="preuves")