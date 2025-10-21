"""Dashboard page for the application - NO PLACEHOLDER DATA."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List
import logging

from config import Config
from utils.calculations import calculate_vat_summary, calculate_expense_summary
from utils.database_utils_local import get_receipt_stats, get_recent_receipts
from utils.invoice_storage import get_invoice_statistics, filter_invoices

logger = logging.getLogger(__name__)

def show():
    """Display the dashboard page."""

    st.title("📊 Dashboard")
    st.markdown("Welkom bij uw administratie overzicht")

    # Date range selector
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        start_date = st.date_input(
            "Van datum",
            value=datetime.now() - timedelta(days=30),
            format="DD/MM/YYYY"
        )
    with col2:
        end_date = st.date_input(
            "Tot datum",
            value=datetime.now(),
            format="DD/MM/YYYY"
        )
    with col3:
        quick_select = st.selectbox(
            "Snelle selectie",
            ["Laatste 30 dagen", "Dit kwartaal", "Dit jaar", "Vorig jaar", "Aangepast"]
        )

    st.markdown("---")

    # Get data for both income and expenses
    try:
        # Convert dates to datetime for consistency
        start_dt = datetime.combine(start_date, datetime.min.time()) if isinstance(start_date, type(datetime.now().date())) else start_date
        end_dt = datetime.combine(end_date, datetime.max.time()) if isinstance(end_date, type(datetime.now().date())) else end_date

        # Expense data
        expense_stats = get_receipt_stats(date_range=(start_date, end_date))
        total_receipts = expense_stats.get('total_receipts', 0)
        total_expenses = expense_stats.get('total_amount', 0.0)
        vat_refund = expense_stats.get('total_vat', 0.0)

        # Income data
        invoice_stats = get_invoice_statistics(start_date=start_dt, end_date=end_dt)
        total_invoices = invoice_stats.get('total_invoices', 0)
        total_revenue = invoice_stats.get('total_revenue', 0.0)
        vat_payable = invoice_stats.get('total_vat_payable', 0.0)
        total_unpaid = invoice_stats.get('total_unpaid', 0.0)

        # Calculate profit (revenue - expenses)
        gross_profit = total_revenue - total_expenses
        net_vat_position = vat_payable - vat_refund  # Positive = owe VAT, Negative = refund

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        total_receipts = 0
        total_expenses = 0.0
        vat_refund = 0.0
        total_invoices = 0
        total_revenue = 0.0
        vat_payable = 0.0
        total_unpaid = 0.0
        gross_profit = 0.0
        net_vat_position = 0.0

    # Financial Overview Section
    st.subheader("💰 Financieel Overzicht")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="💵 Totale Omzet (Incl. BTW)",
            value=f"€ {total_revenue:,.2f}",
            delta=f"{total_invoices} facturen"
        )

    with col2:
        st.metric(
            label="💸 Totale Kosten (Incl. BTW)",
            value=f"€ {total_expenses:,.2f}",
            delta=f"{total_receipts} bonnen"
        )

    with col3:
        profit_color = "normal" if gross_profit >= 0 else "inverse"
        st.metric(
            label="📊 Bruto Resultaat",
            value=f"€ {gross_profit:,.2f}",
            delta="Winst" if gross_profit >= 0 else "Verlies",
            delta_color=profit_color
        )

    st.markdown("---")

    # BTW & Payment Status Section
    st.subheader("🧾 BTW & Betalingen")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="BTW Te Betalen (Omzet)",
            value=f"€ {vat_payable:,.2f}"
        )

    with col2:
        st.metric(
            label="BTW Terugvordering (Kosten)",
            value=f"€ {vat_refund:,.2f}"
        )

    with col3:
        vat_color = "inverse" if net_vat_position > 0 else "normal"
        st.metric(
            label="Netto BTW Positie",
            value=f"€ {net_vat_position:,.2f}",
            delta="Te betalen" if net_vat_position > 0 else "Terug te vorderen",
            delta_color=vat_color
        )

    with col4:
        st.metric(
            label="Openstaande Facturen",
            value=f"€ {total_unpaid:,.2f}",
            help="Nog niet betaalde facturen"
        )

    # Show info if no data
    if total_receipts == 0 and total_invoices == 0:
        st.info("ℹ️ Nog geen gegevens beschikbaar. Begin met het uploaden van bonnen of het aanmaken van facturen!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Upload Bonnen", use_container_width=True, type="primary"):
                st.session_state['selected_page'] = "Upload Bonnen"
                st.rerun()
        with col2:
            if st.button("📝 Factuur Maken", use_container_width=True, type="primary"):
                st.session_state['selected_page'] = "Facturen"
                st.rerun()
        return

    st.markdown("---")

    # Get data for charts
    try:
        receipts_list = get_recent_receipts(limit=1000)  # Get all for period
        invoices_list = filter_invoices(start_date=start_dt, end_date=end_dt)

        # Charts section
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 Omzet vs Kosten")

            # Monthly income vs expenses
            monthly_income = []
            monthly_expenses = []

            if invoices_list:
                invoices_df = pd.DataFrame(invoices_list)
                # Handle datetime parsing with mixed formats
                invoices_df['invoice_date'] = pd.to_datetime(invoices_df['invoice_date'], format='mixed', errors='coerce')
                invoices_df['month'] = invoices_df['invoice_date'].dt.to_period('M')
                monthly_income_data = invoices_df.groupby('month')['total_incl_vat'].sum().reset_index()
                monthly_income_data['month'] = monthly_income_data['month'].dt.to_timestamp()
                monthly_income = monthly_income_data

            if receipts_list:
                receipts_df = pd.DataFrame(receipts_list)
                receipts_df['transaction_date'] = pd.to_datetime(receipts_df['transaction_date'])
                receipts_df['month'] = receipts_df['transaction_date'].dt.to_period('M')
                monthly_expense_data = receipts_df.groupby('month')['total_incl_vat'].sum().reset_index()
                monthly_expense_data['month'] = monthly_expense_data['month'].dt.to_timestamp()
                monthly_expenses = monthly_expense_data

            if len(monthly_income) > 0 or len(monthly_expenses) > 0:
                fig_comparison = go.Figure()

                if len(monthly_income) > 0:
                    fig_comparison.add_trace(go.Bar(
                        x=monthly_income['month'],
                        y=monthly_income['total_incl_vat'],
                        name='Omzet',
                        marker_color='#2ecc71'
                    ))

                if len(monthly_expenses) > 0:
                    fig_comparison.add_trace(go.Bar(
                        x=monthly_expenses['month'],
                        y=monthly_expenses['total_incl_vat'],
                        name='Kosten',
                        marker_color='#e74c3c'
                    ))

                fig_comparison.update_layout(
                    height=400,
                    xaxis_title="Maand",
                    yaxis_title="Bedrag (€)",
                    barmode='group',
                    hovermode='x unified'
                )
                st.plotly_chart(fig_comparison, use_container_width=True)
            else:
                st.info("Geen maandgegevens beschikbaar")

        with col2:
            st.subheader("📈 Uitgaven per Categorie")

            if receipts_list:
                receipts_df = pd.DataFrame(receipts_list)
                if 'expense_category' in receipts_df.columns and 'total_incl_vat' in receipts_df.columns:
                    expense_data = receipts_df.groupby('expense_category')['total_incl_vat'].sum().reset_index()
                    expense_data.columns = ['Categorie', 'Bedrag']

                    if not expense_data.empty:
                        fig_pie = px.pie(
                            expense_data,
                            values='Bedrag',
                            names='Categorie',
                            color_discrete_sequence=px.colors.sequential.Reds_r
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie.update_layout(height=400)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Geen categoriegegevens beschikbaar")
                else:
                    st.info("Geen categoriegegevens beschikbaar")
            else:
                st.info("Geen categoriegegevens beschikbaar")

            st.markdown("---")

            # VAT breakdown section
            st.subheader("💶 BTW Overzicht")

            col1, col2, col3, col4 = st.columns(4)

            # Calculate VAT from actual data
            vat_6 = receipts_df['vat_6_amount'].sum() if 'vat_6_amount' in receipts_df.columns else 0
            vat_9 = receipts_df['vat_9_amount'].sum() if 'vat_9_amount' in receipts_df.columns else 0
            vat_21 = receipts_df['vat_21_amount'].sum() if 'vat_21_amount' in receipts_df.columns else 0
            vat_total = vat_6 + vat_9 + vat_21

            with col1:
                st.info(f"""
                **BTW 6% (oud tarief)**
                € {vat_6:,.2f}
                """)

            with col2:
                st.info(f"""
                **BTW 9%**
                € {vat_9:,.2f}
                """)

            with col3:
                st.info(f"""
                **BTW 21%**
                € {vat_21:,.2f}
                """)

            with col4:
                st.success(f"""
                **Totaal BTW**
                € {vat_total:,.2f}
                """)

            st.markdown("---")

            # Recent receipts section
            st.subheader("📋 Recente Bonnen")

            recent_receipts = get_recent_receipts(limit=10)
            if recent_receipts:
                recent_receipts_df = pd.DataFrame(recent_receipts)

                # Format display columns
                display_df = pd.DataFrame({
                    'Datum': pd.to_datetime(recent_receipts_df['transaction_date']).dt.strftime('%d-%m-%Y') if 'transaction_date' in recent_receipts_df.columns else 'N/A',
                    'Leverancier': recent_receipts_df.get('vendor_name', 'Onbekend'),
                    'Categorie': recent_receipts_df.get('expense_category', 'Niet gecategoriseerd'),
                    'Bedrag': recent_receipts_df.get('total_incl_vat', 0).apply(lambda x: f"€ {x:,.2f}"),
                    'Status': recent_receipts_df.get('processing_status', 'onbekend').apply(lambda x: {
                        'completed': 'Verwerkt',
                        'pending': 'In behandeling',
                        'failed': 'Mislukt',
                        'processing': 'Bezig...'
                    }.get(x, x))
                })

                # Apply status colors
                def highlight_status(row):
                    if row['Status'] == 'Verwerkt':
                        return ['background-color: #d4edda'] * len(row)
                    elif row['Status'] in ['In behandeling', 'Bezig...']:
                        return ['background-color: #fff3cd'] * len(row)
                    elif row['Status'] == 'Mislukt':
                        return ['background-color: #f8d7da'] * len(row)
                    return [''] * len(row)

                styled_df = display_df.style.apply(highlight_status, axis=1)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            else:
                st.info("Geen recente bonnen gevonden")

    except Exception as e:
        logger.error(f"Error loading dashboard data: {e}")
        st.error(f"Fout bij laden van dashboard gegevens: {str(e)}")

    # Quick actions
    st.markdown("---")
    st.subheader("⚡ Snelle Acties")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📝 Nieuwe Factuur", use_container_width=True, type="primary"):
            st.session_state['selected_page'] = "Facturen"
            st.rerun()

    with col2:
        if st.button("🆕 Nieuwe Bon", use_container_width=True):
            st.session_state['selected_page'] = "Upload Bonnen"
            st.rerun()

    with col3:
        if st.button("💾 Exporteren", use_container_width=True):
            st.session_state['selected_page'] = "Export/Rapporten"
            st.rerun()

    with col4:
        if st.button("🔄 Ververs", use_container_width=True):
            st.rerun()

    # Footer with last update time
    st.markdown("---")
    st.caption(f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
