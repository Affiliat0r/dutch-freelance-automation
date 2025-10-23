"""Utility functions for resetting application data."""

import logging
import shutil
from pathlib import Path
from typing import Dict

from config import Config
from database.connection import drop_db, init_db

logger = logging.getLogger(__name__)

# Receipt storage paths (same as in local_storage.py)
RECEIPT_STORAGE_DIR = Path(Config.UPLOAD_FOLDER).parent / "receipt_data"
RECEIPTS_DIR = RECEIPT_STORAGE_DIR / "receipts"
RECEIPTS_METADATA_FILE = RECEIPT_STORAGE_DIR / "receipts_metadata.json"


def hard_reset_all_data() -> Dict[str, bool]:
    """
    Perform a hard reset of all application data.

    This will:
    - Delete all receipt files and metadata
    - Delete all invoice files and metadata
    - Delete exchange rate cache
    - Drop and recreate the database

    Returns:
        Dict with success status for each operation
    """
    results = {
        'receipts_deleted': False,
        'invoices_deleted': False,
        'cache_deleted': False,
        'database_reset': False,
        'success': False
    }

    try:
        # 1. Delete receipt data
        logger.info("Deleting receipt data...")
        receipts_metadata = Path(RECEIPTS_METADATA_FILE)
        if receipts_metadata.exists():
            receipts_metadata.unlink()
            logger.info(f"Deleted {receipts_metadata}")

        receipts_dir = Path(RECEIPTS_DIR)
        if receipts_dir.exists():
            for file in receipts_dir.iterdir():
                if file.is_file():
                    file.unlink()
            logger.info(f"Deleted all files in {receipts_dir}")

        results['receipts_deleted'] = True

        # 2. Delete invoice data
        logger.info("Deleting invoice data...")
        invoice_metadata = Path("invoice_data/invoices_metadata.json")
        if invoice_metadata.exists():
            invoice_metadata.unlink()
            logger.info(f"Deleted {invoice_metadata}")

        clients_file = Path("invoice_data/clients.json")
        if clients_file.exists():
            clients_file.unlink()
            logger.info(f"Deleted {clients_file}")

        settings_file = Path("invoice_data/invoice_settings.json")
        if settings_file.exists():
            settings_file.unlink()
            logger.info(f"Deleted {settings_file}")

        invoices_dir = Path("invoice_data/invoices")
        if invoices_dir.exists():
            for file in invoices_dir.iterdir():
                if file.is_file():
                    file.unlink()
            logger.info(f"Deleted all files in {invoices_dir}")

        results['invoices_deleted'] = True

        # 3. Delete exchange rate cache
        logger.info("Deleting exchange rate cache...")
        cache_file = Path("temp/exchange_rates_cache.json")
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"Deleted {cache_file}")

        results['cache_deleted'] = True

        # 4. Reset database
        logger.info("Resetting database...")
        try:
            drop_db()
            logger.info("Database dropped successfully")
        except Exception as e:
            logger.warning(f"Could not drop database: {e}")

        try:
            init_db()
            logger.info("Database recreated successfully")
            results['database_reset'] = True
        except Exception as e:
            logger.error(f"Failed to recreate database: {e}")
            results['database_reset'] = False

        # Check if all operations succeeded
        results['success'] = all([
            results['receipts_deleted'],
            results['invoices_deleted'],
            results['cache_deleted'],
            results['database_reset']
        ])

        if results['success']:
            logger.info("Hard reset completed successfully")
        else:
            logger.warning("Hard reset completed with some errors")

        return results

    except Exception as e:
        logger.error(f"Hard reset failed: {e}")
        results['success'] = False
        results['error'] = str(e)
        return results


def get_data_statistics() -> Dict:
    """
    Get statistics about current data before reset.

    Returns:
        Dict with counts of receipts, invoices, etc.
    """
    stats = {
        'receipt_count': 0,
        'invoice_count': 0,
        'receipt_files': 0,
        'invoice_files': 0
    }

    try:
        # Count receipts
        receipts_metadata = Path(RECEIPTS_METADATA_FILE)
        if receipts_metadata.exists():
            import json
            with open(receipts_metadata, 'r', encoding='utf-8') as f:
                receipts = json.load(f)
                stats['receipt_count'] = len(receipts)

        receipts_dir = Path(RECEIPTS_DIR)
        if receipts_dir.exists():
            stats['receipt_files'] = len(list(receipts_dir.glob('*.*')))

        # Count invoices
        invoice_metadata = Path("invoice_data/invoices_metadata.json")
        if invoice_metadata.exists():
            import json
            with open(invoice_metadata, 'r', encoding='utf-8') as f:
                invoices = json.load(f)
                stats['invoice_count'] = len(invoices)

        invoices_dir = Path("invoice_data/invoices")
        if invoices_dir.exists():
            stats['invoice_files'] = len(list(invoices_dir.glob('*.pdf')))

    except Exception as e:
        logger.error(f"Failed to get data statistics: {e}")

    return stats
