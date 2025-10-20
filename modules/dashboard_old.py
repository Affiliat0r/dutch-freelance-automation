"""Dashboard page for the application."""

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

    # Sample data for demonstration
    total_receipts = 127
    total_amount = 15234.56
    vat_refund = 2456.78
    processing_rate = 95.3

    with col1:
        st.metric(
            label="Totaal Bonnen",
            value=total_receipts,
            delta="12 deze maand",
            delta_color="normal"
        )

    with col2:
        st.metric(
            label="Totaal Bedrag",
            value=f"€ {total_amount:,.2f}",
            delta=f"€ {1234.56:,.2f}",
            delta_color="normal"
        )

    with col3:
        st.metric(
            label="BTW Terug te Vorderen",
            value=f"€ {vat_refund:,.2f}",
            delta=f"€ {234.56:,.2f}",
            delta_color="normal"
        )

    with col4:
        st.metric(
            label="Verwerkingspercentage",
            value=f"{processing_rate}%",
            delta="2.3%",
            delta_color="normal"
        )

    st.markdown("---")

    # Charts section
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Uitgaven per Categorie")

        # Sample expense data
        expense_data = pd.DataFrame({
            'Categorie': Config.EXPENSE_CATEGORIES,
            'Bedrag': [3456.78, 2345.67, 1234.56, 987.65, 876.54, 765.43, 654.32]
        })

        fig_pie = px.pie(
            expense_data,
            values='Bedrag',
            names='Categorie',
            color_discrete_sequence=px.colors.sequential.Blues_r
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.subheader("📊 Maandelijkse Trend")

        # Sample monthly data
        months = pd.date_range(start='2024-01', periods=12, freq='M')
        monthly_data = pd.DataFrame({
            'Maand': months,
            'Uitgaven': [1234, 1567, 1890, 2234, 2567, 2890,
                        3234, 3567, 3890, 4234, 4567, 4890],
            'BTW Terug': [234, 267, 290, 334, 367, 390,
                         434, 467, 490, 534, 567, 590]
        })

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=monthly_data['Maand'],
            y=monthly_data['Uitgaven'],
            mode='lines+markers',
            name='Uitgaven',
            line=dict(color='#1f4788', width=2)
        ))
        fig_line.add_trace(go.Scatter(
            x=monthly_data['Maand'],
            y=monthly_data['BTW Terug'],
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

    st.markdown("---")

    # VAT breakdown section
    st.subheader("💶 BTW Overzicht")

    col1, col2, col3, col4 = st.columns(4)

    # Sample VAT data
    vat_6 = 234.56
    vat_9 = 345.67
    vat_21 = 1876.55
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

    # Sample recent receipts data
    recent_receipts_data = pd.DataFrame({
        'Datum': pd.date_range(start='2024-12-01', periods=10, freq='D'),
        'Leverancier': ['Albert Heijn', 'Bol.com', 'Coolblue', 'HEMA', 'MediaMarkt',
                       'Kruidvat', 'Jumbo', 'Action', 'Blokker', 'Praxis'],
        'Categorie': ['Representatiekosten - Type 1', 'Kantoorkosten', 'Kantoorkosten',
                     'Kantoorkosten', 'Beroepskosten', 'Kantoorkosten',
                     'Representatiekosten - Type 1', 'Kantoorkosten', 'Kantoorkosten',
                     'Beroepskosten'],
        'Bedrag': [45.67, 123.45, 234.56, 34.56, 567.89,
                  23.45, 67.89, 12.34, 45.67, 234.56],
        'Status': ['Verwerkt', 'Verwerkt', 'In behandeling', 'Verwerkt', 'Verwerkt',
                  'Verwerkt', 'In behandeling', 'Verwerkt', 'Verwerkt', 'Review nodig']
    })

    # Format the dataframe for display
    recent_receipts_display = recent_receipts_data.copy()
    recent_receipts_display['Datum'] = recent_receipts_display['Datum'].dt.strftime('%d-%m-%Y')
    recent_receipts_display['Bedrag'] = recent_receipts_display['Bedrag'].apply(lambda x: f"€ {x:,.2f}")

    # Apply status colors
    def highlight_status(row):
        if row['Status'] == 'Verwerkt':
            return ['background-color: #d4edda'] * len(row)
        elif row['Status'] == 'In behandeling':
            return ['background-color: #fff3cd'] * len(row)
        elif row['Status'] == 'Review nodig':
            return ['background-color: #f8d7da'] * len(row)
        return [''] * len(row)

    styled_df = recent_receipts_display.style.apply(highlight_status, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Quick actions
    st.markdown("---")
    st.subheader("⚡ Snelle Acties")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🆕 Nieuwe Bon Uploaden", use_container_width=True):
            st.switch_page("pages/upload_receipts.py")

    with col2:
        if st.button("📊 Kwartaal Rapport", use_container_width=True):
            st.info("Kwartaal rapport wordt gegenereerd...")

    with col3:
        if st.button("💾 Export naar Excel", use_container_width=True):
            st.info("Export wordt voorbereid...")

    with col4:
        if st.button("🔄 Ververs Dashboard", use_container_width=True):
            st.rerun()

    # Footer with last update time
    st.markdown("---")
    st.caption(f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")