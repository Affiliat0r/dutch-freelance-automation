"""Local file-based storage for receipts - no database needed."""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

from config import Config

logger = logging.getLogger(__name__)

# Local storage directories
STORAGE_DIR = Path(Config.UPLOAD_FOLDER).parent / "receipt_data"
RECEIPTS_DIR = STORAGE_DIR / "receipts"
METADATA_FILE = STORAGE_DIR / "receipts_metadata.json"

def init_storage():
    """Initialize local storage directories."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    if not METADATA_FILE.exists():
        save_metadata([])

    logger.info(f"Local storage initialized at {STORAGE_DIR}")

def get_next_receipt_id() -> int:
    """Get the next available receipt ID."""
    metadata = load_metadata()
    if not metadata:
        return 1
    return max([r['id'] for r in metadata]) + 1

def save_receipt(
    file_path: str,
    filename: str,
    file_size: int,
    file_type: str,
    extracted_data: Optional[Dict] = None
) -> int:
    """Save receipt information to local storage.

    Args:
        file_path: Path to the uploaded file
        filename: Original filename
        file_size: File size in bytes
        file_type: MIME type
        extracted_data: Extracted data from OCR/LLM processing

    Returns:
        Receipt ID
    """
    init_storage()

    receipt_id = get_next_receipt_id()
    upload_date = datetime.now()

    # Copy file to receipts directory
    source = Path(file_path)
    destination = RECEIPTS_DIR / f"{receipt_id}_{filename}"
    shutil.copy2(source, destination)

    # Create receipt record
    receipt = {
        'id': receipt_id,
        'filename': filename,
        'file_path': str(destination),
        'file_size': file_size,
        'file_type': file_type,
        'upload_date': upload_date.isoformat(),
        'processing_status': 'pending',
        'extracted_data': extracted_data or {},
        'error_message': None,
        'created_at': upload_date.isoformat(),
        'updated_at': upload_date.isoformat()
    }

    # Load existing metadata
    metadata = load_metadata()
    metadata.append(receipt)

    # Save metadata
    save_metadata(metadata)

    logger.info(f"Saved receipt {receipt_id}: {filename}")
    return receipt_id

def update_receipt_status(receipt_id: int, status: str, error_message: Optional[str] = None):
    """Update receipt processing status.

    Args:
        receipt_id: Receipt ID
        status: Processing status (pending, processing, completed, failed)
        error_message: Error message if failed
    """
    metadata = load_metadata()

    for receipt in metadata:
        if receipt['id'] == receipt_id:
            receipt['processing_status'] = status
            receipt['updated_at'] = datetime.now().isoformat()
            if error_message:
                receipt['error_message'] = error_message
            break

    save_metadata(metadata)
    logger.info(f"Updated receipt {receipt_id} status to {status}")

def update_receipt_data(receipt_id: int, extracted_data: Dict):
    """Update extracted data for a receipt.

    Args:
        receipt_id: Receipt ID
        extracted_data: Extracted data from processing
    """
    metadata = load_metadata()

    for receipt in metadata:
        if receipt['id'] == receipt_id:
            receipt['extracted_data'] = extracted_data
            receipt['processing_status'] = 'completed'
            receipt['updated_at'] = datetime.now().isoformat()
            break

    save_metadata(metadata)
    logger.info(f"Updated receipt {receipt_id} with extracted data")

def get_receipt(receipt_id: int) -> Optional[Dict]:
    """Get a single receipt by ID.

    Args:
        receipt_id: Receipt ID

    Returns:
        Receipt dictionary or None
    """
    metadata = load_metadata()

    for receipt in metadata:
        if receipt['id'] == receipt_id:
            return receipt

    return None

def get_all_receipts() -> List[Dict]:
    """Get all receipts.

    Returns:
        List of receipt dictionaries
    """
    return load_metadata()

def filter_receipts(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    categories: Optional[List[str]] = None,
    vendor: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> List[Dict]:
    """Filter receipts based on criteria.

    Args:
        start_date: Start date filter
        end_date: End date filter
        status: Processing status filter
        categories: List of categories to filter
        vendor: Vendor name to search
        min_amount: Minimum amount
        max_amount: Maximum amount

    Returns:
        Filtered list of receipts
    """
    metadata = load_metadata()
    filtered = []

    for receipt in metadata:
        # Date filter
        if start_date or end_date:
            upload_date = datetime.fromisoformat(receipt['upload_date'])
            if start_date and upload_date < start_date:
                continue
            if end_date and upload_date > end_date:
                continue

        # Status filter
        if status and status != "Alle" and receipt['processing_status'] != status:
            continue

        # Category filter
        extracted = receipt.get('extracted_data', {})
        if categories:
            category = extracted.get('expense_category') or extracted.get('category')
            if category not in categories:
                continue

        # Vendor filter
        if vendor:
            vendor_name = extracted.get('vendor_name', '').lower()
            if vendor.lower() not in vendor_name:
                continue

        # Amount filter
        if min_amount is not None or max_amount is not None:
            amount = extracted.get('total_incl_vat') or extracted.get('total_amount', 0)
            if min_amount is not None and amount < min_amount:
                continue
            if max_amount is not None and amount > max_amount:
                continue

        filtered.append(receipt)

    return filtered

def delete_receipt(receipt_id: int) -> bool:
    """Delete a receipt and its file.

    Args:
        receipt_id: Receipt ID

    Returns:
        True if deleted, False if not found
    """
    metadata = load_metadata()

    for idx, receipt in enumerate(metadata):
        if receipt['id'] == receipt_id:
            # Delete file
            file_path = Path(receipt['file_path'])
            if file_path.exists():
                file_path.unlink()

            # Remove from metadata
            metadata.pop(idx)
            save_metadata(metadata)

            logger.info(f"Deleted receipt {receipt_id}")
            return True

    return False

def get_statistics(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict:
    """Get statistics for receipts.

    Args:
        start_date: Start date filter
        end_date: End date filter

    Returns:
        Statistics dictionary
    """
    receipts = filter_receipts(start_date=start_date, end_date=end_date)

    total_receipts = len(receipts)
    total_amount = 0
    total_vat = 0
    processed = 0

    for receipt in receipts:
        if receipt['processing_status'] == 'completed':
            processed += 1
            extracted = receipt.get('extracted_data', {})
            total_amount += extracted.get('total_incl_vat') or extracted.get('total_amount', 0)

            # Calculate VAT
            vat_6 = extracted.get('vat_6_amount', 0)
            vat_9 = extracted.get('vat_9_amount', 0)
            vat_21 = extracted.get('vat_21_amount', 0)

            # Also check for vat_breakdown format
            vat_breakdown = extracted.get('vat_breakdown', {})
            if vat_breakdown:
                vat_6 = vat_breakdown.get('6', vat_6)
                vat_9 = vat_breakdown.get('9', vat_9)
                vat_21 = vat_breakdown.get('21', vat_21)

            total_vat += vat_6 + vat_9 + vat_21

    return {
        'total_receipts': total_receipts,
        'total_amount': total_amount,
        'total_vat': total_vat,
        'processed': processed
    }

def load_metadata() -> List[Dict]:
    """Load receipts metadata from JSON file."""
    if not METADATA_FILE.exists():
        return []

    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading metadata: {e}")
        return []

def save_metadata(metadata: List[Dict]):
    """Save receipts metadata to JSON file."""
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving metadata: {e}")
        raise

def export_to_json(output_path: str) -> bool:
    """Export all receipts to a JSON file.

    Args:
        output_path: Path to save JSON file

    Returns:
        True if successful
    """
    try:
        metadata = load_metadata()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported receipts to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")
        return False
