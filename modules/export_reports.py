"""Export and reports page for generating various output formats."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import logging
from typing import Dict, List

from config import Config
from services.export_service import ExportService

logger = logging.getLogger(__name__)

def show():
    """Display the export and reports page."""

    st.title("📥 Export & Rapporten")
    st.markdown("Exporteer uw administratie in verschillende formaten")

    # Export type selection
    export_type = st.selectbox(
        "Selecteer export type",
        [
            "BTW Aangifte (Kwartaal)",
            "Jaaroverzicht",
            "Maandrapport",
            "Categorie Overzicht",
            "Leveranciers Overzicht",
            "Custom Export"
        ]
    )

    st.markdown("---")

    if export_type == "BTW Aangifte (Kwartaal)":
        show_vat_declaration_export()
    elif export_type == "Jaaroverzicht":
        show_annual_report()
    elif export_type == "Maandrapport":
        show_monthly_report()
    elif export_type == "Categorie Overzicht":
        show_category_report()
    elif export_type == "Leveranciers Overzicht":
        show_vendor_report()
    else:
        show_custom_export()

def show_vat_declaration_export():
    """Show VAT declaration export for quarterly tax filing."""

    st.subheader("💶 BTW Aangifte Export")
    st.info("""
    Genereer een export voor uw kwartaal BTW aangifte.
    Dit rapport bevat alle benodigde informatie voor de Belastingdienst.
    """)

    col1, col2 = st.columns(2)

    with col1:
        year = st.selectbox("Jaar", [2024, 2025, 2023])

    with col2:
        quarter = st.selectbox(
            "Kwartaal",
            ["Q1 (Jan-Mrt)", "Q2 (Apr-Jun)", "Q3 (Jul-Sep)", "Q4 (Okt-Dec)"]
        )

    # Calculate date range based on selection
    quarter_dates = {
        "Q1 (Jan-Mrt)": (f"{year}-01-01", f"{year}-03-31"),
        "Q2 (Apr-Jun)": (f"{year}-04-01", f"{year}-06-30"),
        "Q3 (Jul-Sep)": (f"{year}-07-01", f"{year}-09-30"),
        "Q4 (Okt-Dec)": (f"{year}-10-01", f"{year}-12-31")
    }

    start_date, end_date = quarter_dates[quarter]

    st.markdown("---")

    # Preview section
    st.markdown("### Voorvertoning BTW Overzicht")

    # Sample VAT data
    vat_data = {
        'Omschrijving': [
            '1a. Leveringen/diensten belast met hoog tarief',
            '1b. Leveringen/diensten belast met laag tarief',
            '1c. Leveringen/diensten belast met overige tarieven',
            '1d. Privégebruik',
            '1e. Leveringen/diensten belast met 0%',
            'Totaal',
            '',
            '5b. Voorbelasting'
        ],
        'Basis': [45000, 5000, 0, 0, 0, 50000, None, None],
        'BTW': [9450, 450, 0, 0, 0, 9900, None, 8234]
    }

    df_vat = pd.DataFrame(vat_data)

    # Display with formatting
    st.dataframe(
        df_vat.style.format({
            'Basis': lambda x: f"€ {x:,.2f}" if pd.notna(x) else "",
            'BTW': lambda x: f"€ {x:,.2f}" if pd.notna(x) else ""
        }),
        use_container_width=True,
        hide_index=True
    )

    # Summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Te betalen BTW", "€ 9,900.00")
    with col2:
        st.metric("Voorbelasting", "€ 8,234.00")
    with col3:
        st.metric("Saldo", "€ 1,666.00", "Te betalen")

    st.markdown("---")

    # Export options
    st.markdown("### Export Opties")

    col1, col2 = st.columns(2)

    with col1:
        include_details = st.checkbox("Gedetailleerde transacties bijvoegen", value=True)
        include_summary = st.checkbox("Samenvattingsblad toevoegen", value=True)

    with col2:
        format_option = st.selectbox(
            "Bestandsformaat",
            ["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"]
        )

    # Export button
    if st.button("📥 Genereer BTW Aangifte Export", use_container_width=True, type="primary"):
        with st.spinner("Export wordt gegenereerd..."):
            # Generate export (placeholder)
            st.success(f"✅ BTW aangifte voor {quarter} {year} succesvol gegenereerd!")

            # Provide download button
            export_data = generate_sample_excel()
            st.download_button(
                label="⬇️ Download BTW Aangifte",
                data=export_data,
                file_name=f"BTW_Aangifte_{year}_{quarter.split()[0]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def show_annual_report():
    """Show annual report export."""

    st.subheader("📊 Jaaroverzicht")

    year = st.selectbox("Selecteer jaar", [2024, 2023, 2022])

    st.markdown("---")

    # Annual summary
    st.markdown("### Jaarsamenvatting " + str(year))

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totale Uitgaven", "€ 54,321.00")
    with col2:
        st.metric("BTW Terugvordering", "€ 9,876.00")
    with col3:
        st.metric("Aantal Bonnen", "487")
    with col4:
        st.metric("Gem. per Bon", "€ 111.53")

    # Category breakdown
    st.markdown("### Uitgaven per Categorie")

    category_data = pd.DataFrame({
        'Categorie': Config.EXPENSE_CATEGORIES,
        'Bedrag excl. BTW': [12345, 8765, 5432, 3210, 2345, 4567, 7890],
        'BTW': [2592, 1840, 1140, 0, 0, 958, 1657],
        'Totaal incl. BTW': [14937, 10605, 6572, 3210, 2345, 5525, 9547],
        'Percentage': [20.1, 14.3, 8.9, 4.3, 3.2, 7.4, 12.9]
    })

    st.dataframe(
        category_data.style.format({
            'Bedrag excl. BTW': '€ {:,.2f}',
            'BTW': '€ {:,.2f}',
            'Totaal incl. BTW': '€ {:,.2f}',
            'Percentage': '{:.1f}%'
        }),
        use_container_width=True,
        hide_index=True
    )

    # Export button
    if st.button("📥 Genereer Jaaroverzicht", use_container_width=True, type="primary"):
        with st.spinner("Jaaroverzicht wordt gegenereerd..."):
            st.success(f"✅ Jaaroverzicht {year} succesvol gegenereerd!")

            export_data = generate_sample_excel()
            st.download_button(
                label="⬇️ Download Jaaroverzicht",
                data=export_data,
                file_name=f"Jaaroverzicht_{year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def show_monthly_report():
    """Show monthly report export."""

    st.subheader("📅 Maandrapport")

    col1, col2 = st.columns(2)

    with col1:
        month = st.selectbox(
            "Maand",
            ["Januari", "Februari", "Maart", "April", "Mei", "Juni",
             "Juli", "Augustus", "September", "Oktober", "November", "December"]
        )

    with col2:
        year = st.selectbox("Jaar", [2024, 2023])

    # Generate and display monthly data
    generate_monthly_preview(month, year)

def show_category_report():
    """Show category-based report."""

    st.subheader("📂 Categorie Overzicht")

    selected_categories = st.multiselect(
        "Selecteer categorieën",
        Config.EXPENSE_CATEGORIES,
        default=Config.EXPENSE_CATEGORIES[:3]
    )

    if selected_categories:
        # Date range
        col1, col2 = st.columns(2)

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

        # Generate preview
        st.markdown("### Overzicht Geselecteerde Categorieën")

        for category in selected_categories:
            with st.expander(f"📁 {category}", expanded=True):
                # Sample data for each category
                transactions = pd.DataFrame({
                    'Datum': pd.date_range(start=start_date, periods=5, freq='W'),
                    'Leverancier': ['Vendor A', 'Vendor B', 'Vendor C', 'Vendor D', 'Vendor E'],
                    'Bedrag excl.': [123.45, 234.56, 345.67, 456.78, 567.89],
                    'BTW': [25.92, 49.26, 72.59, 95.92, 119.25],
                    'Totaal': [149.37, 283.82, 418.26, 552.70, 687.14]
                })

                st.dataframe(
                    transactions.style.format({
                        'Datum': lambda x: x.strftime('%d-%m-%Y'),
                        'Bedrag excl.': '€ {:.2f}',
                        'BTW': '€ {:.2f}',
                        'Totaal': '€ {:.2f}'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Totaal", f"€ {transactions['Totaal'].sum():.2f}")
                with col2:
                    st.metric("BTW", f"€ {transactions['BTW'].sum():.2f}")
                with col3:
                    st.metric("Aantal", len(transactions))

def show_vendor_report():
    """Show vendor-based report."""

    st.subheader("🏪 Leveranciers Overzicht")

    # Vendor selection
    vendor_search = st.text_input("Zoek leverancier", placeholder="Typ om te zoeken...")

    # Sample vendor list
    vendors = ['Albert Heijn', 'Bol.com', 'Coolblue', 'MediaMarkt', 'HEMA', 'Kruidvat']

    if vendor_search:
        vendors = [v for v in vendors if vendor_search.lower() in v.lower()]

    selected_vendors = st.multiselect("Selecteer leveranciers", vendors)

    if selected_vendors:
        st.markdown("### Leveranciers Analyse")

        vendor_data = pd.DataFrame({
            'Leverancier': selected_vendors,
            'Aantal Transacties': [23, 15, 8, 12, 19],
            'Totaal Bedrag': [2345.67, 1234.56, 3456.78, 4567.89, 1876.54],
            'Gem. Bedrag': [101.99, 82.30, 432.10, 380.66, 98.77],
            'Laatste Transactie': pd.date_range(end='2024-12-01', periods=5)
        })

        st.dataframe(
            vendor_data.style.format({
                'Totaal Bedrag': '€ {:.2f}',
                'Gem. Bedrag': '€ {:.2f}',
                'Laatste Transactie': lambda x: x.strftime('%d-%m-%Y')
            }),
            use_container_width=True,
            hide_index=True
        )

def show_custom_export():
    """Show custom export options."""

    st.subheader("🔧 Aangepaste Export")

    st.info("""
    Maak een aangepaste export met alleen de gegevens die u nodig heeft.
    """)

    # Column selection
    st.markdown("### Selecteer Kolommen")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Basis Informatie**")
        col_receipt_id = st.checkbox("Bon ID", value=True)
        col_date = st.checkbox("Datum", value=True)
        col_vendor = st.checkbox("Leverancier", value=True)
        col_category = st.checkbox("Categorie", value=True)

    with col2:
        st.markdown("**Financiële Gegevens**")
        col_amount_excl = st.checkbox("Bedrag excl. BTW", value=True)
        col_vat = st.checkbox("BTW bedragen", value=True)
        col_total = st.checkbox("Totaal incl. BTW", value=True)
        col_deductions = st.checkbox("Aftrekposten", value=False)

    # Date range
    st.markdown("### Periode")

    col1, col2 = st.columns(2)

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

    # Format selection
    st.markdown("### Export Formaat")

    format_option = st.radio(
        "Selecteer formaat",
        ["Excel (.xlsx)", "CSV (.csv)", "JSON (.json)", "PDF (.pdf)"],
        horizontal=True
    )

    # Additional options
    with st.expander("Geavanceerde opties"):
        include_deleted = st.checkbox("Inclusief verwijderde bonnen", value=False)
        include_failed = st.checkbox("Inclusief mislukte verwerkingen", value=False)
        group_by = st.selectbox(
            "Groeperen op",
            ["Geen", "Categorie", "Leverancier", "Maand"]
        )

    # Export button
    if st.button("🚀 Start Custom Export", use_container_width=True, type="primary"):
        with st.spinner("Custom export wordt voorbereid..."):
            st.success("✅ Export succesvol gegenereerd!")

            # Generate sample export
            export_data = generate_sample_excel()
            st.download_button(
                label="⬇️ Download Export",
                data=export_data,
                file_name=f"Custom_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def generate_monthly_preview(month: str, year: int):
    """Generate monthly report preview."""

    st.markdown(f"### Overzicht {month} {year}")

    # Sample monthly data
    days_in_month = 30
    daily_data = pd.DataFrame({
        'Datum': pd.date_range(start=f'{year}-{get_month_number(month)}-01', periods=days_in_month, freq='D'),
        'Aantal Bonnen': [2, 1, 3, 0, 2, 1, 0, 2, 3, 1] * 3,
        'Dagelijks Totaal': [123.45, 0, 234.56, 0, 345.67, 123.45, 0, 234.56, 345.67, 456.78] * 3
    })

    # Weekly aggregation
    weekly_summary = daily_data.groupby(pd.Grouper(key='Datum', freq='W')).agg({
        'Aantal Bonnen': 'sum',
        'Dagelijks Totaal': 'sum'
    }).reset_index()

    st.dataframe(
        weekly_summary.style.format({
            'Datum': lambda x: f"Week {x.isocalendar()[1]}",
            'Dagelijks Totaal': '€ {:.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Totaal Bonnen", daily_data['Aantal Bonnen'].sum())
    with col2:
        st.metric("Totaal Bedrag", f"€ {daily_data['Dagelijks Totaal'].sum():.2f}")
    with col3:
        avg_daily = daily_data['Dagelijks Totaal'].sum() / days_in_month
        st.metric("Gem. per Dag", f"€ {avg_daily:.2f}")

def get_month_number(month_name: str) -> str:
    """Convert month name to number."""
    months = {
        'Januari': '01', 'Februari': '02', 'Maart': '03', 'April': '04',
        'Mei': '05', 'Juni': '06', 'Juli': '07', 'Augustus': '08',
        'September': '09', 'Oktober': '10', 'November': '11', 'December': '12'
    }
    return months.get(month_name, '01')

def generate_sample_excel() -> bytes:
    """Generate a sample Excel file for download."""
    # Create sample data
    df = pd.DataFrame({
        'Nr': range(1, 11),
        'Datum': pd.date_range(start='2024-01-01', periods=10, freq='W'),
        'Leverancier': ['Vendor ' + str(i) for i in range(1, 11)],
        'Categorie': ['Kantoorkosten'] * 10,
        'Bedrag excl. BTW': [100 + i*10 for i in range(10)],
        'BTW 21%': [21 + i*2.1 for i in range(10)],
        'Totaal incl. BTW': [121 + i*12.1 for i in range(10)]
    })

    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Overzicht', index=False)

        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Overzicht']

        # Add formatting
        money_format = workbook.add_format({'num_format': '€ #,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})

        # Apply formatting to columns
        worksheet.set_column('B:B', 12, date_format)
        worksheet.set_column('E:G', 15, money_format)

    output.seek(0)
    return output.read()