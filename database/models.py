"""Database models for the application."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, ForeignKey,
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
    invoices = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    invoice_settings = relationship("InvoiceSettings", back_populates="user", uselist=False)

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

    # Currency conversion (for foreign receipts)
    original_currency = Column(String(3), default='EUR')  # ISO 4217 code: EUR, USD, TRY, etc.
    original_total_amount = Column(Numeric(12, 2))  # Amount in original currency
    original_vat_amount = Column(Numeric(12, 2))  # VAT in original currency
    exchange_rate = Column(Numeric(10, 6))  # Exchange rate to EUR (e.g., 0.028 for TRY→EUR)
    exchange_rate_date = Column(Date)  # Date when exchange rate was fetched
    exchange_rate_source = Column(String(50))  # API source: 'frankfurter', 'manual', etc.

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

class Invoice(Base):
    """Invoice model for income tracking."""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Invoice identification
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    invoice_date = Column(DateTime, nullable=False, index=True)
    due_date = Column(DateTime, nullable=False)

    # Client information
    client_name = Column(String(255), nullable=False, index=True)
    client_company = Column(String(255))
    client_email = Column(String(255))
    client_address = Column(Text)
    client_postal_code = Column(String(20))
    client_city = Column(String(100))
    client_country = Column(String(100), default="Nederland")
    client_kvk = Column(String(20))
    client_btw = Column(String(20))

    # Financial data
    subtotal_excl_vat = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Float, default=21.0)  # 0, 9, or 21
    vat_amount = Column(Numeric(12, 2), nullable=False)
    total_incl_vat = Column(Numeric(12, 2), nullable=False)

    # Payment
    payment_status = Column(String(50), default="unpaid")  # unpaid, paid, overdue, cancelled
    payment_date = Column(DateTime, nullable=True)
    payment_method = Column(String(50))  # bank_transfer, cash, ideal, etc.
    payment_reference = Column(String(255))

    # Additional info
    notes = Column(Text)
    reference = Column(String(255))  # Client reference/PO number
    currency = Column(String(3), default="EUR")

    # Status
    status = Column(String(50), default="draft")  # draft, sent, paid, cancelled
    sent_date = Column(DateTime)
    pdf_path = Column(String(500))  # Path to generated PDF

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLineItem.line_order")

class InvoiceLineItem(Base):
    """Line items for invoices."""

    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    # Line item details
    description = Column(Text, nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False, default=1.0)
    unit_price = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Float, nullable=False)  # Can vary per line item

    # Calculated fields
    subtotal = Column(Numeric(12, 2), nullable=False)  # quantity * unit_price
    vat_amount = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)

    # Order
    line_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")

class InvoiceSettings(Base):
    """Invoice-specific settings per user."""

    __tablename__ = "invoice_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    # Company details for invoices (duplicate from User for flexibility)
    company_name = Column(String(255))
    kvk_number = Column(String(20))
    btw_number = Column(String(20))
    iban = Column(String(34))
    bic = Column(String(11))

    # Address
    address_street = Column(String(255))
    address_postal_code = Column(String(20))
    address_city = Column(String(100))
    address_country = Column(String(100), default="Nederland")

    # Contact
    phone = Column(String(20))
    email = Column(String(255))
    website = Column(String(255))

    # Invoice defaults
    default_vat_rate = Column(Float, default=21.0)
    default_payment_terms = Column(Integer, default=30)  # days
    invoice_number_prefix = Column(String(20), default="INV")
    invoice_number_start = Column(Integer, default=1)
    next_invoice_number = Column(Integer, default=1)

    # Logo
    logo_path = Column(String(500))

    # Footer text
    footer_text = Column(Text)

    # Email template
    email_subject = Column(String(255), default="Factuur {invoice_number}")
    email_body = Column(Text, default="Beste {client_name},\n\nBijgevoegd vindt u factuur {invoice_number}.\n\nMet vriendelijke groet,\n{company_name}")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="invoice_settings")

class Client(Base):
    """Client model for invoice management."""

    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Client details
    name = Column(String(255), nullable=False, index=True)
    company_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(20))

    # Address
    address_street = Column(String(255))
    address_postal_code = Column(String(20))
    address_city = Column(String(100))
    address_country = Column(String(100), default="Nederland")

    # Tax details
    kvk_number = Column(String(20))
    btw_number = Column(String(20))

    # Preferences
    default_payment_terms = Column(Integer, default=30)
    default_vat_rate = Column(Float, default=21.0)

    # Status
    is_active = Column(Boolean, default=True)
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)