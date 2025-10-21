"""Export and reports page for generating various output formats - using REAL local data."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import logging
from typing import Dict, List

from config import Config
from services.export_service import ExportService
from utils.local_storage import filter_receipts, get_all_receipts, get_statistics
from utils.database_utils_local import get_receipts_for_export
from utils.invoice_storage import filter_invoices, get_invoice_statistics

logger = logging.getLogger(__name__)

def show():
    """Display the export and reports page."""

    st.title("📥 Export & Rapporten")
    st.markdown("Exporteer uw administratie in verschillende formaten")

    # Check if there are any receipts
    all_receipts = get_all_receipts()
    if not all_receipts:
        st.warning("⚠️ Geen bonnen gevonden. Upload eerst bonnen om rapporten te genereren.")
        if st.button("📤 Ga naar Upload Bonnen", use_container_width=True):
            st.session_state['selected_page'] = "Upload Bonnen"
            st.rerun()
        return

    # Export type selection
    export_type = st.selectbox(
        "Selecteer export type",
        [
            "BTW Aangifte (Kwartaal)",
            "Winst & Verlies Rapport",
            "Omzet Overzicht",
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
    elif export_type == "Winst & Verlies Rapport":
        show_profit_loss_report()
    elif export_type == "Omzet Overzicht":
        show_revenue_report()
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
        year = st.selectbox("Jaar", [2025, 2024, 2023])

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

    # Get actual receipts for this quarter
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    receipts = get_receipts_for_export(
        user_id=1,
        date_from=start_dt,
        date_to=end_dt
    )

    # Get invoices for this quarter
    invoices = filter_invoices(start_date=start_dt, end_date=end_dt)

    st.markdown("---")

    if not receipts and not invoices:
        st.warning(f"⚠️ Geen gegevens gevonden voor {quarter} {year}")
        return

    # Calculate VAT totals from expenses (receipts)
    expense_vat_6 = sum(r.get('vat_6', 0) for r in receipts)
    expense_vat_9 = sum(r.get('vat_9', 0) for r in receipts)
    expense_vat_21 = sum(r.get('vat_21', 0) for r in receipts)
    total_vat_refund = sum(r.get('vat_refund', 0) for r in receipts)

    # Calculate VAT totals from revenue (invoices)
    revenue_basis_21 = 0
    revenue_basis_9 = 0
    revenue_basis_0 = 0
    revenue_vat_21 = 0
    revenue_vat_9 = 0
    revenue_vat_0 = 0

    for invoice in invoices:
        # Get line items to calculate VAT breakdown
        line_items = invoice.get('line_items', [])
        for item in line_items:
            vat_rate = item.get('vat_rate', 21)
            subtotal = item.get('subtotal', 0)
            vat_amount = item.get('vat_amount', 0)

            if vat_rate == 21:
                revenue_basis_21 += subtotal
                revenue_vat_21 += vat_amount
            elif vat_rate == 9:
                revenue_basis_9 += subtotal
                revenue_vat_9 += vat_amount
            else:  # 0%
                revenue_basis_0 += subtotal
                revenue_vat_0 += vat_amount

    # Calculate total VAT payable
    total_vat_payable = revenue_vat_21 + revenue_vat_9 + revenue_vat_0

    # Preview section
    st.markdown("### Voorvertoning BTW Overzicht")

    # Real VAT data following Dutch BTW aangifte format
    vat_data = {
        'Omschrijving': [
            '1a. Leveringen/diensten belast met hoog tarief (21%)',
            '1b. Leveringen/diensten belast met laag tarief (9%)',
            '1c. Leveringen/diensten belast met overige tarieven',
            '1d. Privégebruik',
            '1e. Leveringen/diensten belast met 0%',
            'Subtotaal verschuldigde BTW',
            '',
            '5b. Voorbelasting (aftrekbare BTW)',
            '',
            'Te betalen/terug te vorderen'
        ],
        'Basis': [
            revenue_basis_21,
            revenue_basis_9,
            0,
            0,
            revenue_basis_0,
            None,
            None,
            None,
            None,
            None
        ],
        'BTW': [
            revenue_vat_21,
            revenue_vat_9,
            0,
            0,
            0,
            total_vat_payable,
            None,
            total_vat_refund,
            None,
            total_vat_payable - total_vat_refund
        ]
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
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Aantal Facturen", len(invoices))
        st.caption(f"{len(receipts)} bonnen")

    with col2:
        st.metric("BTW Verschuldigd", f"€ {total_vat_payable:,.2f}")
        st.caption(f"Omzet BTW")

    with col3:
        st.metric("BTW Terugvraag", f"€ {total_vat_refund:,.2f}")
        st.caption(f"Kosten BTW")

    with col4:
        net_btw = total_vat_payable - total_vat_refund
        st.metric("Netto BTW", f"€ {net_btw:,.2f}")
        st.caption("Te betalen" if net_btw > 0 else "Terug te vorderen")

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
            ["Excel (.xlsx)", "CSV (.csv)", "JSON (.json)"]
        )

    # Export button
    if st.button("📥 Genereer BTW Aangifte Export", use_container_width=True, type="primary"):
        with st.spinner("Export wordt gegenereerd..."):
            try:
                if format_option == "Excel (.xlsx)":
                    export_data = ExportService.export_to_excel(
                        receipts,
                        include_summary=include_summary,
                        include_vat_declaration=True
                    )
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    file_ext = "xlsx"
                elif format_option == "CSV (.csv)":
                    export_data = ExportService.export_to_csv(receipts)
                    mime_type = "text/csv"
                    file_ext = "csv"
                else:  # JSON
                    export_data = ExportService.export_to_json(receipts)
                    mime_type = "application/json"
                    file_ext = "json"

                st.success(f"✅ BTW aangifte voor {quarter} {year} succesvol gegenereerd!")

                # Provide download button
                st.download_button(
                    label="⬇️ Download BTW Aangifte",
                    data=export_data,
                    file_name=f"BTW_Aangifte_{year}_{quarter.split()[0]}.{file_ext}",
                    mime=mime_type
                )
            except Exception as e:
                st.error(f"Fout bij genereren export: {str(e)}")
                logger.error(f"Export error: {e}")

def show_annual_report():
    """Show annual report export."""

    st.subheader("📊 Jaaroverzicht")

    year = st.selectbox("Selecteer jaar", [2025, 2024, 2023, 2022])

    # Get receipts for the year
    start_dt = datetime(year, 1, 1)
    end_dt = datetime(year, 12, 31)

    receipts = get_receipts_for_export(
        user_id=1,
        date_from=start_dt,
        date_to=end_dt
    )

    st.markdown("---")

    if not receipts:
        st.warning(f"⚠️ Geen bonnen gevonden voor {year}")
        return

    # Calculate statistics
    total_amount = sum(r.get('total_incl_vat', 0) for r in receipts)
    total_vat_refund = sum(r.get('vat_refund', 0) for r in receipts)
    avg_per_receipt = total_amount / len(receipts) if len(receipts) > 0 else 0

    # Annual summary
    st.markdown("### Jaarsamenvatting " + str(year))

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totale Uitgaven", f"€ {total_amount:,.2f}")
    with col2:
        st.metric("BTW Terugvordering", f"€ {total_vat_refund:,.2f}")
    with col3:
        st.metric("Aantal Bonnen", len(receipts))
    with col4:
        st.metric("Gem. per Bon", f"€ {avg_per_receipt:,.2f}")

    # Category breakdown
    st.markdown("### Uitgaven per Categorie")

    # Group by category
    category_totals = {}
    category_vat = {}
    category_count = {}

    for receipt in receipts:
        category = receipt.get('category', 'Onbekend')
        amount_excl = receipt.get('amount_excl_vat', 0)
        amount_incl = receipt.get('total_incl_vat', 0)
        vat = amount_incl - amount_excl

        if category not in category_totals:
            category_totals[category] = 0
            category_vat[category] = 0
            category_count[category] = 0

        category_totals[category] += amount_incl
        category_vat[category] += vat
        category_count[category] += 1

    # Create DataFrame
    category_data = []
    for category in sorted(category_totals.keys()):
        percentage = (category_totals[category] / total_amount * 100) if total_amount > 0 else 0
        category_data.append({
            'Categorie': category,
            'Aantal': category_count[category],
            'Bedrag excl. BTW': category_totals[category] - category_vat[category],
            'BTW': category_vat[category],
            'Totaal incl. BTW': category_totals[category],
            'Percentage': percentage
        })

    df_category = pd.DataFrame(category_data)

    st.dataframe(
        df_category.style.format({
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
            try:
                export_data = ExportService.export_to_excel(receipts, include_summary=True)
                st.success(f"✅ Jaaroverzicht {year} succesvol gegenereerd!")

                st.download_button(
                    label="⬇️ Download Jaaroverzicht",
                    data=export_data,
                    file_name=f"Jaaroverzicht_{year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Fout bij genereren export: {str(e)}")
                logger.error(f"Export error: {e}")

def show_monthly_report():
    """Show monthly report export."""

    st.subheader("📅 Maandrapport")

    col1, col2 = st.columns(2)

    with col1:
        month_names = ["Januari", "Februari", "Maart", "April", "Mei", "Juni",
                      "Juli", "Augustus", "September", "Oktober", "November", "December"]
        month = st.selectbox("Maand", month_names)

    with col2:
        year = st.selectbox("Jaar", [2025, 2024, 2023])

    # Calculate date range
    month_num = month_names.index(month) + 1
    start_dt = datetime(year, month_num, 1)

    # Get last day of month
    if month_num == 12:
        end_dt = datetime(year, 12, 31)
    else:
        end_dt = datetime(year, month_num + 1, 1) - timedelta(days=1)

    # Get receipts
    receipts = get_receipts_for_export(
        user_id=1,
        date_from=start_dt,
        date_to=end_dt
    )

    st.markdown("---")

    if not receipts:
        st.warning(f"⚠️ Geen bonnen gevonden voor {month} {year}")
        return

    # Generate and display monthly data
    st.markdown(f"### Overzicht {month} {year}")

    # Calculate metrics
    total_amount = sum(r.get('total_incl_vat', 0) for r in receipts)
    total_vat = sum(r.get('vat_refund', 0) for r in receipts)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Totaal Bonnen", len(receipts))
    with col2:
        st.metric("Totaal Bedrag", f"€ {total_amount:,.2f}")
    with col3:
        st.metric("BTW Terug", f"€ {total_vat:,.2f}")

    # Show receipt list
    st.markdown("### Bonnen dit Maand")

    receipt_list = []
    for r in receipts:
        receipt_list.append({
            'Datum': r.get('transaction_date'),
            'Leverancier': r.get('vendor_name', 'Onbekend'),
            'Categorie': r.get('category', 'Onbekend'),
            'Bedrag': r.get('total_incl_vat', 0)
        })

    df_receipts = pd.DataFrame(receipt_list)
    if not df_receipts.empty:
        df_receipts['Datum'] = pd.to_datetime(df_receipts['Datum'])
        df_receipts = df_receipts.sort_values('Datum')

        st.dataframe(
            df_receipts.style.format({
                'Datum': lambda x: x.strftime('%d-%m-%Y'),
                'Bedrag': '€ {:,.2f}'
            }),
            use_container_width=True,
            hide_index=True
        )

        # Export button
        if st.button("📥 Genereer Maandrapport", use_container_width=True, type="primary"):
            with st.spinner("Maandrapport wordt gegenereerd..."):
                try:
                    export_data = ExportService.export_to_excel(receipts)
                    st.success(f"✅ Maandrapport {month} {year} succesvol gegenereerd!")

                    st.download_button(
                        label="⬇️ Download Maandrapport",
                        data=export_data,
                        file_name=f"Maandrapport_{month}_{year}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Fout bij genereren export: {str(e)}")
                    logger.error(f"Export error: {e}")

def show_category_report():
    """Show category-based report."""

    st.subheader("📂 Categorie Overzicht")

    selected_categories = st.multiselect(
        "Selecteer categorieën",
        Config.EXPENSE_CATEGORIES,
        default=[]
    )

    if not selected_categories:
        st.info("ℹ️ Selecteer één of meer categorieën om het overzicht te zien")
        return

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

    # Get receipts
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    st.markdown("---")

    # Generate preview
    st.markdown("### Overzicht Geselecteerde Categorieën")

    for category in selected_categories:
        # Get receipts for this category
        receipts = get_receipts_for_export(
            user_id=1,
            date_from=start_dt,
            date_to=end_dt,
            categories=[category]
        )

        with st.expander(f"📁 {category}", expanded=True):
            if not receipts:
                st.info(f"Geen bonnen gevonden voor categorie: {category}")
                continue

            # Create transactions DataFrame
            transactions = []
            for r in receipts:
                transactions.append({
                    'Datum': r.get('transaction_date'),
                    'Leverancier': r.get('vendor_name', 'Onbekend'),
                    'Bedrag excl.': r.get('amount_excl_vat', 0),
                    'BTW': r.get('total_incl_vat', 0) - r.get('amount_excl_vat', 0),
                    'Totaal': r.get('total_incl_vat', 0)
                })

            df_trans = pd.DataFrame(transactions)
            df_trans['Datum'] = pd.to_datetime(df_trans['Datum'])
            df_trans = df_trans.sort_values('Datum', ascending=False)

            st.dataframe(
                df_trans.style.format({
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
                st.metric("Totaal", f"€ {df_trans['Totaal'].sum():.2f}")
            with col2:
                st.metric("BTW", f"€ {df_trans['BTW'].sum():.2f}")
            with col3:
                st.metric("Aantal", len(df_trans))

    # Export all categories
    if st.button("📥 Exporteer Alle Categorieën", use_container_width=True, type="primary"):
        with st.spinner("Export wordt gegenereerd..."):
            try:
                # Get all receipts for selected categories
                all_receipts = get_receipts_for_export(
                    user_id=1,
                    date_from=start_dt,
                    date_to=end_dt,
                    categories=selected_categories
                )

                export_data = ExportService.export_to_excel(all_receipts)
                st.success(f"✅ Export voor {len(selected_categories)} categorieën succesvol gegenereerd!")

                st.download_button(
                    label="⬇️ Download Categorie Overzicht",
                    data=export_data,
                    file_name=f"Categorie_Overzicht_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Fout bij genereren export: {str(e)}")
                logger.error(f"Export error: {e}")

def show_vendor_report():
    """Show vendor-based report."""

    st.subheader("🏪 Leveranciers Overzicht")

    # Get all receipts to extract unique vendors
    all_receipts = get_all_receipts()

    # Extract unique vendors
    vendors = set()
    for receipt in all_receipts:
        extracted = receipt.get('extracted_data', {})
        vendor = extracted.get('vendor_name')
        if vendor:
            vendors.add(vendor)

    vendors = sorted(list(vendors))

    if not vendors:
        st.warning("⚠️ Geen leveranciers gevonden in de bonnen")
        return

    # Vendor selection
    vendor_search = st.text_input("Zoek leverancier", placeholder="Typ om te zoeken...")

    if vendor_search:
        vendors = [v for v in vendors if vendor_search.lower() in v.lower()]

    selected_vendors = st.multiselect("Selecteer leveranciers", vendors)

    if not selected_vendors:
        st.info("ℹ️ Selecteer één of meer leveranciers om het overzicht te zien")
        return

    st.markdown("### Leveranciers Analyse")

    # Analyze each vendor
    vendor_data = []
    for vendor in selected_vendors:
        vendor_receipts = filter_receipts(vendor=vendor)

        if vendor_receipts:
            total_amount = sum(
                r.get('extracted_data', {}).get('total_incl_vat', 0) or
                r.get('extracted_data', {}).get('total_amount', 0)
                for r in vendor_receipts
            )

            avg_amount = total_amount / len(vendor_receipts) if len(vendor_receipts) > 0 else 0

            # Get latest transaction date
            latest_date = None
            for r in vendor_receipts:
                extracted = r.get('extracted_data', {})
                trans_date = extracted.get('transaction_date') or extracted.get('date')
                if trans_date:
                    if isinstance(trans_date, str):
                        try:
                            trans_date = datetime.fromisoformat(trans_date)
                        except:
                            continue
                    if latest_date is None or trans_date > latest_date:
                        latest_date = trans_date

            vendor_data.append({
                'Leverancier': vendor,
                'Aantal Transacties': len(vendor_receipts),
                'Totaal Bedrag': total_amount,
                'Gem. Bedrag': avg_amount,
                'Laatste Transactie': latest_date if latest_date else datetime.now()
            })

    if vendor_data:
        df_vendor = pd.DataFrame(vendor_data)

        st.dataframe(
            df_vendor.style.format({
                'Totaal Bedrag': '€ {:,.2f}',
                'Gem. Bedrag': '€ {:,.2f}',
                'Laatste Transactie': lambda x: x.strftime('%d-%m-%Y')
            }),
            use_container_width=True,
            hide_index=True
        )

        # Export button
        if st.button("📥 Exporteer Leveranciers", use_container_width=True, type="primary"):
            with st.spinner("Export wordt gegenereerd..."):
                try:
                    # Get all receipts for selected vendors
                    all_vendor_receipts = []
                    for vendor in selected_vendors:
                        vendor_receipts = filter_receipts(vendor=vendor)
                        for r in vendor_receipts:
                            extracted = r.get('extracted_data', {})
                            if extracted:
                                all_vendor_receipts.append({
                                    'transaction_date': extracted.get('transaction_date') or extracted.get('date'),
                                    'vendor_name': vendor,
                                    'category': extracted.get('expense_category') or extracted.get('category'),
                                    'amount_excl_vat': extracted.get('amount_excl_vat', 0),
                                    'vat_6': extracted.get('vat_6_amount', 0),
                                    'vat_9': extracted.get('vat_9_amount', 0),
                                    'vat_21': extracted.get('vat_21_amount', 0),
                                    'total_incl_vat': extracted.get('total_incl_vat') or extracted.get('total_amount', 0),
                                    'vat_deductible_percentage': extracted.get('vat_deductible_percentage', 100),
                                    'ib_deductible_percentage': extracted.get('ib_deductible_percentage', 100),
                                    'vat_refund': extracted.get('vat_refund_amount', 0),
                                    'profit_deduction': extracted.get('profit_deduction', 0),
                                    'explanation': extracted.get('explanation') or extracted.get('notes', '')
                                })

                    export_data = ExportService.export_to_excel(all_vendor_receipts)
                    st.success(f"✅ Export voor {len(selected_vendors)} leveranciers succesvol gegenereerd!")

                    st.download_button(
                        label="⬇️ Download Leveranciers Overzicht",
                        data=export_data,
                        file_name=f"Leveranciers_Overzicht_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Fout bij genereren export: {str(e)}")
                    logger.error(f"Export error: {e}")

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
        ["Excel (.xlsx)", "CSV (.csv)", "JSON (.json)"],
        horizontal=True
    )

    # Additional options
    with st.expander("Geavanceerde opties"):
        status_filter = st.multiselect(
            "Status",
            ["completed", "pending", "processing", "failed"],
            default=["completed"]
        )

        selected_categories = st.multiselect(
            "Categorieën",
            Config.EXPENSE_CATEGORIES,
            default=[]
        )

    # Export button
    if st.button("🚀 Start Custom Export", use_container_width=True, type="primary"):
        with st.spinner("Custom export wordt voorbereid..."):
            try:
                # Get receipts based on filters
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())

                receipts = get_receipts_for_export(
                    user_id=1,
                    date_from=start_dt,
                    date_to=end_dt,
                    categories=selected_categories if selected_categories else None
                )

                # Filter by status
                if status_filter:
                    receipts = [r for r in receipts if any(status in str(r) for status in status_filter)]

                if not receipts:
                    st.warning("⚠️ Geen bonnen gevonden met de geselecteerde filters")
                    return

                # Generate export based on format
                if format_option == "Excel (.xlsx)":
                    export_data = ExportService.export_to_excel(receipts)
                    mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    file_ext = "xlsx"
                elif format_option == "CSV (.csv)":
                    export_data = ExportService.export_to_csv(receipts)
                    mime_type = "text/csv"
                    file_ext = "csv"
                else:  # JSON
                    export_data = ExportService.export_to_json(receipts)
                    mime_type = "application/json"
                    file_ext = "json"

                st.success(f"✅ Export succesvol gegenereerd! ({len(receipts)} bonnen)")

                # Generate sample export
                st.download_button(
                    label="⬇️ Download Export",
                    data=export_data,
                    file_name=f"Custom_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}",
                    mime=mime_type
                )
            except Exception as e:
                st.error(f"Fout bij genereren export: {str(e)}")
                logger.error(f"Export error: {e}")

def show_profit_loss_report():
    """Show profit and loss report combining income and expenses."""

    st.subheader("📊 Winst & Verlies Rapport")
    st.info("Genereer een compleet winst & verlies overzicht met omzet en kosten.")

    # Date range selection
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Van datum",
            value=datetime.now().replace(month=1, day=1),
            format="DD/MM/YYYY"
        )

    with col2:
        end_date = st.date_input(
            "Tot datum",
            value=datetime.now(),
            format="DD/MM/YYYY"
        )

    # Convert to datetime
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Get data
    receipts = filter_receipts(start_date=start_dt, end_date=end_dt, status='completed')
    invoices = filter_invoices(start_date=start_dt, end_date=end_dt)

    if not receipts and not invoices:
        st.warning("⚠️ Geen gegevens gevonden voor de geselecteerde periode.")
        return

    st.markdown("---")

    # Calculate totals
    total_expenses = 0
    total_vat_refund = 0
    expenses_excl_vat = 0

    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})
        if extracted:
            amount = float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0))
            total_expenses += amount

            vat_deductible = float(extracted.get('vat_deductible_amount') or extracted.get('vat_refund_amount', 0))
            total_vat_refund += vat_deductible

            amount_excl = float(extracted.get('amount_excl_vat', 0))
            if amount_excl == 0:
                vat_breakdown = extracted.get('vat_breakdown', {})
                total_vat = sum(float(v) for v in vat_breakdown.values())
                amount_excl = amount - total_vat
            expenses_excl_vat += amount_excl

    total_revenue = 0
    total_vat_payable = 0
    revenue_excl_vat = 0

    for invoice in invoices:
        total_incl_vat = invoice.get('total_incl_vat', 0)
        vat_amount = invoice.get('vat_amount', 0)
        subtotal = invoice.get('subtotal_excl_vat', 0)

        total_revenue += total_incl_vat
        total_vat_payable += vat_amount
        revenue_excl_vat += subtotal

    gross_profit = total_revenue - total_expenses
    net_vat_position = total_vat_payable - total_vat_refund
    profit_excl_vat = revenue_excl_vat - expenses_excl_vat

    # Preview
    st.markdown("### Voorvertoning")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Omzet", f"€ {total_revenue:,.2f}")

    with col2:
        st.metric("Kosten", f"€ {total_expenses:,.2f}")

    with col3:
        profit_color = "normal" if gross_profit >= 0 else "inverse"
        st.metric("Resultaat", f"€ {gross_profit:,.2f}", delta_color=profit_color)

    with col4:
        margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        st.metric("Marge", f"{margin:.1f}%")

    # Create P&L DataFrame
    pl_data = [
        {"Categorie": "Omzet", "Subcategorie": "Totale omzet (incl. BTW)", "Bedrag": total_revenue},
        {"Categorie": "Omzet", "Subcategorie": "BTW op omzet", "Bedrag": -total_vat_payable},
        {"Categorie": "Omzet", "Subcategorie": "Omzet (excl. BTW)", "Bedrag": revenue_excl_vat},
        {"Categorie": "", "Subcategorie": "", "Bedrag": None},
        {"Categorie": "Kosten", "Subcategorie": "Totale kosten (incl. BTW)", "Bedrag": -total_expenses},
        {"Categorie": "Kosten", "Subcategorie": "BTW terugvordering", "Bedrag": total_vat_refund},
        {"Categorie": "Kosten", "Subcategorie": "Kosten (excl. BTW)", "Bedrag": -expenses_excl_vat},
        {"Categorie": "", "Subcategorie": "", "Bedrag": None},
        {"Categorie": "BTW", "Subcategorie": "BTW te betalen", "Bedrag": -total_vat_payable},
        {"Categorie": "BTW", "Subcategorie": "BTW terugvordering", "Bedrag": total_vat_refund},
        {"Categorie": "BTW", "Subcategorie": "Netto BTW positie", "Bedrag": -net_vat_position},
        {"Categorie": "", "Subcategorie": "", "Bedrag": None},
        {"Categorie": "Resultaat", "Subcategorie": "Bruto resultaat (incl. BTW)", "Bedrag": gross_profit},
        {"Categorie": "Resultaat", "Subcategorie": "Resultaat (excl. BTW)", "Bedrag": profit_excl_vat},
    ]

    df = pd.DataFrame(pl_data)

    st.dataframe(
        df.style.format({
            'Bedrag': lambda x: f"€ {x:,.2f}" if pd.notna(x) else ""
        }),
        use_container_width=True,
        hide_index=True
    )

    # Export buttons
    st.markdown("---")
    st.markdown("### Download Opties")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Winst & Verlies', index=False)

        st.download_button(
            label="📥 Download Excel",
            data=output.getvalue(),
            file_name=f"Winst_Verlies_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        # CSV export
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"Winst_Verlies_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col3:
        # PDF export placeholder
        st.button("📄 Download PDF", disabled=True, use_container_width=True, help="PDF export komt binnenkort")

def show_revenue_report():
    """Show revenue report from invoices."""

    st.subheader("💰 Omzet Overzicht")
    st.info("Genereer een overzicht van alle facturen en omzet.")

    # Date range selection
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Van datum",
            value=datetime.now().replace(month=1, day=1),
            format="DD/MM/YYYY",
            key="revenue_start_date"
        )

    with col2:
        end_date = st.date_input(
            "Tot datum",
            value=datetime.now(),
            format="DD/MM/YYYY",
            key="revenue_end_date"
        )

    # Convert to datetime
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Get invoices
    invoices = filter_invoices(start_date=start_dt, end_date=end_dt)

    if not invoices:
        st.warning("⚠️ Geen facturen gevonden voor de geselecteerde periode.")
        return

    st.markdown("---")

    # Calculate totals
    total_revenue = sum(inv.get('total_incl_vat', 0) for inv in invoices)
    total_vat = sum(inv.get('vat_amount', 0) for inv in invoices)
    total_paid = sum(inv.get('total_incl_vat', 0) for inv in invoices if inv.get('payment_status') == 'paid')
    total_unpaid = sum(inv.get('total_incl_vat', 0) for inv in invoices if inv.get('payment_status') != 'paid')

    # Preview
    st.markdown("### Voorvertoning")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Aantal Facturen", len(invoices))

    with col2:
        st.metric("Totale Omzet", f"€ {total_revenue:,.2f}")

    with col3:
        st.metric("Betaald", f"€ {total_paid:,.2f}")

    with col4:
        st.metric("Openstaand", f"€ {total_unpaid:,.2f}")

    # Create DataFrame
    invoice_data = []
    for inv in invoices:
        invoice_data.append({
            'Factuurnummer': inv.get('invoice_number', ''),
            'Datum': inv.get('invoice_date', ''),
            'Klant': inv.get('client_name', ''),
            'Bedrag excl. BTW': inv.get('subtotal_excl_vat', 0),
            'BTW': inv.get('vat_amount', 0),
            'Totaal incl. BTW': inv.get('total_incl_vat', 0),
            'Status': inv.get('payment_status', 'unpaid'),
            'Betalingstermijn': inv.get('payment_terms', 30)
        })

    df = pd.DataFrame(invoice_data)

    st.dataframe(
        df.style.format({
            'Bedrag excl. BTW': '€ {:,.2f}',
            'BTW': '€ {:,.2f}',
            'Totaal incl. BTW': '€ {:,.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )

    # Export buttons
    st.markdown("---")
    st.markdown("### Download Opties")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Omzet', index=False)

        st.download_button(
            label="📥 Download Excel",
            data=output.getvalue(),
            file_name=f"Omzet_Overzicht_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        # CSV export
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"Omzet_Overzicht_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col3:
        # PDF export placeholder
        st.button("📄 Download PDF", disabled=True, use_container_width=True, help="PDF export komt binnenkort")
