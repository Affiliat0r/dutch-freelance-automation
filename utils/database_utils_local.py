"""Local storage wrappers that match database_utils interface."""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from utils.local_storage import (
    save_receipt,
    update_receipt_status as update_status_local,
    update_receipt_data,
    get_receipt,
    get_all_receipts,
    filter_receipts,
    get_statistics,
    init_storage
)

logger = logging.getLogger(__name__)

# Initialize storage on import
init_storage()

def get_receipt_stats(user_id: int = None, date_range: tuple = None) -> Dict:
    """Get receipt statistics for dashboard."""
    start_date = None
    end_date = None

    if date_range:
        start_date = datetime.combine(date_range[0], datetime.min.time()) if date_range[0] else None
        end_date = datetime.combine(date_range[1], datetime.max.time()) if date_range[1] else None

    return get_statistics(start_date=start_date, end_date=end_date)

def get_recent_receipts(user_id: int = None, limit: int = 10, offset: int = 0) -> List[Dict]:
    """Get recent receipts."""
    receipts = get_all_receipts()

    # Sort by upload_date descending
    receipts = sorted(receipts, key=lambda x: x.get('upload_date', ''), reverse=True)

    # Apply pagination
    receipts = receipts[offset:offset + limit]

    # Convert to expected format
    result = []
    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})

        result.append({
            'id': receipt['id'],
            'receipt_number': f"R{receipt['id']:06d}",
            'date': receipt['upload_date'],
            'transaction_date': extracted.get('transaction_date') or extracted.get('date'),
            'filename': receipt['filename'],
            'status': receipt['processing_status'],
            'vendor_name': extracted.get('vendor_name'),
            'expense_category': extracted.get('expense_category') or extracted.get('category'),
            'total_incl_vat': extracted.get('total_incl_vat') or extracted.get('total_amount', 0),
            'vat_6_amount': extracted.get('vat_6_amount', 0),
            'vat_9_amount': extracted.get('vat_9_amount', 0),
            'vat_21_amount': extracted.get('vat_21_amount', 0),
            'vat_refund_amount': extracted.get('vat_refund_amount') or extracted.get('vat_deductible_amount', 0)
        })

    return result

def save_receipt_to_db(
    file_path: str,
    original_filename: str,
    file_size: int,
    file_type: str,
    user_id: int = None
) -> Optional[int]:
    """Save receipt information to local storage."""
    try:
        receipt_id = save_receipt(
            file_path=file_path,
            filename=original_filename,
            file_size=file_size,
            file_type=file_type
        )
        return receipt_id
    except Exception as e:
        logger.error(f"Error saving receipt: {e}")
        return None

def save_extracted_data(receipt_id: int, extracted_data: Dict) -> bool:
    """Save extracted data for a receipt."""
    try:
        update_receipt_data(receipt_id, extracted_data)
        return True
    except Exception as e:
        logger.error(f"Error saving extracted data: {e}")
        return False

def update_receipt_status(receipt_id: int, status: str, error_msg: str = None) -> bool:
    """Update receipt processing status."""
    try:
        update_status_local(receipt_id, status, error_msg)
        return True
    except Exception as e:
        logger.error(f"Error updating receipt status: {e}")
        return False

def search_receipts(
    user_id: int = None,
    search_term: str = None,
    category: str = None,
    date_from: datetime = None,
    date_to: datetime = None,
    status: str = None,
    min_amount: float = None,
    max_amount: float = None
) -> List[Dict]:
    """Search receipts with filters."""
    try:
        categories = [category] if category else None
        receipts = filter_receipts(
            start_date=date_from,
            end_date=date_to,
            status=status,
            categories=categories,
            vendor=search_term,
            min_amount=min_amount,
            max_amount=max_amount
        )

        # Convert to expected format
        result = []
        for receipt in receipts:
            extracted = receipt.get('extracted_data', {})
            result.append({
                'id': receipt['id'],
                'receipt_number': f"R{receipt['id']:06d}",
                'date': receipt['upload_date'],
                'transaction_date': extracted.get('transaction_date') or extracted.get('date'),
                'filename': receipt['filename'],
                'status': receipt['processing_status'],
                'vendor': extracted.get('vendor_name'),
                'category': extracted.get('expense_category') or extracted.get('category'),
                'amount': extracted.get('total_incl_vat') or extracted.get('total_amount', 0)
            })

        return result
    except Exception as e:
        logger.error(f"Error searching receipts: {e}")
        return []

def get_receipts_for_export(
    user_id: int,
    date_from: datetime,
    date_to: datetime,
    categories: List[str] = None
) -> List[Dict]:
    """Get receipts for export with all details."""
    try:
        receipts = filter_receipts(
            start_date=date_from,
            end_date=date_to,
            categories=categories,
            status='completed'
        )

        result = []
        for receipt in receipts:
            extracted = receipt.get('extracted_data', {})

            # Convert transaction date
            trans_date = extracted.get('transaction_date') or extracted.get('date')
            if isinstance(trans_date, str):
                try:
                    trans_date = datetime.fromisoformat(trans_date)
                except:
                    trans_date = datetime.now()

            # Calculate VAT amounts
            vat_breakdown = extracted.get('vat_breakdown', {})
            vat_6 = vat_breakdown.get('6', extracted.get('vat_6_amount', 0))
            vat_9 = vat_breakdown.get('9', extracted.get('vat_9_amount', 0))
            vat_21 = vat_breakdown.get('21', extracted.get('vat_21_amount', 0))

            data = {
                'receipt_number': f"R{receipt['id']:06d}",
                'transaction_date': trans_date,
                'vendor_name': extracted.get('vendor_name', 'Onbekend'),
                'category': extracted.get('expense_category') or extracted.get('category', 'Niet gecategoriseerd'),
                'amount_excl_vat': extracted.get('amount_excl_vat', 0),
                'vat_6': vat_6,
                'vat_9': vat_9,
                'vat_21': vat_21,
                'total_incl_vat': extracted.get('total_incl_vat') or extracted.get('total_amount', 0),
                'vat_deductible_percentage': extracted.get('vat_deductible_percentage', 100),
                'ib_deductible_percentage': extracted.get('ib_deductible_percentage', 100),
                'vat_refund': extracted.get('vat_refund_amount') or extracted.get('vat_deductible_amount', 0),
                'profit_deduction': extracted.get('profit_deduction') or extracted.get('ib_deduction_amount', 0),
                'explanation': extracted.get('explanation') or extracted.get('notes', '')
            }
            result.append(data)

        # Sort by transaction date
        result = sorted(result, key=lambda x: x['transaction_date'])

        return result

    except Exception as e:
        logger.error(f"Error getting receipts for export: {e}")
        return []

def log_audit_event(*args, **kwargs):
    """Log audit event - no-op for local storage."""
    pass
