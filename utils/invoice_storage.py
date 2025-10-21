"""Local file-based storage for invoices - mirrors receipt storage pattern."""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
import logging

from config import Config

logger = logging.getLogger(__name__)

# Local storage directories
STORAGE_DIR = Path(Config.UPLOAD_FOLDER).parent / "invoice_data"
INVOICES_DIR = STORAGE_DIR / "invoices"
LOGOS_DIR = STORAGE_DIR / "logos"
METADATA_FILE = STORAGE_DIR / "invoices_metadata.json"
SETTINGS_FILE = STORAGE_DIR / "invoice_settings.json"
CLIENTS_FILE = STORAGE_DIR / "clients.json"

def init_invoice_storage():
    """Initialize invoice storage directories."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    if not METADATA_FILE.exists():
        save_metadata([])

    if not SETTINGS_FILE.exists():
        save_settings(get_default_settings())

    if not CLIENTS_FILE.exists():
        save_clients([])

    logger.info(f"Invoice storage initialized at {STORAGE_DIR}")

def get_default_settings() -> Dict:
    """Get default invoice settings."""
    return {
        'company_name': 'Demo Company',
        'kvk_number': '12345678',
        'btw_number': 'NL123456789B01',
        'iban': 'NL12ABCD0123456789',
        'bic': 'ABCDNL2A',
        'address_street': 'Hoofdstraat 123',
        'address_postal_code': '1234 AB',
        'address_city': 'Amsterdam',
        'address_country': 'Nederland',
        'phone': '+31 6 12345678',
        'email': 'facturen@example.com',
        'website': 'www.example.com',
        'default_vat_rate': 21.0,
        'default_payment_terms': 30,
        'invoice_number_prefix': 'INV',
        'invoice_number_start': 1,
        'next_invoice_number': 1,
        'logo_path': None,
        'footer_text': 'Betaling binnen {payment_terms} dagen op rekeningnummer {iban}.\n\nBedankt voor uw opdracht!',
        'email_subject': 'Factuur {invoice_number}',
        'email_body': 'Beste {client_name},\n\nBijgevoegd vindt u factuur {invoice_number}.\n\nMet vriendelijke groet,\n{company_name}'
    }

def get_next_invoice_number() -> str:
    """Get the next invoice number with auto-increment."""
    settings = load_settings()
    prefix = settings.get('invoice_number_prefix', 'INV')
    next_num = settings.get('next_invoice_number', 1)
    year = datetime.now().year

    invoice_number = f"{prefix}-{year}-{next_num:04d}"

    # Increment for next time
    settings['next_invoice_number'] = next_num + 1
    save_settings(settings)

    return invoice_number

def save_invoice(invoice_data: Dict) -> int:
    """Save invoice to local storage.

    Args:
        invoice_data: Invoice dictionary with all details

    Returns:
        Invoice ID
    """
    init_invoice_storage()

    # Get next ID
    metadata = load_metadata()
    if metadata:
        invoice_id = max([inv['id'] for inv in metadata]) + 1
    else:
        invoice_id = 1

    # Add metadata
    invoice_data['id'] = invoice_id
    if 'created_at' not in invoice_data:
        invoice_data['created_at'] = datetime.now().isoformat()
    invoice_data['updated_at'] = datetime.now().isoformat()

    # Append to metadata
    metadata.append(invoice_data)
    save_metadata(metadata)

    logger.info(f"Saved invoice {invoice_id}: {invoice_data.get('invoice_number')}")
    return invoice_id

def update_invoice(invoice_id: int, updates: Dict):
    """Update invoice data.

    Args:
        invoice_id: Invoice ID
        updates: Dictionary with fields to update
    """
    metadata = load_metadata()

    for invoice in metadata:
        if invoice['id'] == invoice_id:
            invoice.update(updates)
            invoice['updated_at'] = datetime.now().isoformat()
            break

    save_metadata(metadata)
    logger.info(f"Updated invoice {invoice_id}")

def update_invoice_status(invoice_id: int, status: str, payment_date: Optional[datetime] = None, payment_method: Optional[str] = None):
    """Update invoice payment status.

    Args:
        invoice_id: Invoice ID
        status: Payment status (unpaid, paid, overdue, cancelled)
        payment_date: Payment date (for paid status)
        payment_method: Payment method
    """
    updates = {
        'payment_status': status,
        'status': 'paid' if status == 'paid' else 'sent'
    }

    if payment_date:
        updates['payment_date'] = payment_date.isoformat()
    if payment_method:
        updates['payment_method'] = payment_method

    update_invoice(invoice_id, updates)

def get_invoice(invoice_id: int) -> Optional[Dict]:
    """Get single invoice by ID.

    Args:
        invoice_id: Invoice ID

    Returns:
        Invoice dictionary or None
    """
    metadata = load_metadata()

    for invoice in metadata:
        if invoice['id'] == invoice_id:
            return invoice

    return None

def get_invoice_by_number(invoice_number: str) -> Optional[Dict]:
    """Get invoice by invoice number.

    Args:
        invoice_number: Invoice number (e.g., INV-2025-0001)

    Returns:
        Invoice dictionary or None
    """
    metadata = load_metadata()

    for invoice in metadata:
        if invoice.get('invoice_number') == invoice_number:
            return invoice

    return None

def get_all_invoices() -> List[Dict]:
    """Get all invoices.

    Returns:
        List of invoice dictionaries
    """
    return load_metadata()

def filter_invoices(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    client_name: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None
) -> List[Dict]:
    """Filter invoices based on criteria.

    Args:
        start_date: Start date filter
        end_date: End date filter
        status: Invoice status (draft, sent, paid, cancelled)
        payment_status: Payment status (unpaid, paid, overdue, cancelled)
        client_name: Client name to search
        min_amount: Minimum amount
        max_amount: Maximum amount

    Returns:
        Filtered list of invoices
    """
    metadata = load_metadata()
    filtered = []

    for invoice in metadata:
        # Date filter
        if start_date or end_date:
            invoice_date_str = invoice['invoice_date']
            # Handle both date and datetime strings
            if 'T' in invoice_date_str or ' ' in invoice_date_str:
                invoice_date = datetime.fromisoformat(invoice_date_str)
            else:
                # Date only string, parse and set to start of day
                invoice_date = datetime.fromisoformat(invoice_date_str + 'T00:00:00')

            if start_date and invoice_date < start_date:
                continue
            if end_date and invoice_date > end_date:
                continue

        # Status filter
        if status and status != "Alle" and invoice.get('status') != status:
            continue

        # Payment status filter
        if payment_status and payment_status != "Alle" and invoice.get('payment_status') != payment_status:
            continue

        # Client filter
        if client_name:
            inv_client = invoice.get('client_name', '').lower()
            if client_name.lower() not in inv_client:
                continue

        # Amount filter
        if min_amount is not None or max_amount is not None:
            amount = invoice.get('total_incl_vat', 0)
            if min_amount is not None and amount < min_amount:
                continue
            if max_amount is not None and amount > max_amount:
                continue

        filtered.append(invoice)

    return filtered

def delete_invoice(invoice_id: int) -> bool:
    """Delete an invoice.

    Args:
        invoice_id: Invoice ID

    Returns:
        True if deleted, False if not found
    """
    metadata = load_metadata()

    for idx, invoice in enumerate(metadata):
        if invoice['id'] == invoice_id:
            # Delete PDF if exists
            pdf_path = invoice.get('pdf_path')
            if pdf_path:
                pdf_file = Path(pdf_path)
                if pdf_file.exists():
                    pdf_file.unlink()

            # Remove from metadata
            metadata.pop(idx)
            save_metadata(metadata)

            logger.info(f"Deleted invoice {invoice_id}")
            return True

    return False

def get_invoice_statistics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict:
    """Get invoice statistics.

    Args:
        start_date: Start date filter
        end_date: End date filter

    Returns:
        Statistics dictionary
    """
    invoices = filter_invoices(start_date=start_date, end_date=end_date)

    total_invoices = len(invoices)
    total_revenue = 0
    total_vat_payable = 0
    total_paid = 0
    total_unpaid = 0
    total_overdue = 0
    count_paid = 0
    count_unpaid = 0
    count_overdue = 0

    for invoice in invoices:
        total_incl_vat = invoice.get('total_incl_vat', 0)
        vat_amount = invoice.get('vat_amount', 0)
        payment_status = invoice.get('payment_status', 'unpaid')

        total_revenue += total_incl_vat
        total_vat_payable += vat_amount

        if payment_status == 'paid':
            total_paid += total_incl_vat
            count_paid += 1
        elif payment_status == 'overdue':
            total_unpaid += total_incl_vat
            total_overdue += total_incl_vat
            count_unpaid += 1
            count_overdue += 1
        else:  # unpaid
            total_unpaid += total_incl_vat
            count_unpaid += 1

    return {
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'total_vat_payable': total_vat_payable,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
        'total_overdue': total_overdue,
        'count_paid': count_paid,
        'count_unpaid': count_unpaid,
        'count_overdue': count_overdue,
        'average_invoice_value': total_revenue / total_invoices if total_invoices > 0 else 0
    }

def check_overdue_invoices():
    """Check for overdue invoices and update their status."""
    metadata = load_metadata()
    today = datetime.now()
    updated = False

    for invoice in metadata:
        if invoice.get('payment_status') == 'unpaid':
            due_date = datetime.fromisoformat(invoice['due_date'])
            if due_date < today:
                invoice['payment_status'] = 'overdue'
                invoice['updated_at'] = today.isoformat()
                updated = True
                logger.info(f"Marked invoice {invoice['id']} as overdue")

    if updated:
        save_metadata(metadata)

# Settings management
def load_settings() -> Dict:
    """Load invoice settings."""
    if not SETTINGS_FILE.exists():
        return get_default_settings()

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading invoice settings: {e}")
        return get_default_settings()

def save_settings(settings: Dict):
    """Save invoice settings."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving invoice settings: {e}")
        raise

# Client management
def load_clients() -> List[Dict]:
    """Load clients."""
    if not CLIENTS_FILE.exists():
        return []

    try:
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading clients: {e}")
        return []

def save_clients(clients: List[Dict]):
    """Save clients."""
    try:
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clients, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving clients: {e}")
        raise

def add_client(client_data: Dict) -> int:
    """Add a new client.

    Args:
        client_data: Client dictionary

    Returns:
        Client ID
    """
    clients = load_clients()

    if clients:
        client_id = max([c['id'] for c in clients]) + 1
    else:
        client_id = 1

    client_data['id'] = client_id
    client_data['created_at'] = datetime.now().isoformat()
    client_data['is_active'] = True

    clients.append(client_data)
    save_clients(clients)

    logger.info(f"Added client {client_id}: {client_data.get('name')}")
    return client_id

def get_client(client_id: int) -> Optional[Dict]:
    """Get client by ID."""
    clients = load_clients()
    for client in clients:
        if client['id'] == client_id:
            return client
    return None

def get_all_clients(active_only: bool = True) -> List[Dict]:
    """Get all clients.

    Args:
        active_only: Only return active clients

    Returns:
        List of clients
    """
    clients = load_clients()
    if active_only:
        return [c for c in clients if c.get('is_active', True)]
    return clients

# Metadata management
def load_metadata() -> List[Dict]:
    """Load invoices metadata from JSON file."""
    if not METADATA_FILE.exists():
        return []

    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading invoice metadata: {e}")
        return []

def save_metadata(metadata: List[Dict]):
    """Save invoices metadata to JSON file."""
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving invoice metadata: {e}")
        raise

def export_to_json(output_path: str) -> bool:
    """Export all invoices to a JSON file.

    Args:
        output_path: Path to save JSON file

    Returns:
        True if successful
    """
    try:
        metadata = load_metadata()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported invoices to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")
        return False
