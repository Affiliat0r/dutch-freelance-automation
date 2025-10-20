"""Receipt management page for viewing and editing receipts."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

from config import Config
from utils.local_storage import (
    filter_receipts,
    get_receipt,
    update_receipt_data,
    load_metadata,
    delete_receipt,
    update_receipt_status
)
import zipfile
import io

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
                ["Alle", "completed", "pending", "processing", "failed"],
                format_func=lambda x: {
                    "Alle": "Alle",
                    "completed": "Verwerkt",
                    "pending": "In behandeling",
                    "processing": "Bezig...",
                    "failed": "Mislukt"
                }.get(x, x)
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

    # Get receipt data from local storage
    try:
        # Convert dates
        start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None

        # Apply filters
        receipts = filter_receipts(
            start_date=start_datetime,
            end_date=end_datetime,
            status=status_filter if status_filter != "Alle" else None,
            categories=selected_categories if selected_categories else None,
            vendor=vendor_search if vendor_search else None,
            min_amount=min_amount if min_amount > 0 else None,
            max_amount=max_amount if max_amount < 10000 else None
        )

        # Convert to DataFrame format
        receipt_data = []
        for receipt in receipts:
            extracted = receipt.get('extracted_data', {})

            # Parse upload date
            upload_date = receipt.get('upload_date')
            if isinstance(upload_date, str):
                try:
                    upload_date = datetime.fromisoformat(upload_date)
                except:
                    upload_date = datetime.now()

            # Get transaction date
            trans_date = extracted.get('transaction_date') or extracted.get('date')
            if isinstance(trans_date, str):
                try:
                    trans_date = datetime.fromisoformat(trans_date)
                except:
                    trans_date = upload_date
            elif trans_date is None:
                trans_date = upload_date

            # Calculate VAT amounts
            vat_breakdown = extracted.get('vat_breakdown', {})
            vat_6 = vat_breakdown.get('6', extracted.get('vat_6_amount', 0))
            vat_9 = vat_breakdown.get('9', extracted.get('vat_9_amount', 0))
            vat_21 = vat_breakdown.get('21', extracted.get('vat_21_amount', 0))
            total_vat = vat_6 + vat_9 + vat_21

            if extracted:
                receipt_data.append({
                    'ID': receipt['id'],
                    'Datum': trans_date,
                    'Leverancier': extracted.get('vendor_name', 'Onbekend'),
                    'Categorie': extracted.get('expense_category') or extracted.get('category', 'Niet gecategoriseerd'),
                    'Bedrag excl. BTW': float(extracted.get('amount_excl_vat') or extracted.get('total_excl_vat', 0)),
                    'BTW bedrag': float(total_vat),
                    'Totaal incl. BTW': float(extracted.get('total_incl_vat') or extracted.get('total_amount', 0)),
                    'Status': receipt['processing_status'],
                    'Bestand': receipt['filename']
                })
            else:
                receipt_data.append({
                    'ID': receipt['id'],
                    'Datum': upload_date,
                    'Leverancier': 'Nog niet verwerkt',
                    'Categorie': 'Niet gecategoriseerd',
                    'Bedrag excl. BTW': 0.0,
                    'BTW bedrag': 0.0,
                    'Totaal incl. BTW': 0.0,
                    'Status': receipt['processing_status'],
                    'Bestand': receipt['filename']
                })

        if not receipt_data:
            st.info("ℹ️ Geen bonnen gevonden met de huidige filters. Upload bonnen om te beginnen!")
            if st.button("📤 Ga naar Upload Bonnen", use_container_width=True, type="primary"):
                st.session_state['selected_page'] = "Upload Bonnen"
            return

        df = pd.DataFrame(receipt_data)

        # Statistics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Totaal bonnen", len(df))

        with col2:
            total_amount = df['Totaal incl. BTW'].sum()
            st.metric("Totaal bedrag", f"€ {total_amount:,.2f}")

        with col3:
            vat_amount = df['BTW bedrag'].sum()
            st.metric("Totaal BTW", f"€ {vat_amount:,.2f}")

        with col4:
            avg_amount = df['Totaal incl. BTW'].mean()
            st.metric("Gem. bedrag", f"€ {avg_amount:,.2f}")

        st.markdown("---")

        # Main receipt table
        st.subheader("📋 Bonnen Overzicht")

        # Display receipt table with selection first
        selected_receipts = display_receipt_table(df)

        # Add action buttons above table
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("✏️ Bewerken", use_container_width=True, key="btn_edit"):
                if len(selected_receipts) > 0:
                    # Store selected IDs in session state and open detailed view
                    st.session_state['edit_receipt_id'] = selected_receipts.iloc[0]['ID']
                    st.session_state['show_detail_view'] = True
                    st.rerun()
                else:
                    st.warning("⚠️ Selecteer eerst één bon om te bewerken")

        with col2:
            if st.button("🗑️ Verwijderen", use_container_width=True, key="btn_delete"):
                if len(selected_receipts) > 0:
                    st.session_state['confirm_delete'] = True
                    st.session_state['receipts_to_delete'] = selected_receipts['ID'].tolist()
                else:
                    st.warning("⚠️ Selecteer bonnen om te verwijderen")

        with col3:
            if st.button("✅ Goedkeuren", use_container_width=True, key="btn_approve"):
                if len(selected_receipts) > 0:
                    # Approve selected receipts
                    approved_count = 0
                    for receipt_id in selected_receipts['ID'].tolist():
                        try:
                            update_receipt_status(receipt_id, 'completed')
                            approved_count += 1
                        except Exception as e:
                            logger.error(f"Error approving receipt {receipt_id}: {e}")
                    st.success(f"✅ {approved_count} bon(nen) goedgekeurd!")
                    st.rerun()
                else:
                    st.warning("⚠️ Selecteer bonnen om goed te keuren")

        with col4:
            if st.button("📥 Downloaden", use_container_width=True, key="btn_download"):
                if len(selected_receipts) > 0:
                    # Create ZIP file with selected receipts
                    zip_buffer = create_zip_download(selected_receipts['ID'].tolist())
                    if zip_buffer:
                        st.download_button(
                            label="💾 Download ZIP",
                            data=zip_buffer,
                            file_name=f"bonnen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                else:
                    st.warning("⚠️ Selecteer bonnen om te downloaden")

        with col5:
            if st.button("💾 Exporteren", use_container_width=True, key="btn_export"):
                st.session_state['selected_page'] = "Export/Rapporten"
                st.rerun()

        # Handle delete confirmation
        if st.session_state.get('confirm_delete', False):
            st.warning("⚠️ Weet u zeker dat u de geselecteerde bonnen wilt verwijderen?")
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                if st.button("✅ Ja, verwijder", type="primary", key="confirm_yes"):
                    deleted_count = 0
                    for receipt_id in st.session_state.get('receipts_to_delete', []):
                        if delete_receipt(receipt_id):
                            deleted_count += 1
                    st.success(f"🗑️ {deleted_count} bon(nen) verwijderd!")
                    st.session_state['confirm_delete'] = False
                    st.session_state['receipts_to_delete'] = []
                    st.rerun()
            with col2:
                if st.button("❌ Annuleren", key="confirm_no"):
                    st.session_state['confirm_delete'] = False
                    st.session_state['receipts_to_delete'] = []
                    st.rerun()

        st.markdown("---")

        # Receipt detail view - auto-open if edit button was clicked
        show_detail = st.checkbox("🔍 Gedetailleerde weergave", value=st.session_state.get('show_detail_view', False))

        if show_detail:
            # If we have a pre-selected receipt from edit button
            if st.session_state.get('edit_receipt_id'):
                show_receipt_details(df, preselected_id=st.session_state.get('edit_receipt_id'))
                # Clear the preselection
                st.session_state['edit_receipt_id'] = None
                st.session_state['show_detail_view'] = False
            else:
                show_receipt_details(df)

    except Exception as e:
        logger.error(f"Error loading receipts: {e}")
        st.error(f"Fout bij laden van bonnen: {str(e)}")

def display_receipt_table(df):
    """Display receipt table with selection capability."""

    # Add checkbox column
    df_display = df.copy()
    df_display.insert(0, 'Selecteer', False)

    # Format columns for display
    df_display['Datum'] = pd.to_datetime(df_display['Datum']).dt.strftime('%d-%m-%Y')
    df_display['Bedrag excl. BTW'] = df_display['Bedrag excl. BTW'].apply(lambda x: f"€ {x:,.2f}")
    df_display['BTW bedrag'] = df_display['BTW bedrag'].apply(lambda x: f"€ {x:,.2f}")
    df_display['Totaal incl. BTW'] = df_display['Totaal incl. BTW'].apply(lambda x: f"€ {x:,.2f}")

    # Format status
    df_display['Status'] = df_display['Status'].apply(lambda x: {
        'completed': '✅ Verwerkt',
        'pending': '⏳ In behandeling',
        'processing': '🔄 Bezig...',
        'failed': '❌ Mislukt'
    }.get(x, x))

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
            "ID": st.column_config.NumberColumn(
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
            "Categorie": st.column_config.TextColumn(
                "Categorie",
                help="Expense categorie",
                width="medium",
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                help="Verwerkingsstatus",
                width="small",
            ),
            "Bestand": st.column_config.TextColumn(
                "Bestand",
                width="small",
            ),
        },
        disabled=["ID", "Datum", "Leverancier", "Categorie", "Bedrag excl. BTW", "BTW bedrag", "Totaal incl. BTW", "Status", "Bestand"],
    )

    # Get selected rows
    selected_rows = edited_df[edited_df['Selecteer'] == True]
    if len(selected_rows) > 0:
        st.info(f"✓ {len(selected_rows)} bon(nen) geselecteerd")

    return selected_rows

def show_receipt_details(df, preselected_id=None):
    """Show detailed view of selected receipt."""

    st.subheader("📄 Bon Details")

    # Select receipt to view
    default_index = 0
    if preselected_id and preselected_id in df['ID'].tolist():
        default_index = df['ID'].tolist().index(preselected_id)

    receipt_id = st.selectbox(
        "Selecteer bon voor details:",
        df['ID'].tolist(),
        index=default_index,
        format_func=lambda x: f"Bon #{x} - {df[df['ID'] == x]['Leverancier'].values[0]}"
    )

    if receipt_id:
        receipt_row = df[df['ID'] == receipt_id].iloc[0]

        # Get full receipt data from local storage
        try:
            receipt = get_receipt(receipt_id)

            if not receipt:
                st.error("Bon niet gevonden in local storage")
                return

            extracted = receipt.get('extracted_data', {})

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### 🖼️ Bon Afbeelding")

                # Show receipt image if available
                file_path = receipt.get('file_path')
                filename = receipt.get('filename')

                if file_path and Path(file_path).exists():
                    try:
                        st.image(file_path, use_container_width=True)
                    except Exception as e:
                        st.info(f"Kan afbeelding niet laden: {filename}")
                        st.text(f"Bestandspad: {file_path}")
                else:
                    st.info(f"Bon afbeelding niet beschikbaar\n\nBestand: {filename}")

                # Image controls
                col1a, col1b, col1c = st.columns(3)
                with col1a:
                    if st.button("🔍 Zoom", use_container_width=True, disabled=True):
                        st.info("Zoom functie komt binnenkort")
                with col1b:
                    if st.button("🔄 Roteren", use_container_width=True, disabled=True):
                        st.info("Rotatie functie komt binnenkort")
                with col1c:
                    if file_path and Path(file_path).exists():
                        with open(file_path, 'rb') as f:
                            st.download_button(
                                "📥 Download",
                                data=f.read(),
                                file_name=filename,
                                use_container_width=True
                            )

            with col2:
                st.markdown("### 📊 Geëxtraheerde Gegevens")

                if not extracted:
                    st.warning("⚠️ Deze bon is nog niet verwerkt of verwerking is mislukt")
                    if st.button("🔄 Opnieuw verwerken", type="primary"):
                        st.info("Herverwerking functie komt binnenkort")
                    return

                # Parse transaction date
                trans_date = extracted.get('transaction_date') or extracted.get('date')
                if isinstance(trans_date, str):
                    try:
                        trans_date = datetime.fromisoformat(trans_date).date()
                    except:
                        trans_date = datetime.now().date()
                elif trans_date is None:
                    trans_date = datetime.now().date()
                elif isinstance(trans_date, datetime):
                    trans_date = trans_date.date()

                # Editable fields
                edited_date = st.date_input(
                    "Datum",
                    value=trans_date,
                    format="DD/MM/YYYY"
                )

                edited_vendor = st.text_input(
                    "Leverancier",
                    value=extracted.get('vendor_name', '')
                )

                current_category = extracted.get('expense_category') or extracted.get('category', '')
                category_index = Config.EXPENSE_CATEGORIES.index(current_category) if current_category in Config.EXPENSE_CATEGORIES else 0

                edited_category = st.selectbox(
                    "Categorie",
                    Config.EXPENSE_CATEGORIES,
                    index=category_index
                )

                col2a, col2b = st.columns(2)
                with col2a:
                    edited_amount_excl = st.number_input(
                        "Bedrag excl. BTW (€)",
                        value=float(extracted.get('amount_excl_vat') or extracted.get('total_excl_vat', 0)),
                        step=0.01
                    )

                with col2b:
                    # Determine current VAT rate
                    vat_breakdown = extracted.get('vat_breakdown', {})
                    vat_6 = float(vat_breakdown.get('6', extracted.get('vat_6_amount', 0)))
                    vat_9 = float(vat_breakdown.get('9', extracted.get('vat_9_amount', 0)))
                    vat_21 = float(vat_breakdown.get('21', extracted.get('vat_21_amount', 0)))

                    current_vat_rate = 21
                    if vat_9 > 0:
                        current_vat_rate = 9
                    elif vat_6 > 0:
                        current_vat_rate = 6

                    edited_vat_rate = st.selectbox(
                        "BTW tarief (%)",
                        [0, 6, 9, 21],
                        index=[0, 6, 9, 21].index(current_vat_rate)
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
                        value=int(extracted.get('vat_deductible_percentage', 100)),
                        step=5
                    )

                with col2f:
                    ib_deductible = st.slider(
                        "IB aftrekbaar (%)",
                        min_value=0,
                        max_value=100,
                        value=int(extracted.get('ib_deductible_percentage', 100)),
                        step=5
                    )

                # Notes
                notes = st.text_area(
                    "Notities / Toelichting",
                    value=extracted.get('notes') or extracted.get('explanation', ''),
                    height=100
                )

                # Save button
                if st.button("💾 Wijzigingen Opslaan", use_container_width=True, type="primary"):
                    try:
                        # Update extracted data dictionary
                        updated_data = extracted.copy()
                        updated_data['transaction_date'] = edited_date.isoformat()
                        updated_data['date'] = edited_date.isoformat()
                        updated_data['vendor_name'] = edited_vendor
                        updated_data['expense_category'] = edited_category
                        updated_data['category'] = edited_category
                        updated_data['total_excl_vat'] = edited_amount_excl
                        updated_data['amount_excl_vat'] = edited_amount_excl
                        updated_data['total_incl_vat'] = total_amount
                        updated_data['total_amount'] = total_amount

                        # Update VAT amounts based on selected rate
                        updated_data['vat_breakdown'] = {
                            '6': vat_amount if edited_vat_rate == 6 else 0,
                            '9': vat_amount if edited_vat_rate == 9 else 0,
                            '21': vat_amount if edited_vat_rate == 21 else 0
                        }
                        updated_data['vat_6_amount'] = vat_amount if edited_vat_rate == 6 else 0
                        updated_data['vat_9_amount'] = vat_amount if edited_vat_rate == 9 else 0
                        updated_data['vat_21_amount'] = vat_amount if edited_vat_rate == 21 else 0

                        updated_data['vat_deductible_percentage'] = vat_deductible
                        updated_data['ib_deductible_percentage'] = ib_deductible
                        updated_data['notes'] = notes
                        updated_data['explanation'] = notes

                        # Calculate deductions
                        updated_data['vat_refund_amount'] = vat_amount * (vat_deductible / 100)
                        updated_data['vat_deductible_amount'] = vat_amount * (vat_deductible / 100)
                        updated_data['ib_deduction_amount'] = edited_amount_excl * (ib_deductible / 100)
                        updated_data['profit_deduction'] = edited_amount_excl * (ib_deductible / 100)

                        # Save to local storage
                        update_receipt_data(receipt_id, updated_data)

                        st.success("✅ Wijzigingen succesvol opgeslagen!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fout bij opslaan: {str(e)}")
                        logger.error(f"Error saving receipt changes: {e}")

                # Additional info
                st.markdown("---")
                st.markdown("#### 📝 Metadata")

                # Parse dates
                upload_date = receipt.get('upload_date', '')
                if isinstance(upload_date, str):
                    try:
                        upload_date = datetime.fromisoformat(upload_date).strftime('%d-%m-%Y %H:%M')
                    except:
                        upload_date = 'Onbekend'

                updated_at = receipt.get('updated_at', '')
                if isinstance(updated_at, str):
                    try:
                        updated_at = datetime.fromisoformat(updated_at).strftime('%d-%m-%Y %H:%M')
                    except:
                        updated_at = 'Onbekend'

                st.text(f"Upload datum: {upload_date}")
                st.text(f"Laatst gewijzigd: {updated_at}")
                st.text(f"Bestandsnaam: {receipt.get('filename', 'Onbekend')}")
                st.text(f"Status: {receipt.get('processing_status', 'Onbekend')}")

                error_msg = receipt.get('error_message')
                if error_msg:
                    st.error(f"Error: {error_msg}")

        except Exception as e:
            logger.error(f"Error loading receipt details: {e}")
            st.error(f"Fout bij laden van bon details: {str(e)}")

def create_zip_download(receipt_ids: list) -> io.BytesIO:
    """Create a ZIP file with selected receipts.

    Args:
        receipt_ids: List of receipt IDs to include

    Returns:
        BytesIO buffer containing ZIP file
    """
    try:
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for receipt_id in receipt_ids:
                receipt = get_receipt(receipt_id)
                if receipt:
                    file_path = receipt.get('file_path')
                    filename = receipt.get('filename')

                    if file_path and Path(file_path).exists():
                        # Add file to ZIP with original filename
                        zip_file.write(file_path, filename)
                    else:
                        logger.warning(f"File not found for receipt {receipt_id}: {file_path}")

        zip_buffer.seek(0)
        return zip_buffer

    except Exception as e:
        logger.error(f"Error creating ZIP file: {e}")
        st.error(f"Fout bij maken van ZIP bestand: {str(e)}")
        return None
