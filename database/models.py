"""Database models for the application."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    Text, Numeric, Boolean, JSON, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    """User model for authentication and multi-tenancy."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    company_name = Column(String(255))
    kvk_number = Column(String(20))  # Dutch Chamber of Commerce number
    btw_number = Column(String(20))  # VAT number
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    receipts = relationship("Receipt", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False)

class UserSettings(Base):
    """User-specific settings and preferences."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    default_vat_deductible = Column(Float, default=100.0)  # Default VAT deductible %
    default_ib_deductible = Column(Float, default=100.0)   # Default income tax deductible %
    auto_categorize = Column(Boolean, default=True)
    language = Column(String(10), default="nl")  # nl or en
    notification_email = Column(Boolean, default=True)
    export_format = Column(String(20), default="excel")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")
    category_tax_rules = relationship("CategoryTaxRule", back_populates="user_settings", cascade="all, delete-orphan")

class CategoryTaxRule(Base):
    """Category-specific tax deduction rules."""

    __tablename__ = "category_tax_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_settings_id = Column(Integer, ForeignKey("user_settings.id"))
    category_name = Column(String(100), nullable=False)
    vat_deductible_percentage = Column(Float, nullable=False, default=100.0)
    ib_deductible_percentage = Column(Float, nullable=False, default=100.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user_settings = relationship("UserSettings", back_populates="category_tax_rules")

class Receipt(Base):
    """Receipt model for storing uploaded receipt information."""

    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receipt_number = Column(String(50), unique=True, index=True)
    original_filename = Column(String(255))
    stored_filename = Column(String(255))
    file_path = Column(String(500))
    file_size = Column(Integer)  # in bytes
    file_type = Column(String(50))
    upload_date = Column(DateTime, default=datetime.utcnow, index=True)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text, nullable=True)
    is_validated = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="receipts")
    extracted_data = relationship("ExtractedData", back_populates="receipt", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="receipt", cascade="all, delete-orphan")

class ExtractedData(Base):
    """Extracted data from receipts."""

    __tablename__ = "extracted_data"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), unique=True)

    # Basic information
    transaction_date = Column(DateTime, index=True)
    vendor_name = Column(String(255), index=True)
    vendor_address = Column(Text)
    invoice_number = Column(String(100))

    # Language and category
    detected_language = Column(String(10))
    expense_category = Column(String(100), index=True)

    # Financial data (stored as Decimal for precision)
    amount_excl_vat = Column(Numeric(12, 2))
    vat_6_amount = Column(Numeric(12, 2), default=0)
    vat_9_amount = Column(Numeric(12, 2), default=0)
    vat_21_amount = Column(Numeric(12, 2), default=0)
    total_incl_vat = Column(Numeric(12, 2))

    # Tax calculations
    vat_deductible_percentage = Column(Float)
    ib_deductible_percentage = Column(Float)
    vat_refund_amount = Column(Numeric(12, 2))
    remainder_after_vat = Column(Numeric(12, 2))
    profit_deduction = Column(Numeric(12, 2))

    # Additional information
    explanation = Column(Text)
    items_json = Column(JSON)  # Store individual line items as JSON
    raw_ocr_text = Column(Text)
    confidence_score = Column(Float)  # OCR confidence

    # Metadata
    extraction_version = Column(String(20), default="1.0")
    extraction_timestamp = Column(DateTime, default=datetime.utcnow)
    manual_review_required = Column(Boolean, default=False)
    manual_review_completed = Column(Boolean, default=False)
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    receipt = relationship("Receipt", back_populates="extracted_data")

class AuditLog(Base):
    """Audit log for tracking all changes to receipts and extracted data."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    action = Column(String(50))  # create, update, delete, export, etc.
    entity_type = Column(String(50))  # receipt, extracted_data, user, etc.
    entity_id = Column(Integer)
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    receipt = relationship("Receipt", back_populates="audit_logs")

class ExportHistory(Base):
    """Track export history for compliance and audit purposes."""

    __tablename__ = "export_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    export_type = Column(String(50))  # excel, csv, pdf
    date_from = Column(DateTime)
    date_to = Column(DateTime)
    receipt_count = Column(Integer)
    file_name = Column(String(255))
    file_size = Column(Integer)
    export_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50))  # success, failed
    error_message = Column(Text)