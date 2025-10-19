"""Receipt management page for viewing and editing receipts."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging

from config import Config

logger = logging.getLogger(__name__)

def show():
    """Display the receipt management page."""

    st.title("📁 Bonnen Beheer")
    st.markdown("Bekijk, bewerk en beheer uw verwerkte bonnen")

    # Filters section
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

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
            selected_categories = st.multiselect(
                "Categorieën",
                Config.EXPENSE_CATEGORIES,
                default=[]
            )

        with col4:
            status_filter = st.selectbox(
                "Status",
                ["Alle", "Verwerkt", "In behandeling", "Review nodig", "Mislukt"]
            )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            vendor_search = st.text_input("Zoek leverancier", placeholder="Naam...")

        with col2:
            min_amount = st.number_input("Min bedrag (€)", min_value=0.0, value=0.0, step=0.01)

        with col3:
            max_amount = st.number_input("Max bedrag (€)", min_value=0.0, value=10000.0, step=0.01)

        with col4:
            if st.button("🔄 Filter toepassen", use_container_width=True):
                st.rerun()

    st.markdown("---")

    # Sample receipt data
    receipt_data = create_sample_receipt_data()

    # Statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Totaal bonnen", len(receipt_data))

    with col2:
        total_amount = receipt_data['Totaal incl. BTW'].sum()
        st.metric("Totaal bedrag", f"€ {total_amount:,.2f}")

    with col3:
        vat_amount = receipt_data['BTW bedrag'].sum()
        st.metric("Totaal BTW", f"€ {vat_amount:,.2f}")

    with col4:
        avg_amount = receipt_data['Totaal incl. BTW'].mean()
        st.metric("Gem. bedrag", f"€ {avg_amount:,.2f}")

    st.markdown("---")

    # Main receipt table
    st.subheader("📋 Bonnen Overzicht")

    # Add action buttons above table
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("✏️ Bewerken", use_container_width=True):
            st.info("Selecteer bonnen om te bewerken")

    with col2:
        if st.button("🗑️ Verwijderen", use_container_width=True):
            st.warning("Selecteer bonnen om te verwijderen")

    with col3:
        if st.button("✅ Goedkeuren", use_container_width=True):
            st.success("Bonnen goedgekeurd")

    with col4:
        if st.button("📥 Downloaden", use_container_width=True):
            st.info("Download wordt voorbereid...")

    with col5:
        if st.button("💾 Exporteren", use_container_width=True):
            st.info("Export wordt voorbereid...")

    # Display receipt table with selection
    selected_receipts = display_receipt_table(receipt_data)

    if selected_receipts:
        st.info(f"{len(selected_receipts)} bon(nen) geselecteerd")

    st.markdown("---")

    # Receipt detail view
    if st.checkbox("🔍 Gedetailleerde weergave"):
        show_receipt_details(receipt_data)

def create_sample_receipt_data():
    """Create sample receipt data for demonstration."""

    data = {
        'ID': [f'R2024{i:04d}' for i in range(1, 21)],
        'Datum': pd.date_range(start='2024-11-01', periods=20, freq='D'),
        'Leverancier': ['Albert Heijn', 'Bol.com', 'Coolblue', 'HEMA', 'MediaMarkt'] * 4,
        'Categorie': ['Kantoorkosten', 'Beroepskosten', 'Representatiekosten - Type 1',
                     'Vervoerskosten', 'Zakelijke opleidingskosten'] * 4,
        'Bedrag excl. BTW': [41.32, 103.31, 206.61, 28.93, 413.22] * 4,
        'BTW bedrag': [8.68, 21.69, 43.39, 6.07, 86.78] * 4,
        'Totaal incl. BTW': [50.00, 125.00, 250.00, 35.00, 500.00] * 4,
        'BTW %': [21, 21, 21, 21, 21] * 4,
        'Status': ['Verwerkt', 'Verwerkt', 'In behandeling', 'Review nodig', 'Verwerkt'] * 4,
        'Bestand': ['receipt_001.pdf', 'receipt_002.jpg', 'receipt_003.pdf',
                   'receipt_004.png', 'receipt_005.pdf'] * 4
    }

    df = pd.DataFrame(data)
    return df

def display_receipt_table(df):
    """Display receipt table with selection capability."""

    # Add checkbox column
    df_display = df.copy()
    df_display.insert(0, 'Selecteer', False)

    # Format columns for display
    df_display['Datum'] = df_display['Datum'].dt.strftime('%d-%m-%Y')
    df_display['Bedrag excl. BTW'] = df_display['Bedrag excl. BTW'].apply(lambda x: f"€ {x:,.2f}")
    df_display['BTW bedrag'] = df_display['BTW bedrag'].apply(lambda x: f"€ {x:,.2f}")
    df_display['Totaal incl. BTW'] = df_display['Totaal incl. BTW'].apply(lambda x: f"€ {x:,.2f}")

    # Use st.data_editor for interactive table
    edited_df = st.data_editor(
        df_display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Selecteer": st.column_config.CheckboxColumn(
                "Selecteer",
                help="Selecteer bonnen voor bulk acties",
                default=False,
            ),
            "ID": st.column_config.TextColumn(
                "Bon ID",
                help="Unieke identificatie van de bon",
                width="small",
            ),
            "Datum": st.column_config.TextColumn(
                "Datum",
                width="small",
            ),
            "Leverancier": st.column_config.TextColumn(
                "Leverancier",
                width="medium",
            ),
            "Categorie": st.column_config.SelectboxColumn(
                "Categorie",
                help="Expense categorie",
                width="medium",
                options=Config.EXPENSE_CATEGORIES,
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                help="Verwerkingsstatus",
                width="small",
                options=["Verwerkt", "In behandeling", "Review nodig", "Mislukt"],
            ),
            "Bestand": st.column_config.TextColumn(
                "Bestand",
                width="small",
            ),
        },
        disabled=["ID", "Bestand"],
    )

    # Get selected rows
    selected_rows = edited_df[edited_df['Selecteer'] == True]
    return selected_rows

def show_receipt_details(df):
    """Show detailed view of selected receipt."""

    st.subheader("📄 Bon Details")

    # Select receipt to view
    receipt_id = st.selectbox(
        "Selecteer bon voor details:",
        df['ID'].tolist()
    )

    if receipt_id:
        receipt = df[df['ID'] == receipt_id].iloc[0]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🖼️ Bon Afbeelding")

            # Placeholder for receipt image
            st.info("Bon afbeelding wordt hier getoond")

            # Image controls
            col1a, col1b, col1c = st.columns(3)
            with col1a:
                st.button("🔍 Zoom", use_container_width=True)
            with col1b:
                st.button("🔄 Roteren", use_container_width=True)
            with col1c:
                st.button("📥 Download", use_container_width=True)

        with col2:
            st.markdown("### 📊 Geëxtraheerde Gegevens")

            # Editable fields
            edited_date = st.date_input(
                "Datum",
                value=receipt['Datum'],
                format="DD/MM/YYYY"
            )

            edited_vendor = st.text_input(
                "Leverancier",
                value=receipt['Leverancier']
            )

            edited_category = st.selectbox(
                "Categorie",
                Config.EXPENSE_CATEGORIES,
                index=Config.EXPENSE_CATEGORIES.index(receipt['Categorie'])
            )

            col2a, col2b = st.columns(2)
            with col2a:
                edited_amount_excl = st.number_input(
                    "Bedrag excl. BTW (€)",
                    value=float(receipt['Bedrag excl. BTW']),
                    step=0.01
                )

            with col2b:
                edited_vat_rate = st.selectbox(
                    "BTW tarief (%)",
                    [6, 9, 21],
                    index=2
                )

            vat_amount = edited_amount_excl * (edited_vat_rate / 100)
            total_amount = edited_amount_excl + vat_amount

            col2c, col2d = st.columns(2)
            with col2c:
                st.number_input(
                    "BTW bedrag (€)",
                    value=vat_amount,
                    disabled=True
                )

            with col2d:
                st.number_input(
                    "Totaal incl. BTW (€)",
                    value=total_amount,
                    disabled=True
                )

            # Tax deduction settings
            st.markdown("#### Belasting Aftrek")

            col2e, col2f = st.columns(2)
            with col2e:
                vat_deductible = st.slider(
                    "BTW aftrekbaar (%)",
                    min_value=0,
                    max_value=100,
                    value=100,
                    step=5
                )

            with col2f:
                ib_deductible = st.slider(
                    "IB aftrekbaar (%)",
                    min_value=0,
                    max_value=100,
                    value=100,
                    step=5
                )

            # Notes
            notes = st.text_area(
                "Notities / Toelichting",
                value="",
                height=100
            )

            # Save button
            if st.button("💾 Wijzigingen Opslaan", use_container_width=True, type="primary"):
                st.success("✅ Wijzigingen opgeslagen!")

            # Additional info
            st.markdown("---")
            st.markdown("#### 📝 Metadata")

            st.text(f"Upload datum: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
            st.text(f"Laatst gewijzigd: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
            st.text(f"Bestandsnaam: {receipt['Bestand']}")
            st.text(f"Status: {receipt['Status']}")