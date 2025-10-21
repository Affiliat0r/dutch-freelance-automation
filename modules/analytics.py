"""Analytics page with detailed financial insights based on real receipt data."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from config import Config
from utils.local_storage import load_metadata, filter_receipts
from utils.invoice_storage import filter_invoices, get_invoice_statistics

logger = logging.getLogger(__name__)

def show():
    """Display the analytics page."""

    st.title("📊 Analytics & Inzichten")
    st.markdown("Gedetailleerde analyse van uw administratie")

    # Load receipt data
    receipts = load_metadata()

    # Check if there's any data
    if not receipts:
        st.info("ℹ️ Geen gegevens beschikbaar. Upload eerst bonnen om analyses te zien.")
        if st.button("📤 Ga naar Upload Bonnen", use_container_width=True, type="primary"):
            st.session_state['selected_page'] = "Upload Bonnen"
        return

    # Filter only completed receipts
    completed_receipts = [r for r in receipts if r.get('processing_status') == 'completed']

    if not completed_receipts:
        st.warning("⚠️ Geen verwerkte bonnen beschikbaar voor analyse. Wacht tot bonnen zijn verwerkt.")
        return

    # Date range selector
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        start_date = st.date_input(
            "Van datum",
            value=datetime.now().replace(day=1) - timedelta(days=365),
            format="DD/MM/YYYY"
        )

    with col2:
        end_date = st.date_input(
            "Tot datum",
            value=datetime.now(),
            format="DD/MM/YYYY"
        )

    with col3:
        analysis_type = st.selectbox(
            "Analyse type",
            ["Overzicht", "Omzet Analyse", "Winst & Verlies", "Trends", "Vergelijking", "BTW Analyse"]
        )

    st.markdown("---")

    # Apply date filter
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    filtered_receipts = filter_receipts(
        start_date=start_datetime,
        end_date=end_datetime,
        status='completed'
    )

    if not filtered_receipts:
        st.info(f"ℹ️ Geen bonnen gevonden tussen {start_date.strftime('%d-%m-%Y')} en {end_date.strftime('%d-%m-%Y')}")
        return

    if analysis_type == "Overzicht":
        show_overview_analytics(filtered_receipts)
    elif analysis_type == "Omzet Analyse":
        show_revenue_analytics(start_datetime, end_datetime)
    elif analysis_type == "Winst & Verlies":
        show_profit_loss_analysis(filtered_receipts, start_datetime, end_datetime)
    elif analysis_type == "Trends":
        show_trend_analysis(filtered_receipts)
    elif analysis_type == "Vergelijking":
        show_comparison_analysis(filtered_receipts)
    elif analysis_type == "BTW Analyse":
        show_vat_analysis(filtered_receipts)

def show_overview_analytics(receipts):
    """Show overview analytics based on real receipt data."""

    st.subheader("📈 Overzicht Analyse")

    # Calculate real metrics
    total_amount = 0
    total_vat = 0
    total_vat_deductible = 0
    category_amounts = defaultdict(float)
    vendor_amounts = defaultdict(float)
    monthly_data = defaultdict(lambda: {'amount': 0, 'vat': 0, 'count': 0})

    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})
        if not extracted:
            continue

        # Get amounts
        amount = float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0))
        total_amount += amount

        # VAT calculations
        vat_breakdown = extracted.get('vat_breakdown', {})
        vat_6 = float(vat_breakdown.get('6', extracted.get('vat_6_amount', 0)))
        vat_9 = float(vat_breakdown.get('9', extracted.get('vat_9_amount', 0)))
        vat_21 = float(vat_breakdown.get('21', extracted.get('vat_21_amount', 0)))
        receipt_vat = vat_6 + vat_9 + vat_21
        total_vat += receipt_vat

        # VAT deductible
        vat_deductible = float(extracted.get('vat_deductible_amount') or extracted.get('vat_refund_amount', 0))
        if vat_deductible == 0 and receipt_vat > 0:
            # Calculate from percentage
            vat_deduct_pct = extracted.get('vat_deductible_percentage', 100)
            vat_deductible = receipt_vat * (vat_deduct_pct / 100)
        total_vat_deductible += vat_deductible

        # Category breakdown
        category = extracted.get('expense_category') or extracted.get('category', 'Niet gecategoriseerd')
        category_amounts[category] += amount

        # Vendor breakdown
        vendor = extracted.get('vendor_name', 'Onbekend')
        vendor_amounts[vendor] += amount

        # Monthly data
        trans_date = extracted.get('transaction_date') or extracted.get('date')
        if trans_date:
            if isinstance(trans_date, str):
                try:
                    trans_date = datetime.fromisoformat(trans_date)
                except:
                    trans_date = datetime.now()
            month_key = trans_date.strftime('%Y-%m')
            monthly_data[month_key]['amount'] += amount
            monthly_data[month_key]['vat'] += receipt_vat
            monthly_data[month_key]['count'] += 1

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_monthly = total_amount / max(len(monthly_data), 1)
        st.metric("Totale Uitgaven", f"€ {total_amount:,.2f}")

    with col2:
        st.metric("BTW Terugvordering", f"€ {total_vat_deductible:,.2f}")

    with col3:
        st.metric("Gem. per Maand", f"€ {avg_monthly:,.2f}")

    with col4:
        max_vendor = max(vendor_amounts.items(), key=lambda x: x[1]) if vendor_amounts else ('N/A', 0)
        st.metric("Grootste Leverancier", f"€ {max_vendor[1]:,.2f}", max_vendor[0])

    st.markdown("---")

    # Category breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Uitgaven per Categorie")

        if category_amounts:
            category_df = pd.DataFrame([
                {'Categorie': cat, 'Bedrag': amt}
                for cat, amt in sorted(category_amounts.items(), key=lambda x: x[1], reverse=True)
            ])

            fig_bar = px.bar(
                category_df,
                x='Bedrag',
                y='Categorie',
                orientation='h',
                color='Bedrag',
                color_continuous_scale='Blues'
            )
            fig_bar.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Geen categoriegegevens beschikbaar")

    with col2:
        st.markdown("### Top 10 Leveranciers")

        if vendor_amounts:
            # Get top 10 vendors
            top_vendors = sorted(vendor_amounts.items(), key=lambda x: x[1], reverse=True)[:10]
            vendor_df = pd.DataFrame([
                {'Leverancier': vendor, 'Bedrag': amt}
                for vendor, amt in top_vendors
            ])

            fig_pie = px.pie(
                vendor_df,
                values='Bedrag',
                names='Leverancier',
                hole=0.4
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Geen leveranciersgegevens beschikbaar")

    # Monthly summary table
    st.markdown("### Maandelijks Overzicht")

    if monthly_data:
        monthly_df = pd.DataFrame([
            {
                'Maand': datetime.strptime(month, '%Y-%m').strftime('%B %Y'),
                'Aantal': data['count'],
                'Uitgaven': data['amount'],
                'BTW': data['vat'],
                'Netto': data['amount'] - data['vat']
            }
            for month, data in sorted(monthly_data.items())
        ])

        st.dataframe(
            monthly_df.style.format({
                'Uitgaven': '€ {:,.2f}',
                'BTW': '€ {:,.2f}',
                'Netto': '€ {:,.2f}',
                'Aantal': '{:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Geen maandelijkse gegevens beschikbaar")

def show_trend_analysis(receipts):
    """Show trend analysis based on real data."""

    st.subheader("📈 Trend Analyse")

    # Trend options
    col1, col2 = st.columns(2)

    with col1:
        trend_metric = st.selectbox(
            "Selecteer metriek",
            ["Uitgaven", "BTW", "Aantal Bonnen", "Gemiddeld Bedrag"]
        )

    with col2:
        trend_period = st.selectbox(
            "Periode",
            ["Dagelijks", "Wekelijks", "Maandelijks"]
        )

    # Aggregate data by date
    date_data = defaultdict(lambda: {'amount': 0, 'vat': 0, 'count': 0})

    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})
        if not extracted:
            continue

        trans_date = extracted.get('transaction_date') or extracted.get('date')
        if not trans_date:
            continue

        if isinstance(trans_date, str):
            try:
                trans_date = datetime.fromisoformat(trans_date)
            except:
                continue

        # Format date based on period
        if trend_period == "Dagelijks":
            date_key = trans_date.strftime('%Y-%m-%d')
        elif trend_period == "Wekelijks":
            date_key = trans_date.strftime('%Y-W%U')
        else:  # Maandelijks
            date_key = trans_date.strftime('%Y-%m')

        amount = float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0))
        vat_breakdown = extracted.get('vat_breakdown', {})
        vat = sum(float(v) for v in vat_breakdown.values())

        date_data[date_key]['amount'] += amount
        date_data[date_key]['vat'] += vat
        date_data[date_key]['count'] += 1

    if not date_data:
        st.info("Geen gegevens beschikbaar voor trend analyse")
        return

    # Create DataFrame
    trend_df = pd.DataFrame([
        {
            'Datum': date_key,
            'Uitgaven': data['amount'],
            'BTW': data['vat'],
            'Aantal': data['count'],
            'Gemiddeld': data['amount'] / data['count'] if data['count'] > 0 else 0
        }
        for date_key, data in sorted(date_data.items())
    ])

    # Convert date strings to datetime for plotting
    if trend_period == "Dagelijks":
        trend_df['Datum_dt'] = pd.to_datetime(trend_df['Datum'])
    elif trend_period == "Wekelijks":
        trend_df['Datum_dt'] = pd.to_datetime(trend_df['Datum'] + '-1', format='%Y-W%U-%w')
    else:
        trend_df['Datum_dt'] = pd.to_datetime(trend_df['Datum'])

    # Calculate moving average
    metric_map = {
        'Uitgaven': 'Uitgaven',
        'BTW': 'BTW',
        'Aantal Bonnen': 'Aantal',
        'Gemiddeld Bedrag': 'Gemiddeld'
    }
    metric_col = metric_map[trend_metric]

    window_size = min(7, len(trend_df))
    if window_size > 1:
        trend_df['Moving_Avg'] = trend_df[metric_col].rolling(window=window_size, min_periods=1).mean()
    else:
        trend_df['Moving_Avg'] = trend_df[metric_col]

    # Create trend chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=trend_df['Datum_dt'],
        y=trend_df[metric_col],
        mode='lines+markers',
        name='Werkelijk',
        line=dict(color='#1f4788', width=2)
    ))

    if window_size > 1:
        fig.add_trace(go.Scatter(
            x=trend_df['Datum_dt'],
            y=trend_df['Moving_Avg'],
            mode='lines',
            name=f'{window_size}-periode gemiddelde',
            line=dict(color='#ff7f0e', width=2)
        ))

    fig.update_layout(
        title=f"{trend_metric} Trend Analyse",
        xaxis_title="Datum",
        yaxis_title=trend_metric,
        height=500,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    # Insights
    if len(trend_df) >= 2:
        first_value = trend_df[metric_col].iloc[0]
        last_value = trend_df[metric_col].iloc[-1]
        change_pct = ((last_value - first_value) / first_value * 100) if first_value > 0 else 0

        col1, col2, col3 = st.columns(3)

        with col1:
            trend_text = "Stijgende" if change_pct > 0 else "Dalende"
            st.info(f"""
            **📊 Trend Inzicht**

            {trend_text} trend van {abs(change_pct):.1f}% over de geselecteerde periode
            """)

        with col2:
            max_value = trend_df[metric_col].max()
            max_date = trend_df[trend_df[metric_col] == max_value]['Datum'].iloc[0]
            st.warning(f"""
            **📈 Hoogste Waarde**

            € {max_value:,.2f} op {max_date}
            """)

        with col3:
            avg_value = trend_df[metric_col].mean()
            st.success(f"""
            **📊 Gemiddelde**

            € {avg_value:,.2f} per periode
            """)

def show_comparison_analysis(receipts):
    """Show comparison analysis based on real data."""

    st.subheader("📊 Vergelijkingsanalyse")

    comparison_type = st.radio(
        "Vergelijk:",
        ["Maand-op-maand", "Kwartaal-op-kwartaal"],
        horizontal=True
    )

    # Group data by time period and category
    if comparison_type == "Maand-op-maand":
        period_format = '%Y-%m'
        period_name = "Maand"
    else:  # Kwartaal-op-kwartaal
        period_format = '%Y-Q'
        period_name = "Kwartaal"

    period_category_data = defaultdict(lambda: defaultdict(float))

    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})
        if not extracted:
            continue

        trans_date = extracted.get('transaction_date') or extracted.get('date')
        if not trans_date:
            continue

        if isinstance(trans_date, str):
            try:
                trans_date = datetime.fromisoformat(trans_date)
            except:
                continue

        # Format period
        if comparison_type == "Maand-op-maand":
            period = trans_date.strftime(period_format)
        else:
            quarter = (trans_date.month - 1) // 3 + 1
            period = f"{trans_date.year}-Q{quarter}"

        category = extracted.get('expense_category') or extracted.get('category', 'Niet gecategoriseerd')
        amount = float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0))

        period_category_data[period][category] += amount

    if len(period_category_data) < 2:
        st.info(f"Niet genoeg gegevens voor {period_name.lower()}-op-{period_name.lower()} vergelijking. Minimaal 2 periodes nodig.")
        return

    # Get the two most recent periods
    sorted_periods = sorted(period_category_data.keys())
    current_period = sorted_periods[-1]
    previous_period = sorted_periods[-2]

    # Get all categories
    all_categories = set()
    all_categories.update(period_category_data[current_period].keys())
    all_categories.update(period_category_data[previous_period].keys())

    # Create comparison DataFrame
    comparison_data = []
    for category in sorted(all_categories):
        current = period_category_data[current_period].get(category, 0)
        previous = period_category_data[previous_period].get(category, 0)
        diff = current - previous
        diff_pct = (diff / previous * 100) if previous > 0 else 0

        comparison_data.append({
            'Categorie': category,
            'Vorige Periode': previous,
            'Huidige Periode': current,
            'Verschil': diff,
            'Verschil %': diff_pct
        })

    comparison_df = pd.DataFrame(comparison_data)

    # Grouped bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name=f'{period_name}: {previous_period}',
        x=comparison_df['Categorie'],
        y=comparison_df['Vorige Periode'],
        marker_color='lightgray'
    ))

    fig.add_trace(go.Bar(
        name=f'{period_name}: {current_period}',
        x=comparison_df['Categorie'],
        y=comparison_df['Huidige Periode'],
        marker_color='#1f4788'
    ))

    fig.update_layout(
        title=f"Vergelijking per Categorie ({previous_period} vs {current_period})",
        xaxis_title="Categorie",
        yaxis_title="Bedrag (€)",
        barmode='group',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # Comparison table
    st.markdown("### Gedetailleerde Vergelijking")

    st.dataframe(
        comparison_df.style.format({
            'Huidige Periode': '€ {:,.2f}',
            'Vorige Periode': '€ {:,.2f}',
            'Verschil': '€ {:,.2f}',
            'Verschil %': '{:.1f}%'
        }).map(
            lambda x: 'color: green' if isinstance(x, (int, float)) and x > 0 else ('color: red' if isinstance(x, (int, float)) and x < 0 else ''),
            subset=['Verschil', 'Verschil %']
        ),
        use_container_width=True,
        hide_index=True
    )

def show_vat_analysis(receipts):
    """Show VAT analysis based on real data."""

    st.subheader("💶 BTW Analyse")

    # Calculate VAT data
    vat_rate_totals = {'6': 0, '9': 0, '21': 0, '0': 0}
    monthly_vat_deductible = defaultdict(float)
    category_vat_data = defaultdict(lambda: {'total': 0, 'vat_paid': 0, 'vat_deductible': 0, 'btw_pct': 0, 'ib_pct': 0, 'count': 0})

    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})
        if not extracted:
            continue

        # VAT rate breakdown
        vat_breakdown = extracted.get('vat_breakdown', {})
        for rate, amount in vat_breakdown.items():
            vat_rate_totals[str(rate)] += float(amount)

        # Check for zero-rated
        total_vat = sum(float(v) for v in vat_breakdown.values())
        total_amount = float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0))
        if total_vat == 0 and total_amount > 0:
            vat_rate_totals['0'] += total_amount

        # Monthly VAT deductible
        trans_date = extracted.get('transaction_date') or extracted.get('date')
        if trans_date:
            if isinstance(trans_date, str):
                try:
                    trans_date = datetime.fromisoformat(trans_date)
                except:
                    trans_date = datetime.now()
            month_key = trans_date.strftime('%Y-%m')

            vat_deductible = float(extracted.get('vat_deductible_amount') or extracted.get('vat_refund_amount', 0))
            if vat_deductible == 0 and total_vat > 0:
                vat_deduct_pct = extracted.get('vat_deductible_percentage', 100)
                vat_deductible = total_vat * (vat_deduct_pct / 100)
            monthly_vat_deductible[month_key] += vat_deductible

        # Category VAT data
        category = extracted.get('expense_category') or extracted.get('category', 'Niet gecategoriseerd')
        category_vat_data[category]['total'] += total_amount
        category_vat_data[category]['vat_paid'] += total_vat
        category_vat_data[category]['vat_deductible'] += vat_deductible
        category_vat_data[category]['btw_pct'] = extracted.get('vat_deductible_percentage', 100)
        category_vat_data[category]['ib_pct'] = extracted.get('ib_deductible_percentage', 100)
        category_vat_data[category]['count'] += 1

    # VAT rate breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### BTW Tarieven Verdeling")

        vat_data = pd.DataFrame([
            {'Tarief': '0% (vrijgesteld)', 'Bedrag': vat_rate_totals['0']},
            {'Tarief': '6% (oud)', 'Bedrag': vat_rate_totals['6']},
            {'Tarief': '9%', 'Bedrag': vat_rate_totals['9']},
            {'Tarief': '21%', 'Bedrag': vat_rate_totals['21']}
        ])

        # Filter out zero amounts
        vat_data = vat_data[vat_data['Bedrag'] > 0]

        if not vat_data.empty:
            fig_donut = px.pie(
                vat_data,
                values='Bedrag',
                names='Tarief',
                hole=0.5,
                color_discrete_sequence=['#e8f4f8', '#b3d9e8', '#5ca3c4', '#1f4788']
            )
            fig_donut.update_layout(height=350)
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Geen BTW gegevens beschikbaar")

    with col2:
        st.markdown("### BTW Terugvordering per Maand")

        if monthly_vat_deductible:
            monthly_df = pd.DataFrame([
                {'Maand': month, 'BTW Terug': amount}
                for month, amount in sorted(monthly_vat_deductible.items())
            ])

            # Convert month to readable format
            monthly_df['Maand_dt'] = pd.to_datetime(monthly_df['Maand'])
            monthly_df['Maand_label'] = monthly_df['Maand_dt'].dt.strftime('%b %Y')

            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=monthly_df['Maand_dt'],
                y=monthly_df['BTW Terug'],
                mode='lines+markers',
                fill='tozeroy',
                line=dict(color='#1f4788', width=2)
            ))
            fig_line.update_layout(
                height=350,
                xaxis_title="Maand",
                yaxis_title="BTW Terugvordering (€)"
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Geen maandelijkse BTW gegevens beschikbaar")

    # Deductibility analysis
    st.markdown("### Aftrekbaarheid Analyse per Categorie")

    if category_vat_data:
        deductibility_df = pd.DataFrame([
            {
                'Categorie': category,
                'BTW Aftrekbaar (%)': data['btw_pct'],
                'IB Aftrekbaar (%)': data['ib_pct'],
                'Totaal Bedrag': data['total'],
                'BTW Betaald': data['vat_paid'],
                'BTW Terug': data['vat_deductible']
            }
            for category, data in sorted(category_vat_data.items())
        ])

        st.dataframe(
            deductibility_df.style.format({
                'BTW Aftrekbaar (%)': '{:.0f}%',
                'IB Aftrekbaar (%)': '{:.0f}%',
                'Totaal Bedrag': '€ {:,.2f}',
                'BTW Betaald': '€ {:,.2f}',
                'BTW Terug': '€ {:,.2f}'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Geen aftrekbaarheidsgegevens beschikbaar")

    # Summary metrics
    st.markdown("### Samenvatting")

    total_vat_paid = sum(vat_rate_totals.values())
    total_vat_deductible = sum(monthly_vat_deductible.values())
    total_receipts_amount = sum(data['total'] for data in category_vat_data.values())
    effective_vat_pct = (total_vat_paid / total_receipts_amount * 100) if total_receipts_amount > 0 else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totaal BTW Betaald", f"€ {total_vat_paid:,.2f}")

    with col2:
        st.metric("BTW Aftrekbaar", f"€ {total_vat_deductible:,.2f}")

    with col3:
        st.metric("Effectief BTW %", f"{effective_vat_pct:.1f}%")

    with col4:
        saving = total_vat_deductible
        st.metric("Besparing", f"€ {saving:,.2f}")

def show_revenue_analytics(start_date, end_date):
    """Show revenue analytics from invoices."""

    st.subheader("💰 Omzet Analyse")

    # Get invoice data
    invoices = filter_invoices(start_date=start_date, end_date=end_date)

    if not invoices:
        st.info("ℹ️ Geen facturen gevonden in de geselecteerde periode.")
        if st.button("📝 Ga naar Facturen", use_container_width=True, type="primary"):
            st.session_state['selected_page'] = "Facturen"
            st.rerun()
        return

    # Calculate metrics
    total_revenue = 0
    total_vat_payable = 0
    total_paid = 0
    total_unpaid = 0
    total_overdue = 0
    client_revenue = defaultdict(float)
    monthly_revenue = defaultdict(lambda: {'revenue': 0, 'vat': 0, 'count': 0, 'paid': 0, 'unpaid': 0})

    for invoice in invoices:
        total_incl_vat = invoice.get('total_incl_vat', 0)
        vat_amount = invoice.get('vat_amount', 0)
        payment_status = invoice.get('payment_status', 'unpaid')
        client_name = invoice.get('client_name', 'Onbekend')

        total_revenue += total_incl_vat
        total_vat_payable += vat_amount

        if payment_status == 'paid':
            total_paid += total_incl_vat
        else:
            total_unpaid += total_incl_vat
            if payment_status == 'overdue':
                total_overdue += total_incl_vat

        client_revenue[client_name] += total_incl_vat

        # Monthly data
        invoice_date = invoice.get('invoice_date')
        if invoice_date:
            if isinstance(invoice_date, str):
                try:
                    invoice_date = datetime.fromisoformat(invoice_date)
                except:
                    invoice_date = datetime.now()
            month_key = invoice_date.strftime('%Y-%m')
            monthly_revenue[month_key]['revenue'] += total_incl_vat
            monthly_revenue[month_key]['vat'] += vat_amount
            monthly_revenue[month_key]['count'] += 1
            if payment_status == 'paid':
                monthly_revenue[month_key]['paid'] += total_incl_vat
            else:
                monthly_revenue[month_key]['unpaid'] += total_incl_vat

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totale Omzet", f"€ {total_revenue:,.2f}", f"{len(invoices)} facturen")

    with col2:
        st.metric("BTW Te Betalen", f"€ {total_vat_payable:,.2f}")

    with col3:
        st.metric("Betaald", f"€ {total_paid:,.2f}", delta="Ontvangen")

    with col4:
        st.metric("Openstaand", f"€ {total_unpaid:,.2f}", delta=f"€ {total_overdue:,.2f} achterstallig" if total_overdue > 0 else None, delta_color="inverse" if total_overdue > 0 else "off")

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Omzet per Klant")

        if client_revenue:
            # Get top 10 clients
            top_clients = sorted(client_revenue.items(), key=lambda x: x[1], reverse=True)[:10]
            client_df = pd.DataFrame([
                {'Klant': client, 'Omzet': revenue}
                for client, revenue in top_clients
            ])

            fig_bar = px.bar(
                client_df,
                x='Omzet',
                y='Klant',
                orientation='h',
                color='Omzet',
                color_continuous_scale='Greens'
            )
            fig_bar.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Geen klantgegevens beschikbaar")

    with col2:
        st.markdown("### Betalingsstatus Verdeling")

        payment_data = pd.DataFrame([
            {'Status': 'Betaald', 'Bedrag': total_paid},
            {'Status': 'Openstaand', 'Bedrag': total_unpaid - total_overdue},
            {'Status': 'Achterstallig', 'Bedrag': total_overdue}
        ])

        payment_data = payment_data[payment_data['Bedrag'] > 0]

        if not payment_data.empty:
            fig_pie = px.pie(
                payment_data,
                values='Bedrag',
                names='Status',
                color='Status',
                color_discrete_map={
                    'Betaald': '#2ecc71',
                    'Openstaand': '#f39c12',
                    'Achterstallig': '#e74c3c'
                }
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Geen betalingsgegevens beschikbaar")

    # Monthly revenue chart
    st.markdown("### Maandelijkse Omzet Trend")

    if monthly_revenue:
        monthly_df = pd.DataFrame([
            {
                'Maand': datetime.strptime(month, '%Y-%m'),
                'Omzet': data['revenue'],
                'BTW': data['vat'],
                'Betaald': data['paid'],
                'Openstaand': data['unpaid']
            }
            for month, data in sorted(monthly_revenue.items())
        ])

        fig = go.Figure()

        fig.add_trace(go.Bar(
            name='Betaald',
            x=monthly_df['Maand'],
            y=monthly_df['Betaald'],
            marker_color='#2ecc71'
        ))

        fig.add_trace(go.Bar(
            name='Openstaand',
            x=monthly_df['Maand'],
            y=monthly_df['Openstaand'],
            marker_color='#f39c12'
        ))

        fig.update_layout(
            height=400,
            xaxis_title="Maand",
            yaxis_title="Omzet (€)",
            barmode='stack',
            hovermode='x unified'
        )

        st.plotly_chart(fig, use_container_width=True)

        # Monthly summary table
        st.markdown("### Maandelijks Overzicht")

        summary_df = pd.DataFrame([
            {
                'Maand': month.strftime('%B %Y'),
                'Aantal Facturen': data['count'],
                'Totale Omzet': data['revenue'],
                'BTW': data['vat'],
                'Betaald': data['paid'],
                'Openstaand': data['unpaid']
            }
            for month, data in [(datetime.strptime(m, '%Y-%m'), d) for m, d in sorted(monthly_revenue.items())]
        ])

        st.dataframe(
            summary_df.style.format({
                'Totale Omzet': '€ {:,.2f}',
                'BTW': '€ {:,.2f}',
                'Betaald': '€ {:,.2f}',
                'Openstaand': '€ {:,.2f}',
                'Aantal Facturen': '{:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Geen maandelijkse gegevens beschikbaar")

def show_profit_loss_analysis(receipts, start_date, end_date):
    """Show profit and loss analysis combining income and expenses."""

    st.subheader("📊 Winst & Verlies Analyse")

    # Get both receipts and invoices
    invoices = filter_invoices(start_date=start_date, end_date=end_date)

    # Calculate expenses
    total_expenses = 0
    total_vat_refund = 0
    expenses_excl_vat = 0

    for receipt in receipts:
        extracted = receipt.get('extracted_data', {})
        if not extracted:
            continue

        amount = float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0))
        total_expenses += amount

        vat_deductible = float(extracted.get('vat_deductible_amount') or extracted.get('vat_refund_amount', 0))
        total_vat_refund += vat_deductible

        amount_excl = float(extracted.get('amount_excl_vat', 0))
        if amount_excl == 0:
            # Calculate if not present
            vat_breakdown = extracted.get('vat_breakdown', {})
            total_vat = sum(float(v) for v in vat_breakdown.values())
            amount_excl = amount - total_vat
        expenses_excl_vat += amount_excl

    # Calculate revenue
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

    # Calculate profit
    gross_profit = total_revenue - total_expenses
    net_vat_position = total_vat_payable - total_vat_refund
    profit_excl_vat = revenue_excl_vat - expenses_excl_vat

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totale Omzet", f"€ {total_revenue:,.2f}", f"{len(invoices)} facturen")

    with col2:
        st.metric("Totale Kosten", f"€ {total_expenses:,.2f}", f"{len(receipts)} bonnen")

    with col3:
        profit_color = "normal" if gross_profit >= 0 else "inverse"
        st.metric("Bruto Resultaat", f"€ {gross_profit:,.2f}", "Winst" if gross_profit >= 0 else "Verlies", delta_color=profit_color)

    with col4:
        margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        st.metric("Winstmarge", f"{margin:.1f}%")

    st.markdown("---")

    # P&L Statement
    st.markdown("### Resultatenrekening")

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

    pl_df = pd.DataFrame(pl_data)

    # Format and style
    def highlight_pl(row):
        if row['Categorie'] == 'Resultaat':
            return ['background-color: #d4edda; font-weight: bold'] * len(row)
        elif row['Categorie'] in ['Omzet', 'BTW']:
            return ['background-color: #e8f4f8'] * len(row)
        elif row['Categorie'] == 'Kosten':
            return ['background-color: #fff3cd'] * len(row)
        elif pd.isna(row['Bedrag']):
            return ['border-top: 2px solid #dee2e6'] * len(row)
        return [''] * len(row)

    styled_pl = pl_df.style.format({
        'Bedrag': lambda x: f"€ {x:,.2f}" if pd.notna(x) else ""
    }).apply(highlight_pl, axis=1)

    st.dataframe(styled_pl, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Visual comparison
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Omzet vs Kosten")

        comparison_data = pd.DataFrame([
            {'Categorie': 'Omzet (excl. BTW)', 'Bedrag': revenue_excl_vat},
            {'Categorie': 'Kosten (excl. BTW)', 'Bedrag': expenses_excl_vat},
            {'Categorie': 'Resultaat', 'Bedrag': profit_excl_vat}
        ])

        fig = px.bar(
            comparison_data,
            x='Categorie',
            y='Bedrag',
            color='Categorie',
            color_discrete_map={
                'Omzet (excl. BTW)': '#2ecc71',
                'Kosten (excl. BTW)': '#e74c3c',
                'Resultaat': '#3498db'
            }
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### BTW Positie")

        vat_data = pd.DataFrame([
            {'Categorie': 'BTW Te Betalen', 'Bedrag': total_vat_payable},
            {'Categorie': 'BTW Terugvordering', 'Bedrag': total_vat_refund},
            {'Categorie': 'Netto BTW', 'Bedrag': abs(net_vat_position)}
        ])

        fig = px.bar(
            vat_data,
            x='Categorie',
            y='Bedrag',
            color='Categorie',
            color_discrete_map={
                'BTW Te Betalen': '#e74c3c',
                'BTW Terugvordering': '#2ecc71',
                'Netto BTW': '#f39c12'
            }
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Summary insights
    st.markdown("### Inzichten")

    col1, col2, col3 = st.columns(3)

    with col1:
        if total_revenue > 0:
            expense_ratio = (total_expenses / total_revenue * 100)
            st.info(f"""
            **💡 Kostenratio**

            Kosten zijn {expense_ratio:.1f}% van de omzet
            """)

    with col2:
        if gross_profit >= 0:
            st.success(f"""
            **✅ Positief Resultaat**

            Winst van € {gross_profit:,.2f}
            """)
        else:
            st.error(f"""
            **⚠️ Negatief Resultaat**

            Verlies van € {abs(gross_profit):,.2f}
            """)

    with col3:
        if net_vat_position > 0:
            st.warning(f"""
            **💶 BTW Te Betalen**

            € {net_vat_position:,.2f} aan Belastingdienst
            """)
        elif net_vat_position < 0:
            st.success(f"""
            **💶 BTW Terug te Vorderen**

            € {abs(net_vat_position):,.2f} van Belastingdienst
            """)
        else:
            st.info("""
            **💶 BTW Neutraal**

            Geen netto BTW positie
            """)
