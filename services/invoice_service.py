"""Invoice business logic and calculations."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from config import Config

logger = logging.getLogger(__name__)

def calculate_line_item_totals(
    quantity: float,
    unit_price: float,
    vat_rate: float
) -> Dict:
    """Calculate totals for a single line item.

    Args:
        quantity: Quantity
        unit_price: Price per unit
        vat_rate: VAT rate (0, 9, or 21)

    Returns:
        Dictionary with subtotal, vat_amount, total
    """
    subtotal = Decimal(str(quantity)) * Decimal(str(unit_price))
    vat_amount = subtotal * Decimal(str(vat_rate)) / Decimal('100')
    total = subtotal + vat_amount

    return {
        'subtotal': float(subtotal),
        'vat_amount': float(vat_amount),
        'total': float(total)
    }

def calculate_invoice_totals(line_items: List[Dict]) -> Dict:
    """Calculate invoice totals from line items.

    Args:
        line_items: List of line item dictionaries

    Returns:
        Dictionary with totals breakdown
    """
    subtotal_excl_vat = Decimal('0')
    total_vat = Decimal('0')
    vat_breakdown = {0: Decimal('0'), 9: Decimal('0'), 21: Decimal('0')}

    for item in line_items:
        quantity = Decimal(str(item.get('quantity', 1)))
        unit_price = Decimal(str(item.get('unit_price', 0)))
        vat_rate = float(item.get('vat_rate', 21))

        item_subtotal = quantity * unit_price
        item_vat = item_subtotal * Decimal(str(vat_rate)) / Decimal('100')

        subtotal_excl_vat += item_subtotal
        total_vat += item_vat

        # Track VAT by rate
        if vat_rate in vat_breakdown:
            vat_breakdown[vat_rate] += item_vat

    total_incl_vat = subtotal_excl_vat + total_vat

    return {
        'subtotal_excl_vat': float(subtotal_excl_vat),
        'vat_0': float(vat_breakdown[0]),
        'vat_9': float(vat_breakdown[9]),
        'vat_21': float(vat_breakdown[21]),
        'total_vat': float(total_vat),
        'total_incl_vat': float(total_incl_vat)
    }

def validate_invoice_data(invoice_data: Dict) -> Tuple[bool, Optional[str]]:
    """Validate invoice data before saving.

    Args:
        invoice_data: Invoice dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Required fields
    required_fields = ['invoice_number', 'invoice_date', 'client_name']
    for field in required_fields:
        if not invoice_data.get(field):
            return False, f"Veld '{field}' is verplicht"

    # Validate line items
    line_items = invoice_data.get('line_items', [])
    if not line_items:
        return False, "Factuur moet minimaal 1 regel bevatten"

    # Validate VAT rates
    valid_vat_rates = Config.INVOICE_VAT_RATES
    for item in line_items:
        vat_rate = item.get('vat_rate')
        if vat_rate not in valid_vat_rates:
            return False, f"Ongeldig BTW tarief: {vat_rate}%. Toegestane tarieven: {valid_vat_rates}"

    # Validate amounts
    if invoice_data.get('total_incl_vat', 0) <= 0:
        return False, "Totaalbedrag moet groter zijn dan 0"

    return True, None

def generate_invoice_number(settings: Dict) -> str:
    """Generate next invoice number.

    Args:
        settings: Invoice settings dictionary

    Returns:
        Invoice number string
    """
    prefix = settings.get('invoice_number_prefix', 'INV')
    next_num = settings.get('next_invoice_number', 1)
    year = datetime.now().year

    return Config.INVOICE_NUMBER_FORMAT.format(
        prefix=prefix,
        year=year,
        number=next_num
    )

def calculate_due_date(invoice_date: datetime, payment_terms: int) -> datetime:
    """Calculate due date based on invoice date and payment terms.

    Args:
        invoice_date: Invoice date
        payment_terms: Payment terms in days

    Returns:
        Due date
    """
    return invoice_date + timedelta(days=payment_terms)

def create_invoice_from_form(form_data: Dict, settings: Dict) -> Dict:
    """Create invoice dictionary from form data.

    Args:
        form_data: Form data from UI
        settings: Invoice settings

    Returns:
        Invoice dictionary ready to save
    """
    # Parse dates
    invoice_date = form_data.get('invoice_date')
    if isinstance(invoice_date, str):
        invoice_date = datetime.fromisoformat(invoice_date)
    elif not isinstance(invoice_date, datetime):
        invoice_date = datetime.now()

    due_date = form_data.get('due_date')
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date)
    elif not isinstance(due_date, datetime):
        payment_terms = form_data.get('payment_terms', settings.get('default_payment_terms', 30))
        due_date = calculate_due_date(invoice_date, payment_terms)

    # Calculate totals from line items
    line_items = form_data.get('line_items', [])
    totals = calculate_invoice_totals(line_items)

    # Build invoice dictionary
    invoice = {
        'invoice_number': form_data.get('invoice_number') or generate_invoice_number(settings),
        'invoice_date': invoice_date.isoformat(),
        'due_date': due_date.isoformat(),

        # Client info
        'client_name': form_data.get('client_name', ''),
        'client_company': form_data.get('client_company', ''),
        'client_email': form_data.get('client_email', ''),
        'client_address': form_data.get('client_address', ''),
        'client_postal_code': form_data.get('client_postal_code', ''),
        'client_city': form_data.get('client_city', ''),
        'client_country': form_data.get('client_country', 'Nederland'),
        'client_kvk': form_data.get('client_kvk', ''),
        'client_btw': form_data.get('client_btw', ''),

        # Financial data
        'subtotal_excl_vat': totals['subtotal_excl_vat'],
        'vat_amount': totals['total_vat'],
        'total_incl_vat': totals['total_incl_vat'],

        # VAT breakdown
        'vat_0': totals['vat_0'],
        'vat_9': totals['vat_9'],
        'vat_21': totals['vat_21'],

        # Line items
        'line_items': line_items,

        # Payment
        'payment_status': form_data.get('payment_status', 'unpaid'),
        'payment_date': None,
        'payment_method': None,
        'payment_reference': form_data.get('payment_reference', ''),

        # Additional info
        'notes': form_data.get('notes', ''),
        'reference': form_data.get('reference', ''),
        'currency': form_data.get('currency', 'EUR'),

        # Status
        'status': form_data.get('status', 'draft'),
        'sent_date': None,
        'pdf_path': None
    }

    return invoice

def format_currency(amount: float, currency: str = "EUR") -> str:
    """Format amount as currency.

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted string
    """
    if currency == "EUR":
        return f"€ {amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"

def get_payment_status_label(status: str) -> str:
    """Get Dutch label for payment status.

    Args:
        status: Payment status code

    Returns:
        Dutch label
    """
    labels = {
        'unpaid': 'Openstaand',
        'paid': 'Betaald',
        'overdue': 'Achterstallig',
        'cancelled': 'Geannuleerd'
    }
    return labels.get(status, status)

def get_invoice_status_label(status: str) -> str:
    """Get Dutch label for invoice status.

    Args:
        status: Invoice status code

    Returns:
        Dutch label
    """
    labels = {
        'draft': 'Concept',
        'sent': 'Verzonden',
        'paid': 'Betaald',
        'cancelled': 'Geannuleerd'
    }
    return labels.get(status, status)

def check_invoice_overdue(invoice: Dict) -> bool:
    """Check if invoice is overdue.

    Args:
        invoice: Invoice dictionary

    Returns:
        True if overdue
    """
    if invoice.get('payment_status') == 'paid':
        return False

    due_date = invoice.get('due_date')
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date)

    return datetime.now() > due_date

def get_days_overdue(invoice: Dict) -> int:
    """Get number of days invoice is overdue.

    Args:
        invoice: Invoice dictionary

    Returns:
        Number of days (0 if not overdue)
    """
    if not check_invoice_overdue(invoice):
        return 0

    due_date = invoice.get('due_date')
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date)

    delta = datetime.now() - due_date
    return delta.days

def calculate_vat_summary(invoices: List[Dict]) -> Dict:
    """Calculate VAT summary for multiple invoices.

    Args:
        invoices: List of invoice dictionaries

    Returns:
        VAT summary dictionary
    """
    vat_0 = Decimal('0')
    vat_9 = Decimal('0')
    vat_21 = Decimal('0')

    for invoice in invoices:
        vat_0 += Decimal(str(invoice.get('vat_0', 0)))
        vat_9 += Decimal(str(invoice.get('vat_9', 0)))
        vat_21 += Decimal(str(invoice.get('vat_21', 0)))

    total_vat = vat_0 + vat_9 + vat_21

    return {
        'vat_0': float(vat_0),
        'vat_9': float(vat_9),
        'vat_21': float(vat_21),
        'total_vat': float(total_vat)
    }

def get_top_clients(invoices: List[Dict], limit: int = 10) -> List[Dict]:
    """Get top clients by revenue.

    Args:
        invoices: List of invoice dictionaries
        limit: Number of top clients to return

    Returns:
        List of client dictionaries with totals
    """
    clients = {}

    for invoice in invoices:
        client_name = invoice.get('client_name', 'Onbekend')
        total = invoice.get('total_incl_vat', 0)

        if client_name in clients:
            clients[client_name]['total'] += total
            clients[client_name]['count'] += 1
        else:
            clients[client_name] = {
                'name': client_name,
                'total': total,
                'count': 1
            }

    # Sort by total descending
    sorted_clients = sorted(clients.values(), key=lambda x: x['total'], reverse=True)

    return sorted_clients[:limit]

def calculate_monthly_revenue(invoices: List[Dict]) -> Dict:
    """Calculate revenue by month.

    Args:
        invoices: List of invoice dictionaries

    Returns:
        Dictionary with month -> revenue mapping
    """
    monthly = {}

    for invoice in invoices:
        invoice_date = invoice.get('invoice_date')
        if isinstance(invoice_date, str):
            invoice_date = datetime.fromisoformat(invoice_date)

        month_key = invoice_date.strftime('%Y-%m')
        total = invoice.get('total_incl_vat', 0)

        if month_key in monthly:
            monthly[month_key] += total
        else:
            monthly[month_key] = total

    return monthly
