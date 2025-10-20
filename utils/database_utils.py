"""Database utility functions for data operations."""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from database.models import Receipt, ExtractedData, User, AuditLog, UserSettings, CategoryTaxRule
from database.connection import get_db

logger = logging.getLogger(__name__)

def get_receipt_stats(user_id: int = None, date_range: tuple = None) -> Dict:
    """
    Get receipt statistics for dashboard.

    Args:
        user_id: User ID for filtering
        date_range: Tuple of (start_date, end_date)

    Returns:
        Dictionary with statistics
    """
    try:
        db = next(get_db())

        query = db.query(Receipt)

        if user_id:
            query = query.filter(Receipt.user_id == user_id)

        if date_range and date_range[0] and date_range[1]:
            query = query.filter(
                and_(
                    Receipt.upload_date >= date_range[0],
                    Receipt.upload_date <= date_range[1]
                )
            )

        receipts = query.all()

        stats = {
            'total_receipts': len(receipts),
            'processed': sum(1 for r in receipts if r.processing_status == 'completed'),
            'pending': sum(1 for r in receipts if r.processing_status == 'pending'),
            'failed': sum(1 for r in receipts if r.processing_status == 'failed'),
            'total_amount': 0,
            'total_vat': 0
        }

        # Calculate financial totals
        for receipt in receipts:
            if receipt.extracted_data:
                stats['total_amount'] += float(receipt.extracted_data.total_incl_vat or 0)
                stats['total_vat'] += (
                    float(receipt.extracted_data.vat_6_amount or 0) +
                    float(receipt.extracted_data.vat_9_amount or 0) +
                    float(receipt.extracted_data.vat_21_amount or 0)
                )

        return stats

    except Exception as e:
        logger.error(f"Error getting receipt stats: {e}")
        return {
            'total_receipts': 0,
            'processed': 0,
            'pending': 0,
            'failed': 0,
            'total_amount': 0,
            'total_vat': 0
        }

def get_recent_receipts(
    user_id: int = None,
    limit: int = 10,
    offset: int = 0
) -> List[Dict]:
    """
    Get recent receipts.

    Args:
        user_id: User ID for filtering
        limit: Maximum number of receipts
        offset: Offset for pagination

    Returns:
        List of receipt dictionaries
    """
    try:
        db = next(get_db())

        query = db.query(Receipt).filter(Receipt.is_deleted == False)

        if user_id:
            query = query.filter(Receipt.user_id == user_id)

        receipts = query.order_by(
            desc(Receipt.upload_date)
        ).limit(limit).offset(offset).all()

        result = []
        for receipt in receipts:
            data = {
                'id': receipt.id,
                'receipt_number': receipt.receipt_number,
                'date': receipt.upload_date,
                'filename': receipt.original_filename,
                'status': receipt.processing_status,
                'vendor': None,
                'category': None,
                'amount': 0
            }

            if receipt.extracted_data:
                data['vendor'] = receipt.extracted_data.vendor_name
                data['category'] = receipt.extracted_data.expense_category
                data['amount'] = float(receipt.extracted_data.total_incl_vat or 0)

            result.append(data)

        return result

    except Exception as e:
        logger.error(f"Error getting recent receipts: {e}")
        return []

def save_receipt_to_db(
    file_path: str,
    original_filename: str,
    file_size: int,
    file_type: str,
    user_id: int = None
) -> Optional[int]:
    """
    Save receipt information to database.

    Args:
        file_path: Path to saved file
        original_filename: Original file name
        file_size: File size in bytes
        file_type: MIME type
        user_id: User ID

    Returns:
        Receipt ID if successful, None otherwise
    """
    try:
        db = next(get_db())

        # Generate receipt number
        receipt_number = f"R{datetime.now().strftime('%Y%m%d%H%M%S')}"

        receipt = Receipt(
            user_id=user_id or 1,  # Default user for demo
            receipt_number=receipt_number,
            original_filename=original_filename,
            stored_filename=file_path.split('/')[-1],
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            processing_status='pending'
        )

        db.add(receipt)
        db.commit()
        db.refresh(receipt)

        logger.info(f"Receipt saved to database: {receipt.id}")
        return receipt.id

    except Exception as e:
        logger.error(f"Error saving receipt to database: {e}")
        db.rollback()
        return None

def save_extracted_data(
    receipt_id: int,
    extracted_data: Dict
) -> bool:
    """
    Save extracted data for a receipt.

    Args:
        receipt_id: Receipt ID
        extracted_data: Dictionary with extracted data

    Returns:
        True if successful
    """
    try:
        db = next(get_db())

        # Check if extracted data already exists
        existing = db.query(ExtractedData).filter(
            ExtractedData.receipt_id == receipt_id
        ).first()

        if existing:
            # Update existing record
            for key, value in extracted_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            # Create new record
            data = ExtractedData(
                receipt_id=receipt_id,
                **extracted_data
            )
            db.add(data)

        # Update receipt status
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if receipt:
            receipt.processing_status = 'completed'
            receipt.updated_at = datetime.now()

        db.commit()
        logger.info(f"Extracted data saved for receipt {receipt_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving extracted data: {e}")
        db.rollback()
        return False

def update_receipt_status(
    receipt_id: int,
    status: str,
    error_msg: str = None
) -> bool:
    """
    Update receipt processing status.

    Args:
        receipt_id: Receipt ID
        status: New status
        error_msg: Optional error message

    Returns:
        True if successful
    """
    try:
        db = next(get_db())

        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()

        if receipt:
            receipt.processing_status = status
            receipt.processing_error = error_msg
            receipt.updated_at = datetime.now()
            db.commit()
            logger.info(f"Receipt {receipt_id} status updated to {status}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error updating receipt status: {e}")
        db.rollback()
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
    """
    Search receipts with filters.

    Args:
        Various filter parameters

    Returns:
        List of matching receipts
    """
    try:
        db = next(get_db())

        query = db.query(Receipt).join(
            ExtractedData,
            Receipt.id == ExtractedData.receipt_id,
            isouter=True
        ).filter(Receipt.is_deleted == False)

        if user_id:
            query = query.filter(Receipt.user_id == user_id)

        if search_term:
            query = query.filter(
                or_(
                    Receipt.original_filename.ilike(f"%{search_term}%"),
                    ExtractedData.vendor_name.ilike(f"%{search_term}%"),
                    ExtractedData.invoice_number.ilike(f"%{search_term}%")
                )
            )

        if category:
            query = query.filter(ExtractedData.expense_category == category)

        if date_from:
            query = query.filter(Receipt.upload_date >= date_from)

        if date_to:
            query = query.filter(Receipt.upload_date <= date_to)

        if status:
            query = query.filter(Receipt.processing_status == status)

        if min_amount is not None:
            query = query.filter(ExtractedData.total_incl_vat >= min_amount)

        if max_amount is not None:
            query = query.filter(ExtractedData.total_incl_vat <= max_amount)

        receipts = query.order_by(desc(Receipt.upload_date)).all()

        result = []
        for receipt in receipts:
            data = {
                'id': receipt.id,
                'receipt_number': receipt.receipt_number,
                'date': receipt.upload_date,
                'filename': receipt.original_filename,
                'status': receipt.processing_status,
                'vendor': None,
                'category': None,
                'amount': 0
            }

            if receipt.extracted_data:
                data['vendor'] = receipt.extracted_data.vendor_name
                data['category'] = receipt.extracted_data.expense_category
                data['amount'] = float(receipt.extracted_data.total_incl_vat or 0)
                data['transaction_date'] = receipt.extracted_data.transaction_date

            result.append(data)

        return result

    except Exception as e:
        logger.error(f"Error searching receipts: {e}")
        return []

def log_audit_event(
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    old_values: Dict = None,
    new_values: Dict = None,
    ip_address: str = None
):
    """
    Log an audit event.

    Args:
        Various audit parameters
    """
    try:
        db = next(get_db())

        audit = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address
        )

        db.add(audit)
        db.commit()

        logger.info(f"Audit logged: {action} on {entity_type} {entity_id}")

    except Exception as e:
        logger.error(f"Error logging audit event: {e}")

def get_receipts_for_export(
    user_id: int,
    date_from: datetime,
    date_to: datetime,
    categories: List[str] = None
) -> List[Dict]:
    """
    Get receipts for export with all details.

    Args:
        user_id: User ID
        date_from: Start date
        date_to: End date
        categories: Optional category filter

    Returns:
        List of receipt dictionaries with full details
    """
    try:
        db = next(get_db())

        query = db.query(Receipt).join(
            ExtractedData,
            Receipt.id == ExtractedData.receipt_id
        ).filter(
            and_(
                Receipt.user_id == user_id,
                Receipt.is_deleted == False,
                Receipt.processing_status == 'completed',
                ExtractedData.transaction_date >= date_from,
                ExtractedData.transaction_date <= date_to
            )
        )

        if categories:
            query = query.filter(ExtractedData.expense_category.in_(categories))

        receipts = query.order_by(ExtractedData.transaction_date).all()

        result = []
        for receipt in receipts:
            ed = receipt.extracted_data
            data = {
                'receipt_number': receipt.receipt_number,
                'transaction_date': ed.transaction_date,
                'vendor_name': ed.vendor_name,
                'category': ed.expense_category,
                'amount_excl_vat': float(ed.amount_excl_vat or 0),
                'vat_6': float(ed.vat_6_amount or 0),
                'vat_9': float(ed.vat_9_amount or 0),
                'vat_21': float(ed.vat_21_amount or 0),
                'total_incl_vat': float(ed.total_incl_vat or 0),
                'vat_deductible_percentage': ed.vat_deductible_percentage or 0,
                'ib_deductible_percentage': ed.ib_deductible_percentage or 0,
                'vat_refund': float(ed.vat_refund_amount or 0),
                'profit_deduction': float(ed.profit_deduction or 0),
                'explanation': ed.explanation
            }
            result.append(data)

        return result

    except Exception as e:
        logger.error(f"Error getting receipts for export: {e}")
        return []

def get_category_tax_rules(user_settings_id: int = 1) -> Dict[str, Dict[str, float]]:
    """
    Get category-specific tax deduction rules from database.

    Args:
        user_settings_id: ID of user settings (default: 1 for single-user mode)

    Returns:
        Dictionary mapping category names to their tax percentages
    """
    try:
        db = next(get_db())

        rules = db.query(CategoryTaxRule).filter(
            CategoryTaxRule.user_settings_id == user_settings_id
        ).all()

        result = {}
        for rule in rules:
            result[rule.category_name] = {
                'vat_deductible': rule.vat_deductible_percentage,
                'ib_deductible': rule.ib_deductible_percentage
            }

        return result

    except Exception as e:
        logger.error(f"Error getting category tax rules: {e}")
        return {}

def save_category_tax_rules(rules: Dict[str, Dict[str, float]], user_settings_id: int = 1):
    """
    Save category-specific tax deduction rules to database.

    Args:
        rules: Dictionary mapping category names to their tax percentages
        user_settings_id: ID of user settings (default: 1 for single-user mode)
    """
    try:
        db = next(get_db())

        # Delete existing rules for this user
        db.query(CategoryTaxRule).filter(
            CategoryTaxRule.user_settings_id == user_settings_id
        ).delete()

        # Create new rules
        for category_name, percentages in rules.items():
            rule = CategoryTaxRule(
                user_settings_id=user_settings_id,
                category_name=category_name,
                vat_deductible_percentage=percentages['vat'],
                ib_deductible_percentage=percentages['ib']
            )
            db.add(rule)

        db.commit()
        logger.info(f"Saved {len(rules)} category tax rules for user_settings_id {user_settings_id}")

    except Exception as e:
        logger.error(f"Error saving category tax rules: {e}")
        db.rollback()

def ensure_user_settings_exists(user_id: int = 1) -> int:
    """
    Ensure UserSettings record exists for the user.

    Args:
        user_id: User ID (default: 1 for single-user mode)

    Returns:
        UserSettings ID
    """
    try:
        db = next(get_db())

        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
            logger.info(f"Created UserSettings for user_id {user_id}")

        return settings.id

    except Exception as e:
        logger.error(f"Error ensuring user settings exists: {e}")
        return 1