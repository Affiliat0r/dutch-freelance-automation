"""Analytics page with detailed financial insights."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

from config import Config

def show():
    """Display the analytics page."""

    st.title("📊 Analytics & Inzichten")
    st.markdown("Gedetailleerde analyse van uw administratie")

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
            ["Overzicht", "Trends", "Vergelijking", "Voorspelling", "BTW Analyse"]
        )

    st.markdown("---")

    if analysis_type == "Overzicht":
        show_overview_analytics()
    elif analysis_type == "Trends":
        show_trend_analysis()
    elif analysis_type == "Vergelijking":
        show_comparison_analysis()
    elif analysis_type == "Voorspelling":
        show_predictive_analytics()
    elif analysis_type == "BTW Analyse":
        show_vat_analysis()

def show_overview_analytics():
    """Show overview analytics."""

    st.subheader("📈 Overzicht Analyse")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totale Uitgaven", "€ 45,678", "12% ↑")
    with col2:
        st.metric("BTW Terugvordering", "€ 8,234", "8% ↑")
    with col3:
        st.metric("Gem. per Maand", "€ 3,806", "5% ↓")
    with col4:
        st.metric("Grootste Uitgave", "€ 2,345", "MediaMarkt")

    st.markdown("---")

    # Category breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Uitgaven per Categorie")

        category_data = pd.DataFrame({
            'Categorie': Config.EXPENSE_CATEGORIES,
            'Bedrag': np.random.randint(1000, 8000, len(Config.EXPENSE_CATEGORIES))
        })

        fig_bar = px.bar(
            category_data,
            x='Bedrag',
            y='Categorie',
            orientation='h',
            color='Bedrag',
            color_continuous_scale='Blues'
        )
        fig_bar.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.markdown("### Top 10 Leveranciers")

        vendor_data = pd.DataFrame({
            'Leverancier': ['Bol.com', 'Coolblue', 'MediaMarkt', 'Albert Heijn',
                           'Amazon', 'HEMA', 'Kruidvat', 'Jumbo', 'Action', 'Praxis'],
            'Bedrag': [5432, 4321, 3210, 2987, 2345, 1987, 1654, 1432, 1234, 987]
        })

        fig_pie = px.pie(
            vendor_data,
            values='Bedrag',
            names='Leverancier',
            hole=0.4
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Monthly summary table
    st.markdown("### Maandelijks Overzicht")

    monthly_data = create_monthly_summary()
    st.dataframe(
        monthly_data.style.format({
            'Uitgaven': '€ {:,.2f}',
            'BTW': '€ {:,.2f}',
            'Netto': '€ {:,.2f}',
            'Aantal': '{:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )

def show_trend_analysis():
    """Show trend analysis."""

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
            ["Dagelijks", "Wekelijks", "Maandelijks", "Per Kwartaal"]
        )

    # Generate trend data
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    trend_values = np.cumsum(np.random.randn(len(dates)) * 100) + 10000

    trend_df = pd.DataFrame({
        'Datum': dates,
        'Waarde': trend_values,
        'Moving_Avg': pd.Series(trend_values).rolling(window=30).mean()
    })

    # Create trend chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=trend_df['Datum'],
        y=trend_df['Waarde'],
        mode='lines',
        name='Werkelijk',
        line=dict(color='#1f4788', width=1)
    ))

    fig.add_trace(go.Scatter(
        x=trend_df['Datum'],
        y=trend_df['Moving_Avg'],
        mode='lines',
        name='30-dagen gemiddelde',
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
    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("""
        **📊 Trend Inzicht**

        Stijgende trend van 15% over de afgelopen periode
        """)

    with col2:
        st.warning("""
        **⚠️ Aandachtspunt**

        Piek in uitgaven gedetecteerd in maart
        """)

    with col3:
        st.success("""
        **✅ Positief**

        BTW terugvordering consistent boven verwachting
        """)

def show_comparison_analysis():
    """Show comparison analysis."""

    st.subheader("📊 Vergelijkingsanalyse")

    comparison_type = st.radio(
        "Vergelijk:",
        ["Jaar-op-jaar", "Kwartaal-op-kwartaal", "Maand-op-maand"],
        horizontal=True
    )

    # Create comparison data
    categories = Config.EXPENSE_CATEGORIES
    current_period = np.random.randint(1000, 5000, len(categories))
    previous_period = np.random.randint(1000, 5000, len(categories))

    comparison_df = pd.DataFrame({
        'Categorie': categories,
        'Huidige Periode': current_period,
        'Vorige Periode': previous_period,
        'Verschil': current_period - previous_period,
        'Verschil %': ((current_period - previous_period) / previous_period * 100)
    })

    # Grouped bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Vorige Periode',
        x=categories,
        y=previous_period,
        marker_color='lightgray'
    ))

    fig.add_trace(go.Bar(
        name='Huidige Periode',
        x=categories,
        y=current_period,
        marker_color='#1f4788'
    ))

    fig.update_layout(
        title="Vergelijking per Categorie",
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
        }).applymap(
            lambda x: 'color: green' if isinstance(x, (int, float)) and x > 0 else 'color: red',
            subset=['Verschil', 'Verschil %']
        ),
        use_container_width=True,
        hide_index=True
    )

def show_predictive_analytics():
    """Show predictive analytics."""

    st.subheader("🔮 Voorspellende Analyse")

    st.info("""
    **Machine Learning Voorspellingen**

    Op basis van historische gegevens voorspellen we toekomstige uitgaven en BTW terugvorderingen.
    """)

    # Forecast settings
    col1, col2 = st.columns(2)

    with col1:
        forecast_months = st.slider(
            "Voorspel aantal maanden",
            min_value=1,
            max_value=12,
            value=3
        )

    with col2:
        confidence_level = st.select_slider(
            "Betrouwbaarheidsniveau",
            options=["Laag", "Gemiddeld", "Hoog"],
            value="Gemiddeld"
        )

    # Generate forecast data
    historical_dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='M')
    historical_values = np.random.randint(3000, 6000, len(historical_dates))

    forecast_dates = pd.date_range(start='2025-01-01', periods=forecast_months, freq='M')
    forecast_values = np.random.randint(3500, 5500, len(forecast_dates))
    upper_bound = forecast_values + np.random.randint(500, 1000, len(forecast_dates))
    lower_bound = forecast_values - np.random.randint(500, 1000, len(forecast_dates))

    # Create forecast chart
    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=historical_dates,
        y=historical_values,
        mode='lines+markers',
        name='Historisch',
        line=dict(color='#1f4788', width=2)
    ))

    # Forecast
    fig.add_trace(go.Scatter(
        x=forecast_dates,
        y=forecast_values,
        mode='lines+markers',
        name='Voorspelling',
        line=dict(color='#ff7f0e', width=2, dash='dash')
    ))

    # Confidence interval
    fig.add_trace(go.Scatter(
        x=forecast_dates,
        y=upper_bound,
        fill=None,
        mode='lines',
        line_color='rgba(0,100,80,0)',
        showlegend=False
    ))

    fig.add_trace(go.Scatter(
        x=forecast_dates,
        y=lower_bound,
        fill='tonexty',
        mode='lines',
        line_color='rgba(0,100,80,0)',
        name='Betrouwbaarheidsinterval'
    ))

    fig.update_layout(
        title="Uitgaven Voorspelling",
        xaxis_title="Maand",
        yaxis_title="Bedrag (€)",
        height=500,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    # Predictions summary
    st.markdown("### Voorspelde Waarden")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Verwachte Uitgaven (3 maanden)",
            f"€ {sum(forecast_values):,.2f}",
            f"± € {np.mean(upper_bound - forecast_values):,.2f}"
        )

    with col2:
        st.metric(
            "Verwachte BTW Terug",
            f"€ {sum(forecast_values) * 0.17:,.2f}",
            "Gebaseerd op 17% gemiddeld"
        )

    with col3:
        st.metric(
            "Betrouwbaarheid",
            "82%",
            "Gebaseerd op 12 maanden data"
        )

def show_vat_analysis():
    """Show VAT analysis."""

    st.subheader("💶 BTW Analyse")

    # VAT rate breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### BTW Tarieven Verdeling")

        vat_data = pd.DataFrame({
            'Tarief': ['6% (oud)', '9%', '21%', 'Vrijgesteld'],
            'Bedrag': [1234, 2345, 8765, 432]
        })

        fig_donut = px.pie(
            vat_data,
            values='Bedrag',
            names='Tarief',
            hole=0.5,
            color_discrete_sequence=['#e8f4f8', '#b3d9e8', '#5ca3c4', '#1f4788']
        )
        fig_donut.update_layout(height=350)
        st.plotly_chart(fig_donut, use_container_width=True)

    with col2:
        st.markdown("### BTW Terugvordering per Maand")

        months = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
        vat_refund = np.random.randint(500, 1500, 12)

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=months,
            y=vat_refund,
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

    # Deductibility analysis
    st.markdown("### Aftrekbaarheid Analyse")

    deductibility_data = pd.DataFrame({
        'Categorie': Config.EXPENSE_CATEGORIES,
        'BTW Aftrekbaar (%)': [100, 100, 73.5, 0, 0, 100, 100],
        'IB Aftrekbaar (%)': [100, 100, 73.5, 80, 80, 100, 100],
        'Totaal Bedrag': np.random.randint(1000, 5000, len(Config.EXPENSE_CATEGORIES))
    })

    deductibility_data['BTW Terug'] = (
        deductibility_data['Totaal Bedrag'] * 0.21 *
        deductibility_data['BTW Aftrekbaar (%)'] / 100
    )

    st.dataframe(
        deductibility_data.style.format({
            'BTW Aftrekbaar (%)': '{:.1f}%',
            'IB Aftrekbaar (%)': '{:.1f}%',
            'Totaal Bedrag': '€ {:,.2f}',
            'BTW Terug': '€ {:,.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )

    # Summary metrics
    st.markdown("### Samenvatting")

    col1, col2, col3, col4 = st.columns(4)

    total_vat = deductibility_data['BTW Terug'].sum()

    with col1:
        st.metric("Totaal BTW Betaald", f"€ {total_vat * 1.2:,.2f}")

    with col2:
        st.metric("BTW Aftrekbaar", f"€ {total_vat:,.2f}")

    with col3:
        st.metric("Effectief BTW %", "17.3%")

    with col4:
        st.metric("Besparing", f"€ {total_vat * 0.8:,.2f}")

def create_monthly_summary():
    """Create monthly summary data."""

    months = pd.date_range(start='2024-01-01', end='2024-12-31', freq='M')

    data = {
        'Maand': months.strftime('%B %Y'),
        'Aantal': np.random.randint(20, 50, len(months)),
        'Uitgaven': np.random.randint(2000, 6000, len(months)),
        'BTW': np.random.randint(300, 900, len(months)),
        'Netto': np.random.randint(1700, 5100, len(months))
    }

    return pd.DataFrame(data)