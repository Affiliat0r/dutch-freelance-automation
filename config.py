"""Configuration management for the application."""

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration."""

    # Application settings
    APP_NAME: str = os.getenv("APP_NAME", "Administration Automation")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Paths
    BASE_DIR: Path = Path(__file__).parent
    UPLOAD_FOLDER: Path = BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads")
    TEMP_FOLDER: Path = BASE_DIR / "temp"
    INVOICE_DATA_DIR: Path = BASE_DIR / "invoice_data"
    INVOICE_PDF_DIR: Path = INVOICE_DATA_DIR / "invoices"
    INVOICE_LOGO_DIR: Path = INVOICE_DATA_DIR / "logos"

    # File upload settings
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    MAX_UPLOAD_SIZE: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    ALLOWED_EXTENSIONS: List[str] = os.getenv(
        "ALLOWED_EXTENSIONS", "pdf,png,jpg,jpeg"
    ).split(",")
    MAX_BATCH_SIZE: int = 50

    # Google Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/admin_automation"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # Dutch VAT rates
    VAT_RATES = {
        "low": 9,      # Previously 6%, now 9%
        "medium": 9,   # Books, magazines, etc.
        "high": 21     # Standard rate
    }

    # Expense categories (in Dutch)
    EXPENSE_CATEGORIES = [
        "Beroepskosten",
        "Kantoorkosten",
        "Reis- en verblijfkosten",
        "Representatiekosten - Type 1 (Supermarket)",
        "Representatiekosten - Type 2 (Horeca)",
        "Vervoerskosten",
        "Zakelijke opleidingskosten"
    ]

    # Export columns for Excel
    EXPORT_COLUMNS = [
        "Nr",
        "Datum",
        "Winkel/Leverancier",
        "Categorie kosten",
        "Bedrag excl. BTW",
        "BTW 6%",
        "BTW 9%",
        "BTW 21%",
        "Totaal incl. BTW",
        "BTW aftrekbaar %",
        "IB aftrekbaar %",
        "BTW terugvraag",
        "Restant na BTW",
        "Winstaftrek",
        "Toelichting/motivatie"
    ]

    # Invoice settings
    INVOICE_NUMBER_FORMAT = "{prefix}-{year}-{number:04d}"  # INV-2025-0001
    DEFAULT_PAYMENT_TERMS = 30  # days
    INVOICE_VAT_RATES = [0, 9, 21]  # Valid VAT rates
    INVOICE_STATUS_OPTIONS = ["draft", "sent", "paid", "cancelled"]
    PAYMENT_STATUS_OPTIONS = ["unpaid", "paid", "overdue", "cancelled"]
    PAYMENT_METHODS = ["Bankoverschrijving", "iDEAL", "Contant", "Creditcard", "PayPal"]

    # PDF settings
    INVOICE_PDF_FONT = "Helvetica"
    INVOICE_LOGO_MAX_WIDTH = 200  # pixels
    INVOICE_LOGO_MAX_HEIGHT = 100  # pixels

    @classmethod
    def create_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        cls.TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for organization
        (cls.UPLOAD_FOLDER / "receipts").mkdir(exist_ok=True)
        (cls.UPLOAD_FOLDER / "processed").mkdir(exist_ok=True)
        (cls.UPLOAD_FOLDER / "failed").mkdir(exist_ok=True)

        # Create invoice directories
        cls.INVOICE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.INVOICE_PDF_DIR.mkdir(parents=True, exist_ok=True)
        cls.INVOICE_LOGO_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        """Validate configuration."""
        errors = []

        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is not set")

        if not cls.SECRET_KEY or cls.SECRET_KEY == "your-secret-key-here":
            errors.append("SECRET_KEY must be set to a secure value")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True

# Create directories on module import
Config.create_directories()