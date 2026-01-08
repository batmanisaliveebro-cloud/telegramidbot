from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, BigInteger, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    purchases = relationship("Purchase", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")

class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    emoji = Column(String)
    price = Column(Float) # Base price for ID

    accounts = relationship("Account", back_populates="country")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"))
    phone_number = Column(String, index=True) # Removed unique=True to allow restocking same number
    session_data = Column(Text, nullable=True) # Can be session file path or string
    is_sold = Column(Boolean, default=False)
    type = Column(String, default="ID") # ID or SESSION
    created_at = Column(DateTime, default=datetime.utcnow)
    twofa_password = Column(String, nullable=True)  # 2FA password (optional)

    country = relationship("Country", back_populates="accounts")
    purchase = relationship("Purchase", back_populates="account", uselist=False)

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="purchases")
    account = relationship("Account", back_populates="purchase")

class Deposit(Base):
    __tablename__ = "deposits"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float)
    upi_ref_id = Column(String, unique=True)
    screenshot_path = Column(String, nullable=True)
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="deposits")

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(String)
