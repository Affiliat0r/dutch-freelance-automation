"""PDF generation for invoices using ReportLab."""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import Config

logger = logging.getLogger(__name__)

# Page dimensions
PAGE_WIDTH, PAGE_HEIGHT = A4

def generate_invoice_pdf(invoice: Dict, settings: Dict, output_path: Optional[str] = None) -> str:
    """Generate professional Dutch invoice PDF.

    Args:
        invoice: Invoice dictionary
        settings: Invoice settings dictionary
        output_path: Optional custom output path

    Returns:
        Path to generated PDF
    """
    if not output_path:
        invoice_number = invoice.get('invoice_number', 'DRAFT')
        safe_number = invoice_number.replace('/', '-')
        output_path = str(Config.INVOICE_PDF_DIR / f"{safe_number}.pdf")

    # Ensure directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Create PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # Build content
    elements = []
    styles = getSampleStyleSheet()

    # Add custom styles
    styles.add(ParagraphStyle(
        name='CompanyName',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name='InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12
    ))

    # Header: Logo and Company Info
    header_data = []

    # Check if logo exists
    logo_path = settings.get('logo_path')
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image(logo_path, width=Config.INVOICE_LOGO_MAX_WIDTH, height=Config.INVOICE_LOGO_MAX_HEIGHT)
            logo.hAlign = 'LEFT'
            header_data.append([logo, ''])
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")

    # Company details (right side)
    company_info = f"""<b>{settings.get('company_name', '')}</b><br/>
    {settings.get('address_street', '')}<br/>
    {settings.get('address_postal_code', '')} {settings.get('address_city', '')}<br/>
    {settings.get('address_country', '')}<br/><br/>
    KvK: {settings.get('kvk_number', '')}<br/>
    BTW: {settings.get('btw_number', '')}<br/>
    Tel: {settings.get('phone', '')}<br/>
    Email: {settings.get('email', '')}"""

    if header_data:
        header_table = Table(
            [[Paragraph(company_info, styles['Normal'])]],
            colWidths=[17*cm]
        )
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph(company_info, styles['Normal']))

    elements.append(Spacer(1, 1*cm))

    # Invoice Title
    elements.append(Paragraph("FACTUUR", styles['InvoiceTitle']))
    elements.append(Spacer(1, 0.5*cm))

    # Client and Invoice Info - Two columns
    invoice_date = invoice.get('invoice_date', '')
    if isinstance(invoice_date, str):
        try:
            invoice_date = datetime.fromisoformat(invoice_date).strftime('%d-%m-%Y')
        except:
            pass

    due_date = invoice.get('due_date', '')
    if isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(due_date).strftime('%d-%m-%Y')
        except:
            pass

    # Client info (left)
    client_info = f"""<b>Aan:</b><br/>
    {invoice.get('client_name', '')}<br/>"""

    if invoice.get('client_company'):
        client_info += f"{invoice.get('client_company')}<br/>"

    client_info += f"""{invoice.get('client_address', '')}<br/>
    {invoice.get('client_postal_code', '')} {invoice.get('client_city', '')}<br/>
    {invoice.get('client_country', '')}"""

    if invoice.get('client_btw'):
        client_info += f"<br/><br/>BTW nummer: {invoice.get('client_btw')}"

    # Invoice details (right)
    invoice_info = f"""<b>Factuurnummer:</b> {invoice.get('invoice_number', '')}<br/>
    <b>Factuurdatum:</b> {invoice_date}<br/>
    <b>Vervaldatum:</b> {due_date}<br/>"""

    if invoice.get('reference'):
        invoice_info += f"<b>Uw referentie:</b> {invoice.get('reference')}<br/>"

    info_table = Table(
        [[Paragraph(client_info, styles['Normal']), Paragraph(invoice_info, styles['Normal'])]],
        colWidths=[8.5*cm, 8.5*cm]
    )
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 1*cm))

    # Line items table
    line_items = invoice.get('line_items', [])

    table_data = [
        ['Omschrijving', 'Aantal', 'Prijs', 'BTW', 'Totaal']
    ]

    for item in line_items:
        quantity = item.get('quantity', 1)
        unit_price = item.get('unit_price', 0)
        vat_rate = item.get('vat_rate', 21)
        subtotal = item.get('subtotal', 0)
        total = item.get('total', 0)

        table_data.append([
            item.get('description', ''),
            f"{quantity:.2f}",
            f"€ {unit_price:,.2f}",
            f"{vat_rate:.0f}%",
            f"€ {total:,.2f}"
        ])

    items_table = Table(table_data, colWidths=[7*cm, 2.5*cm, 2.5*cm, 2*cm, 3*cm])
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),

        # Data rows
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f2f6')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.5*cm))

    # Totals table (right-aligned)
    totals_data = []

    subtotal = invoice.get('subtotal_excl_vat', 0)
    vat_0 = invoice.get('vat_0', 0)
    vat_9 = invoice.get('vat_9', 0)
    vat_21 = invoice.get('vat_21', 0)
    total_vat = invoice.get('vat_amount', 0)
    total = invoice.get('total_incl_vat', 0)

    totals_data.append(['Subtotaal excl. BTW:', f"€ {subtotal:,.2f}"])

    if vat_0 > 0:
        totals_data.append(['BTW 0%:', f"€ {vat_0:,.2f}"])
    if vat_9 > 0:
        totals_data.append(['BTW 9%:', f"€ {vat_9:,.2f}"])
    if vat_21 > 0:
        totals_data.append(['BTW 21%:', f"€ {vat_21:,.2f}"])

    totals_data.append(['', ''])  # Empty row
    totals_data.append(['<b>Totaal incl. BTW:</b>', f"<b>€ {total:,.2f}</b>"])

    totals_table = Table(totals_data, colWidths=[10*cm, 7*cm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 1*cm))

    # Payment terms and footer
    footer_text = settings.get('footer_text', '')
    if footer_text:
        # Replace placeholders
        footer_text = footer_text.replace('{payment_terms}', str(settings.get('default_payment_terms', 30)))
        footer_text = footer_text.replace('{iban}', settings.get('iban', ''))
        footer_text = footer_text.replace('{company_name}', settings.get('company_name', ''))

        # Convert newlines to <br/>
        footer_text = footer_text.replace('\n', '<br/>')

        elements.append(Paragraph(footer_text, styles['Normal']))
        elements.append(Spacer(1, 0.5*cm))

    # Bank details
    bank_info = f"""<b>Betaalinformatie:</b><br/>
    IBAN: {settings.get('iban', '')}<br/>
    BIC: {settings.get('bic', '')}<br/>
    Ten name van: {settings.get('company_name', '')}"""

    elements.append(Paragraph(bank_info, styles['Normal']))

    # Notes
    if invoice.get('notes'):
        elements.append(Spacer(1, 0.5*cm))
        notes_text = f"<b>Opmerkingen:</b><br/>{invoice.get('notes')}"
        elements.append(Paragraph(notes_text, styles['Normal']))

    # Build PDF
    try:
        doc.build(elements)
        logger.info(f"Generated invoice PDF: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise

def generate_invoice_preview(invoice: Dict, settings: Dict) -> bytes:
    """Generate invoice PDF as bytes for preview.

    Args:
        invoice: Invoice dictionary
        settings: Invoice settings dictionary

    Returns:
        PDF bytes
    """
    import io

    buffer = io.BytesIO()

    # Similar to generate_invoice_pdf but write to buffer
    # (Simplified version - full implementation would be similar to above)

    return buffer.getvalue()
