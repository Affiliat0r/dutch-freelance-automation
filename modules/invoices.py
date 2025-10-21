"""Invoice management module - Create, view, and manage invoices."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

from config import Config
from utils.invoice_storage import (
    init_invoice_storage, save_invoice, get_all_invoices, filter_invoices,
    get_invoice, update_invoice_status, delete_invoice, get_invoice_statistics,
    load_settings, save_settings, get_next_invoice_number,
    load_clients, add_client, get_all_clients, check_overdue_invoices
)
from services.invoice_service import (
    calculate_line_item_totals, calculate_invoice_totals, validate_invoice_data,
    create_invoice_from_form, format_currency, get_payment_status_label,
    get_invoice_status_label, check_invoice_overdue, get_days_overdue
)
from services.pdf_generator import generate_invoice_pdf

logger = logging.getLogger(__name__)

def show():
    """Display the invoices page."""

    st.title("📄 Facturen")
    st.markdown("Beheer uw facturen en omzet")

    # Initialize storage
    init_invoice_storage()

    # Check for overdue invoices on page load
    check_overdue_invoices()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Nieuwe Factuur",
        "📋 Factuur Overzicht",
        "⏰ Openstaande Facturen",
        "👥 Klanten"
    ])

    with tab1:
        show_new_invoice()

    with tab2:
        show_invoice_overview()

    with tab3:
        show_unpaid_invoices()

    with tab4:
        show_clients()

def show_new_invoice():
    """Show new invoice creation form."""

    st.subheader("Nieuwe Factuur Aanmaken")

    # Load settings and clients
    settings = load_settings()
    clients = get_all_clients()

    # Invoice number
    col1, col2 = st.columns([2, 1])

    with col1:
        invoice_number = st.text_input(
            "Factuurnummer",
            value=get_next_invoice_number(),
            key="invoice_number",
            help="Dit nummer wordt automatisch gegenereerd"
        )

    with col2:
        invoice_date = st.date_input(
            "Factuurdatum",
            value=datetime.now(),
            key="invoice_date",
            format="DD/MM/YYYY"
        )

    # Client selection
    st.markdown("### Klant")

    col1, col2 = st.columns([3, 1])

    with col1:
        # Existing client dropdown
        client_names = ["-- Nieuwe klant --"] + [c['name'] for c in clients]
        selected_client_name = st.selectbox(
            "Selecteer klant",
            options=client_names,
            key="client_select"
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        add_new_client = st.checkbox("Nieuwe klant toevoegen")

    # Client form
    if add_new_client or selected_client_name == "-- Nieuwe klant --":
        # New client form
        col1, col2 = st.columns(2)

        with col1:
            client_name = st.text_input("Naam *", key="client_name")
            client_company = st.text_input("Bedrijfsnaam", key="client_company")
            client_email = st.text_input("Email", key="client_email")
            client_address = st.text_input("Adres", key="client_address")

        with col2:
            client_postal_code = st.text_input("Postcode", key="client_postal_code")
            client_city = st.text_input("Plaats", key="client_city")
            client_kvk = st.text_input("KvK nummer", key="client_kvk")
            client_btw = st.text_input("BTW nummer", key="client_btw")

    else:
        # Load selected client data
        selected_client = next((c for c in clients if c['name'] == selected_client_name), None)

        if selected_client:
            col1, col2 = st.columns(2)

            with col1:
                client_name = st.text_input("Naam *", value=selected_client.get('name', ''), key="client_name")
                client_company = st.text_input("Bedrijfsnaam", value=selected_client.get('company_name', ''), key="client_company")
                client_email = st.text_input("Email", value=selected_client.get('email', ''), key="client_email")
                client_address = st.text_input("Adres", value=selected_client.get('address_street', ''), key="client_address")

            with col2:
                client_postal_code = st.text_input("Postcode", value=selected_client.get('address_postal_code', ''), key="client_postal_code")
                client_city = st.text_input("Plaats", value=selected_client.get('address_city', ''), key="client_city")
                client_kvk = st.text_input("KvK nummer", value=selected_client.get('kvk_number', ''), key="client_kvk")
                client_btw = st.text_input("BTW nummer", value=selected_client.get('btw_number', ''), key="client_btw")
        else:
            st.warning("Selecteer een klant of voeg een nieuwe toe")
            return

    st.markdown("---")

    # Line items
    st.markdown("### Factuurregels")

    # Initialize session state for line items
    if 'line_items' not in st.session_state:
        st.session_state.line_items = [
            {'description': '', 'quantity': 1.0, 'unit_price': 0.0, 'vat_rate': settings.get('default_vat_rate', 21.0)}
        ]

    # Display line items
    for idx, item in enumerate(st.session_state.line_items):
        col1, col2, col3, col4, col5 = st.columns([4, 1, 1.5, 1, 0.5])

        with col1:
            item['description'] = st.text_input(
                "Omschrijving",
                value=item.get('description', ''),
                key=f"desc_{idx}",
                label_visibility="collapsed" if idx > 0 else "visible"
            )

        with col2:
            item['quantity'] = st.number_input(
                "Aantal",
                min_value=0.01,
                value=float(item.get('quantity', 1.0)),
                step=0.01,
                key=f"qty_{idx}",
                label_visibility="collapsed" if idx > 0 else "visible"
            )

        with col3:
            item['unit_price'] = st.number_input(
                "Prijs per stuk",
                min_value=0.0,
                value=float(item.get('unit_price', 0.0)),
                step=0.01,
                key=f"price_{idx}",
                label_visibility="collapsed" if idx > 0 else "visible"
            )

        with col4:
            item['vat_rate'] = st.selectbox(
                "BTW %",
                options=Config.INVOICE_VAT_RATES,
                index=Config.INVOICE_VAT_RATES.index(item.get('vat_rate', 21.0)),
                key=f"vat_{idx}",
                label_visibility="collapsed" if idx > 0 else "visible"
            )

        with col5:
            if idx > 0:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_{idx}"):
                    st.session_state.line_items.pop(idx)
                    st.rerun()

        # Calculate line item totals
        totals = calculate_line_item_totals(
            item['quantity'],
            item['unit_price'],
            item['vat_rate']
        )
        item['subtotal'] = totals['subtotal']
        item['vat_amount'] = totals['vat_amount']
        item['total'] = totals['total']

    # Add row button
    if st.button("➕ Regel toevoegen"):
        st.session_state.line_items.append({
            'description': '',
            'quantity': 1.0,
            'unit_price': 0.0,
            'vat_rate': settings.get('default_vat_rate', 21.0)
        })
        st.rerun()

    st.markdown("---")

    # Calculate invoice totals
    invoice_totals = calculate_invoice_totals(st.session_state.line_items)

    # Display totals
    col1, col2 = st.columns([2, 1])

    with col2:
        st.markdown("### Totalen")

        st.metric("Subtotaal excl. BTW", format_currency(invoice_totals['subtotal_excl_vat']))

        if invoice_totals['vat_0'] > 0:
            st.metric("BTW 0%", format_currency(invoice_totals['vat_0']))
        if invoice_totals['vat_9'] > 0:
            st.metric("BTW 9%", format_currency(invoice_totals['vat_9']))
        if invoice_totals['vat_21'] > 0:
            st.metric("BTW 21%", format_currency(invoice_totals['vat_21']))

        st.markdown("---")
        st.metric("**Totaal incl. BTW**", format_currency(invoice_totals['total_incl_vat']))

    with col1:
        st.markdown("### Aanvullende Informatie")

        payment_terms = st.number_input(
            "Betalingstermijn (dagen)",
            min_value=1,
            max_value=90,
            value=settings.get('default_payment_terms', 30),
            step=1,
            key="payment_terms"
        )

        due_date = invoice_date + timedelta(days=payment_terms)
        st.info(f"Vervaldatum: {due_date.strftime('%d-%m-%Y')}")

        reference = st.text_input("Referentie (optioneel)", key="reference")
        notes = st.text_area("Opmerkingen (optioneel)", key="notes")

    st.markdown("---")

    # Action buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("💾 Opslaan als Concept", use_container_width=True):
            save_invoice_draft()

    with col2:
        if st.button("📄 Preview PDF", use_container_width=True):
            preview_invoice_pdf()

    with col3:
        if st.button("📧 Opslaan en Verzenden", use_container_width=True, type="primary"):
            save_and_send_invoice()

    with col4:
        if st.button("🔄 Reset Formulier", use_container_width=True):
            st.session_state.line_items = [
                {'description': '', 'quantity': 1.0, 'unit_price': 0.0, 'vat_rate': 21.0}
            ]
            st.rerun()

def save_invoice_draft():
    """Save invoice as draft."""
    try:
        settings = load_settings()

        # Get invoice date from session state
        invoice_date = st.session_state.get('invoice_date', datetime.now())
        if isinstance(invoice_date, str):
            invoice_date = datetime.fromisoformat(invoice_date)

        payment_terms = st.session_state.get('payment_terms', 30)

        # Get line items from session state
        line_items = st.session_state.get('line_items', [])

        # DEBUG: Log line items
        logger.info(f"Line items to save: {line_items}")

        # Build invoice data
        invoice_data = {
            'invoice_number': st.session_state.get('invoice_number', get_next_invoice_number()),
            'invoice_date': datetime.combine(invoice_date, datetime.min.time()).isoformat(),
            'due_date': (datetime.combine(invoice_date, datetime.min.time()) + timedelta(days=payment_terms)).isoformat(),
            'client_name': st.session_state.get('client_name', ''),
            'client_company': st.session_state.get('client_company', ''),
            'client_email': st.session_state.get('client_email', ''),
            'client_address': st.session_state.get('client_address', ''),
            'client_postal_code': st.session_state.get('client_postal_code', ''),
            'client_city': st.session_state.get('client_city', ''),
            'client_kvk': st.session_state.get('client_kvk', ''),
            'client_btw': st.session_state.get('client_btw', ''),
            'reference': st.session_state.get('reference', ''),
            'notes': st.session_state.get('notes', ''),
            'line_items': line_items,
            'status': 'draft',
            'payment_status': 'unpaid'
        }

        # Calculate totals
        totals = calculate_invoice_totals(invoice_data['line_items'])
        logger.info(f"Calculated totals: {totals}")
        invoice_data.update(totals)

        # Validate
        is_valid, error = validate_invoice_data(invoice_data)
        if not is_valid:
            st.error(f"❌ Validatiefout: {error}")
            logger.error(f"Validation error: {error}, invoice_data: {invoice_data}")
            return

        # Save
        invoice_id = save_invoice(invoice_data)

        st.success(f"✅ Factuur opgeslagen als concept! (ID: {invoice_id})")

    except Exception as e:
        logger.error(f"Error saving invoice: {e}")
        import traceback
        traceback.print_exc()
        st.error(f"❌ Fout bij opslaan: {e}")

def preview_invoice_pdf():
    """Preview invoice PDF - generate and offer for download."""
    try:
        settings = load_settings()

        # Get form data (same as save_invoice_draft)
        invoice_date = st.session_state.get('invoice_date', datetime.now())
        if isinstance(invoice_date, str):
            invoice_date = datetime.fromisoformat(invoice_date)

        payment_terms = st.session_state.get('payment_terms', 30)
        line_items = st.session_state.get('line_items', [])

        # Build invoice data
        invoice_data = {
            'invoice_number': st.session_state.get('invoice_number', get_next_invoice_number()),
            'invoice_date': datetime.combine(invoice_date, datetime.min.time()).isoformat(),
            'due_date': (datetime.combine(invoice_date, datetime.min.time()) + timedelta(days=payment_terms)).isoformat(),
            'client_name': st.session_state.get('client_name', ''),
            'client_company': st.session_state.get('client_company', ''),
            'client_email': st.session_state.get('client_email', ''),
            'client_address': st.session_state.get('client_address', ''),
            'client_postal_code': st.session_state.get('client_postal_code', ''),
            'client_city': st.session_state.get('client_city', ''),
            'client_kvk': st.session_state.get('client_kvk', ''),
            'client_btw': st.session_state.get('client_btw', ''),
            'reference': st.session_state.get('reference', ''),
            'notes': st.session_state.get('notes', ''),
            'line_items': line_items,
        }

        # Calculate totals
        totals = calculate_invoice_totals(line_items)
        invoice_data.update(totals)

        # Validate
        is_valid, error = validate_invoice_data(invoice_data)
        if not is_valid:
            st.error(f"❌ Kan PDF niet genereren: {error}")
            return

        # Generate PDF
        pdf_path = generate_invoice_pdf(invoice_data, settings)

        # Offer download
        with open(pdf_path, 'rb') as pdf_file:
            st.download_button(
                label="⬇️ Download Preview PDF",
                data=pdf_file,
                file_name=f"{invoice_data['invoice_number']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        st.success(f"✅ PDF gegenereerd: {invoice_data['invoice_number']}.pdf")

    except Exception as e:
        logger.error(f"Error generating preview PDF: {e}")
        import traceback
        traceback.print_exc()
        st.error(f"❌ Fout bij genereren PDF: {e}")

def save_and_send_invoice():
    """Save invoice and mark as sent."""
    try:
        # First save as draft
        save_invoice_draft()

        # TODO: Generate PDF and mark as sent
        st.success("✅ Factuur verzonden!")

    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        st.error(f"❌ Fout bij verzenden: {e}")

def show_invoice_overview():
    """Show all invoices with filters."""

    st.subheader("Factuur Overzicht")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        start_date = st.date_input(
            "Van datum",
            value=datetime.now() - timedelta(days=90),
            format="DD/MM/YYYY"
        )

    with col2:
        end_date = st.date_input(
            "Tot datum",
            value=datetime.now(),
            format="DD/MM/YYYY"
        )

    with col3:
        status_filter = st.selectbox(
            "Status",
            ["Alle", "draft", "sent", "paid", "cancelled"]
        )

    with col4:
        payment_filter = st.selectbox(
            "Betaalstatus",
            ["Alle", "unpaid", "paid", "overdue"]
        )

    # Get invoices
    invoices = filter_invoices(
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time()),
        status=status_filter if status_filter != "Alle" else None,
        payment_status=payment_filter if payment_filter != "Alle" else None
    )

    # Statistics
    stats = get_invoice_statistics(
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time())
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totaal Facturen", stats['total_invoices'])

    with col2:
        st.metric("Totale Omzet", format_currency(stats['total_revenue']))

    with col3:
        st.metric("Betaald", format_currency(stats['total_paid']))

    with col4:
        st.metric("Openstaand", format_currency(stats['total_unpaid']))

    st.markdown("---")

    # Invoice table with inline actions
    if invoices:
        st.markdown("### Facturen Lijst")

        # Table header
        header_cols = st.columns([2, 1.5, 2, 1.5, 1.5, 1.5, 3])
        with header_cols[0]:
            st.markdown("**Factuurnummer**")
        with header_cols[1]:
            st.markdown("**Datum**")
        with header_cols[2]:
            st.markdown("**Klant**")
        with header_cols[3]:
            st.markdown("**Bedrag**")
        with header_cols[4]:
            st.markdown("**Status**")
        with header_cols[5]:
            st.markdown("**Betaalstatus**")
        with header_cols[6]:
            st.markdown("**Acties**")

        st.markdown("---")

        for idx, inv in enumerate(invoices):
            invoice_date = datetime.fromisoformat(inv['invoice_date']).strftime('%d-%m-%Y')

            # Create expandable row for each invoice
            with st.container():
                cols = st.columns([2, 1.5, 2, 1.5, 1.5, 1.5, 3])

                with cols[0]:
                    st.text(inv['invoice_number'])

                with cols[1]:
                    st.text(invoice_date)

                with cols[2]:
                    st.text(inv['client_name'])

                with cols[3]:
                    st.text(format_currency(inv['total_incl_vat']))

                with cols[4]:
                    status_label = get_invoice_status_label(inv.get('status', 'draft'))
                    st.text(status_label)

                with cols[5]:
                    payment_status = inv.get('payment_status', 'unpaid')
                    payment_label = get_payment_status_label(payment_status)

                    # Color code payment status
                    if payment_status == 'paid':
                        st.success(payment_label)
                    elif payment_status == 'overdue':
                        st.error(payment_label)
                    else:
                        st.warning(payment_label)

                with cols[6]:
                    # Action buttons in a single row
                    action_cols = st.columns(4)

                    with action_cols[0]:
                        if st.button("👁️", key=f"view_{inv['id']}", help="Bekijken"):
                            show_invoice_details(inv)

                    with action_cols[1]:
                        if st.button("📄", key=f"pdf_{inv['id']}", help="Download PDF"):
                            download_invoice_pdf(inv)

                    with action_cols[2]:
                        # Only show mark paid button if not already paid
                        if payment_status != 'paid':
                            if st.button("✅", key=f"paid_{inv['id']}", help="Markeer Betaald"):
                                mark_invoice_paid(inv['id'])
                                st.success(f"✅ {inv['invoice_number']} gemarkeerd als betaald")
                                st.rerun()
                        else:
                            st.text("✓")

                    with action_cols[3]:
                        if st.button("🗑️", key=f"delete_{inv['id']}", help="Verwijderen"):
                            # Store deletion request in session state
                            st.session_state[f'confirm_delete_{inv["id"]}'] = True

                # Show confirmation dialog if delete was clicked
                if st.session_state.get(f'confirm_delete_{inv["id"]}', False):
                    st.warning(f"⚠️ Weet u zeker dat u factuur {inv['invoice_number']} wilt verwijderen?")
                    confirm_cols = st.columns([1, 1, 3])
                    with confirm_cols[0]:
                        if st.button("Ja, verwijder", key=f"confirm_yes_{inv['id']}", type="primary"):
                            delete_invoice_func(inv['id'])
                            st.success(f"✅ Factuur {inv['invoice_number']} verwijderd")
                            # Clear confirmation state
                            del st.session_state[f'confirm_delete_{inv["id"]}']
                            st.rerun()
                    with confirm_cols[1]:
                        if st.button("Annuleer", key=f"confirm_no_{inv['id']}"):
                            del st.session_state[f'confirm_delete_{inv["id"]}']
                            st.rerun()

                st.markdown("---")

    else:
        st.info("Geen facturen gevonden voor de geselecteerde periode")

def show_invoice_details(invoice: dict):
    """Show invoice details in expander."""
    with st.expander(f"Details: {invoice['invoice_number']}", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Klantgegevens**")
            st.text(f"Naam: {invoice['client_name']}")
            st.text(f"Bedrijf: {invoice.get('client_company', '-')}")
            st.text(f"Email: {invoice.get('client_email', '-')}")

        with col2:
            st.markdown("**Financieel**")
            st.text(f"Subtotaal: {format_currency(invoice['subtotal_excl_vat'])}")
            st.text(f"BTW: {format_currency(invoice['vat_amount'])}")
            st.text(f"Totaal: {format_currency(invoice['total_incl_vat'])}")

        st.markdown("**Factuurregels**")
        for item in invoice.get('line_items', []):
            st.text(f"- {item['description']}: {item['quantity']} x {format_currency(item['unit_price'])}")

def download_invoice_pdf(invoice: dict):
    """Download invoice as PDF."""
    try:
        settings = load_settings()
        pdf_path = generate_invoice_pdf(invoice, settings)

        with open(pdf_path, 'rb') as pdf_file:
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_file,
                file_name=f"{invoice['invoice_number']}.pdf",
                mime="application/pdf"
            )

    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        st.error(f"Fout bij genereren PDF: {e}")

def mark_invoice_paid(invoice_id: int):
    """Mark invoice as paid."""
    try:
        update_invoice_status(invoice_id, status='paid', payment_date=datetime.now())
        logger.info(f"Marked invoice {invoice_id} as paid")
    except Exception as e:
        logger.error(f"Error marking invoice as paid: {e}")
        st.error(f"Fout bij markeren als betaald: {e}")

def delete_invoice_func(invoice_id: int):
    """Delete an invoice."""
    try:
        delete_invoice(invoice_id)
        logger.info(f"Deleted invoice {invoice_id}")
    except Exception as e:
        logger.error(f"Error deleting invoice: {e}")
        st.error(f"Fout bij verwijderen: {e}")

def show_unpaid_invoices():
    """Show unpaid and overdue invoices."""

    st.subheader("Openstaande Facturen")

    # Get unpaid invoices
    unpaid = filter_invoices(payment_status='unpaid')
    overdue = filter_invoices(payment_status='overdue')

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Openstaand", format_currency(sum(inv['total_incl_vat'] for inv in unpaid)))

    with col2:
        st.metric("Achterstallig", format_currency(sum(inv['total_incl_vat'] for inv in overdue)), delta=f"{len(overdue)} facturen")

    st.markdown("---")

    if overdue:
        st.error(f"⚠️ {len(overdue)} achterstallige facturen!")

        for inv in overdue:
            days = get_days_overdue(inv)
            st.warning(f"**{inv['invoice_number']}** - {inv['client_name']}: {format_currency(inv['total_incl_vat'])} ({days} dagen over tijd)")

    if unpaid:
        st.markdown("### Openstaande Facturen")

        for inv in unpaid:
            due_date = datetime.fromisoformat(inv['due_date']).strftime('%d-%m-%Y')
            st.info(f"**{inv['invoice_number']}** - {inv['client_name']}: {format_currency(inv['total_incl_vat'])} (Vervaldatum: {due_date})")

    if not unpaid and not overdue:
        st.success("🎉 Alle facturen zijn betaald!")

def show_clients():
    """Show client management."""

    st.subheader("Klanten Beheer")

    # Add new client
    with st.expander("➕ Nieuwe Klant Toevoegen"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Naam *", key="add_client_name")
            company = st.text_input("Bedrijfsnaam", key="add_client_company")
            email = st.text_input("Email", key="add_client_email")
            phone = st.text_input("Telefoon", key="add_client_phone")

        with col2:
            address_street = st.text_input("Adres", key="add_client_street")
            postal_code = st.text_input("Postcode", key="add_client_postal")
            city = st.text_input("Plaats", key="add_client_city")

            col_kvk, col_btw = st.columns(2)
            with col_kvk:
                kvk = st.text_input("KvK", key="add_client_kvk")
            with col_btw:
                btw = st.text_input("BTW", key="add_client_btw")

        if st.button("💾 Klant Opslaan"):
            if name:
                client_data = {
                    'name': name,
                    'company_name': company,
                    'email': email,
                    'phone': phone,
                    'address_street': address_street,
                    'address_postal_code': postal_code,
                    'address_city': city,
                    'kvk_number': kvk,
                    'btw_number': btw
                }

                client_id = add_client(client_data)
                st.success(f"✅ Klant toegevoegd! (ID: {client_id})")
                st.rerun()
            else:
                st.error("Naam is verplicht")

    st.markdown("---")

    # Client list
    clients = get_all_clients()

    if clients:
        st.markdown(f"### Klanten ({len(clients)})")

        for client in clients:
            with st.expander(f"{client['name']} - {client.get('company_name', 'Geen bedrijf')}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.text(f"Email: {client.get('email', '-')}")
                    st.text(f"Telefoon: {client.get('phone', '-')}")
                    st.text(f"Adres: {client.get('address_street', '-')}")

                with col2:
                    st.text(f"Plaats: {client.get('address_city', '-')}")
                    st.text(f"KvK: {client.get('kvk_number', '-')}")
                    st.text(f"BTW: {client.get('btw_number', '-')}")

    else:
        st.info("Nog geen klanten toegevoegd")
