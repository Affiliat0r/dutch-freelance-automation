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
from utils.database_utils import get_receipt_stats, get_recent_receipts

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

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    # Get actual data from database
    try:
        stats = get_receipt_stats(date_range=(start_date, end_date))
        total_receipts = stats.get('total_receipts', 0)
        total_amount = stats.get('total_amount', 0.0)
        vat_refund = stats.get('total_vat', 0.0)
        processing_rate = (stats.get('processed', 0) / total_receipts * 100) if total_receipts > 0 else 0
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        total_receipts = 0
        total_amount = 0.0
        vat_refund = 0.0
        processing_rate = 0.0

    with col1:
        st.metric(
            label="Totaal Bonnen",
            value=total_receipts
        )

    with col2:
        st.metric(
            label="Totaal Bedrag",
            value=f"€ {total_amount:,.2f}"
        )

    with col3:
        st.metric(
            label="BTW Terug te Vorderen",
            value=f"€ {vat_refund:,.2f}"
        )

    with col4:
        st.metric(
            label="Verwerkingspercentage",
            value=f"{processing_rate:.1f}%"
        )

    # Show info if no data
    if total_receipts == 0:
        st.info("ℹ️ Nog geen bonnen verwerkt. Upload uw eerste bon om te beginnen!")
        if st.button("📤 Ga naar Upload Bonnen", use_container_width=True, type="primary"):
            st.session_state['selected_page'] = "Upload Bonnen"
            st.rerun()
        return

    st.markdown("---")

    # Get receipt data for charts
    try:
        receipts_list = get_recent_receipts(limit=1000)  # Get all for period
        if receipts_list:
            receipts_df = pd.DataFrame(receipts_list)

            # Charts section
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📈 Uitgaven per Categorie")

                if 'expense_category' in receipts_df.columns and 'total_incl_vat' in receipts_df.columns:
                    expense_data = receipts_df.groupby('expense_category')['total_incl_vat'].sum().reset_index()
                    expense_data.columns = ['Categorie', 'Bedrag']

                    if not expense_data.empty:
                        fig_pie = px.pie(
                            expense_data,
                            values='Bedrag',
                            names='Categorie',
                            color_discrete_sequence=px.colors.sequential.Blues_r
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        fig_pie.update_layout(height=400)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Geen categoriegegevens beschikbaar")
                else:
                    st.info("Geen categoriegegevens beschikbaar")

            with col2:
                st.subheader("📊 Maandelijkse Trend")

                if 'transaction_date' in receipts_df.columns and 'total_incl_vat' in receipts_df.columns:
                    receipts_df['transaction_date'] = pd.to_datetime(receipts_df['transaction_date'])
                    receipts_df['month'] = receipts_df['transaction_date'].dt.to_period('M')

                    monthly_data = receipts_df.groupby('month').agg({
                        'total_incl_vat': 'sum',
                        'vat_refund_amount': 'sum'
                    }).reset_index()

                    monthly_data['month'] = monthly_data['month'].dt.to_timestamp()

                    if not monthly_data.empty:
                        fig_line = go.Figure()
                        fig_line.add_trace(go.Scatter(
                            x=monthly_data['month'],
                            y=monthly_data['total_incl_vat'],
                            mode='lines+markers',
                            name='Uitgaven',
                            line=dict(color='#1f4788', width=2)
                        ))
                        fig_line.add_trace(go.Scatter(
                            x=monthly_data['month'],
                            y=monthly_data['vat_refund_amount'],
                            mode='lines+markers',
                            name='BTW Terugvordering',
                            line=dict(color='#3a6cb5', width=2)
                        ))
                        fig_line.update_layout(
                            height=400,
                            xaxis_title="Maand",
                            yaxis_title="Bedrag (€)",
                            hovermode='x unified'
                        )
                        st.plotly_chart(fig_line, use_container_width=True)
                    else:
                        st.info("Geen maandgegevens beschikbaar")
                else:
                    st.info("Geen maandgegevens beschikbaar")

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
        if st.button("🆕 Nieuwe Bon Uploaden", use_container_width=True):
            st.session_state['selected_page'] = "Upload Bonnen"
            st.rerun()

    with col2:
        if st.button("📋 Bonnen Beheren", use_container_width=True):
            st.session_state['selected_page'] = "Bonnen Beheer"
            st.rerun()

    with col3:
        if st.button("💾 Export naar Excel", use_container_width=True):
            st.session_state['selected_page'] = "Export/Rapporten"
            st.rerun()

    with col4:
        if st.button("🔄 Ververs Dashboard", use_container_width=True):
            st.rerun()

    # Footer with last update time
    st.markdown("---")
    st.caption(f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
