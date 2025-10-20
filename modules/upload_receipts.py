"""Receipt upload page with ACTUAL OCR+LLM processing."""

import streamlit as st
import os
import base64
import zipfile
from pathlib import Path
from datetime import datetime
import logging
from typing import List
from PIL import Image
import io
import time

from config import Config
from services.processing_pipeline import ReceiptProcessor
from utils.file_utils import validate_file, save_uploaded_file
from utils.database_utils_local import save_receipt_to_db
from utils.local_storage import save_receipt as save_to_json, update_receipt_data

logger = logging.getLogger(__name__)

def show_manual_extraction_form(receipt_id, filename, auto_extracted_data):
    """
    Show manual data entry form for receipts with low confidence.

    Args:
        receipt_id: Receipt ID in database
        filename: Original filename
        auto_extracted_data: Automatically extracted data (used as defaults)
    """
    st.markdown("---")
    st.markdown("### ✏️ Handmatige Gegevensinvoer")
    st.info("Vul de onderstaande velden in of corrigeer de automatisch geëxtraheerde gegevens.")

    with st.form(key=f"manual_form_{receipt_id}"):
        # General Information
        st.markdown("#### 📋 Algemene Informatie")
        col1, col2 = st.columns(2)

        with col1:
            vendor_name = st.text_input(
                "Leverancier/Winkel *",
                value=auto_extracted_data.get('vendor_name', ''),
                help="Naam van de winkel of leverancier"
            )
            transaction_date = st.date_input(
                "Datum *",
                value=datetime.strptime(auto_extracted_data.get('date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date() if auto_extracted_data.get('date') else datetime.now().date(),
                help="Datum van de transactie"
            )

        with col2:
            invoice_number = st.text_input(
                "Factuurnummer",
                value=auto_extracted_data.get('invoice_number', ''),
                help="Factuurnummer indien beschikbaar"
            )
            category = st.selectbox(
                "Categorie *",
                Config.EXPENSE_CATEGORIES,
                index=Config.EXPENSE_CATEGORIES.index(auto_extracted_data.get('category', Config.EXPENSE_CATEGORIES[0])) if auto_extracted_data.get('category') in Config.EXPENSE_CATEGORIES else 0,
                help="Selecteer de juiste categorie voor deze uitgave"
            )

        # Amounts
        st.markdown("#### 💶 Bedragen")
        col1, col2, col3 = st.columns(3)

        with col1:
            total_amount = st.number_input(
                "Totaal incl. BTW (€) *",
                min_value=0.0,
                value=float(auto_extracted_data.get('total_amount', 0)),
                step=0.01,
                format="%.2f",
                help="Totaalbedrag inclusief BTW"
            )

        with col2:
            vat_6 = st.number_input(
                "BTW 6% (€)",
                min_value=0.0,
                value=float(auto_extracted_data.get('vat_breakdown', {}).get('6', 0)),
                step=0.01,
                format="%.2f"
            )
            vat_9 = st.number_input(
                "BTW 9% (€)",
                min_value=0.0,
                value=float(auto_extracted_data.get('vat_breakdown', {}).get('9', 0)),
                step=0.01,
                format="%.2f"
            )

        with col3:
            vat_21 = st.number_input(
                "BTW 21% (€)",
                min_value=0.0,
                value=float(auto_extracted_data.get('vat_breakdown', {}).get('21', 0)),
                step=0.01,
                format="%.2f"
            )

        # Notes
        st.markdown("#### 📝 Opmerkingen")
        notes = st.text_area(
            "Toelichting/Motivatie",
            value=auto_extracted_data.get('notes', ''),
            help="Eventuele opmerkingen of toelichting bij deze uitgave",
            height=100
        )

        # Submit button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submit_button = st.form_submit_button("💾 Opslaan", use_container_width=True, type="primary")

        if submit_button:
            # Validate required fields
            if not vendor_name or not transaction_date or total_amount <= 0:
                st.error("❌ Vul alle verplichte velden (*) correct in!")
                return

            # Calculate amounts
            total_vat = vat_6 + vat_9 + vat_21
            amount_excl_vat = total_amount - total_vat

            # Get tax rules for category
            from services.llm_service import LLMService
            llm_service = LLMService()
            tax_percentages = llm_service._apply_tax_rules(category)

            # Calculate tax amounts
            vat_deductible = total_vat * (tax_percentages['vat_deductible_percentage'] / 100)
            remainder_after_vat = total_amount - vat_deductible
            profit_deduction = amount_excl_vat * (tax_percentages['ib_deductible_percentage'] / 100)

            # Create updated data dictionary
            updated_data = {
                'vendor_name': vendor_name,
                'date': transaction_date.strftime('%Y-%m-%d'),
                'invoice_number': invoice_number,
                'category': category,
                'total_amount': total_amount,
                'vat_breakdown': {
                    '6': vat_6,
                    '9': vat_9,
                    '21': vat_21
                },
                'amount_excl_vat': amount_excl_vat,
                'vat_deductible_percentage': tax_percentages['vat_deductible_percentage'],
                'ib_deductible_percentage': tax_percentages['ib_deductible_percentage'],
                'vat_deductible_amount': vat_deductible,
                'remainder_after_vat': remainder_after_vat,
                'profit_deduction': profit_deduction,
                'notes': notes,
                'confidence': 1.0,  # Manual entry = 100% confidence
                'manual_entry': True
            }

            # Update receipt in storage
            try:
                update_receipt_data(receipt_id, updated_data)
                st.success("✅ Gegevens succesvol opgeslagen!")
                st.balloons()

                # Clear the form from session state
                if f'show_manual_form_{receipt_id}' in st.session_state:
                    del st.session_state[f'show_manual_form_{receipt_id}']

                # Wait a moment and rerun to show updated data
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"❌ Fout bij opslaan: {str(e)}")
                logger.error(f"Error saving manual entry: {e}")

def show():
    """Display the receipt upload page."""

    st.title("📤 Bonnen Uploaden")
    st.markdown("Upload uw bonnen voor automatische verwerking met AI")

    # Instructions
    with st.expander("ℹ️ Instructies", expanded=False):
        st.markdown("""
        ### Hoe werkt het uploaden?

        1. **Digitale bonnen**: Upload PDF, PNG, JPG of JPEG bestanden
        2. **Meerdere bestanden**: Upload tot 50 bestanden tegelijk
        3. **ZIP bestanden**: Upload een ZIP met meerdere bonnen
        4. **Maximale grootte**: 10MB per bestand

        ### Tips voor beste resultaten:
        - Zorg voor duidelijke, leesbare bonnen
        - Bij foto's: goede belichting, geen schaduwen
        - Hele bon moet zichtbaar zijn
        - Vermijd wazige of scheve foto's
        """)

    st.markdown("---")

    # Upload method selection
    upload_method = st.radio(
        "Selecteer upload methode:",
        ["📁 Bestanden uploaden", "📦 ZIP bestand uploaden"],
        horizontal=True
    )

    if upload_method == "📁 Bestanden uploaden":
        show_file_upload()
    else:
        show_zip_upload()

def show_file_upload():
    """Show file upload interface."""

    st.subheader("📁 Bestanden Uploaden")

    # File uploader
    uploaded_files = st.file_uploader(
        "Sleep bestanden hierheen of klik om te browsen",
        type=Config.ALLOWED_EXTENSIONS,
        accept_multiple_files=True,
        help=f"Maximaal {Config.MAX_BATCH_SIZE} bestanden, {Config.MAX_UPLOAD_SIZE_MB}MB per bestand"
    )

    if uploaded_files:
        st.markdown(f"### 📋 Voorvertoning - {len(uploaded_files)} bestand(en) geselecteerd")

        # Check batch size limit
        if len(uploaded_files) > Config.MAX_BATCH_SIZE:
            st.error(f"⚠️ Maximaal {Config.MAX_BATCH_SIZE} bestanden tegelijk toegestaan")
            return

        # Preview section with tabs for each file
        tabs = st.tabs([f"📄 {file.name[:20]}..." if len(file.name) > 20 else f"📄 {file.name}" for file in uploaded_files[:5]])

        for idx, (tab, file) in enumerate(zip(tabs, uploaded_files[:5])):
            with tab:
                show_file_preview(file)

        if len(uploaded_files) > 5:
            st.info(f"ℹ️ En nog {len(uploaded_files) - 5} bestanden meer...")

        st.markdown("---")

        # Processing options
        col1, col2 = st.columns(2)

        with col1:
            auto_categorize = st.checkbox("Automatisch categoriseren", value=True)
            extract_items = st.checkbox("Individuele items extraheren", value=True)

        with col2:
            manual_review = st.checkbox("Handmatige review vereist", value=False)

        # Category override
        category_override = st.selectbox(
            "Categorie overschrijven (optioneel):",
            ["Automatisch"] + Config.EXPENSE_CATEGORIES,
            help="Selecteer een categorie om toe te passen op alle uploads"
        )

        st.markdown("---")

        # Process button
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            if st.button("🚀 Start Verwerking", use_container_width=True, type="primary"):
                process_uploads(
                    uploaded_files,
                    auto_categorize=auto_categorize,
                    extract_items=extract_items,
                    manual_review=manual_review,
                    category_override=None if category_override == "Automatisch" else category_override
                )

def show_zip_upload():
    """Show ZIP file upload interface."""

    st.subheader("📦 ZIP Bestand Uploaden")

    uploaded_zip = st.file_uploader(
        "Upload een ZIP bestand met bonnen",
        type=['zip'],
        help=f"Maximaal {Config.MAX_UPLOAD_SIZE_MB}MB"
    )

    if uploaded_zip:
        st.success(f"✅ ZIP bestand geselecteerd: {uploaded_zip.name}")

        # Extract and show contents
        try:
            with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                valid_files = [f for f in file_list if any(f.lower().endswith(ext) for ext in ['.pdf', '.png', '.jpg', '.jpeg'])]

                st.info(f"📊 Gevonden: {len(valid_files)} bonnen in ZIP bestand")

                with st.expander("📄 Bestanden in ZIP", expanded=True):
                    for file in valid_files[:10]:
                        st.text(f"• {file}")
                    if len(valid_files) > 10:
                        st.text(f"... en nog {len(valid_files) - 10} bestanden")

                st.markdown("---")

                # Processing options (same as file upload)
                col1, col2 = st.columns(2)

                with col1:
                    auto_categorize = st.checkbox("Automatisch categoriseren", value=True, key="zip_auto_categorize")
                    extract_items = st.checkbox("Individuele items extraheren", value=True, key="zip_extract_items")

                with col2:
                    manual_review = st.checkbox("Handmatige review vereist", value=False, key="zip_manual_review")

                # Category override
                category_override = st.selectbox(
                    "Categorie overschrijven (optioneel):",
                    ["Automatisch"] + Config.EXPENSE_CATEGORIES,
                    help="Selecteer een categorie om toe te passen op alle uploads",
                    key="zip_category_override"
                )

                st.markdown("---")

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("🚀 Start Verwerking", use_container_width=True, type="primary"):
                        process_zip_file(
                            uploaded_zip,
                            zip_ref,
                            valid_files,
                            auto_categorize=auto_categorize,
                            extract_items=extract_items,
                            manual_review=manual_review,
                            category_override=None if category_override == "Automatisch" else category_override
                        )

        except Exception as e:
            st.error(f"❌ Fout bij lezen ZIP bestand: {str(e)}")
            logger.error(f"ZIP error: {e}")

def show_file_preview(file):
    """Show preview of uploaded file."""

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**Bestand Informatie:**")
        st.text(f"Naam: {file.name}")
        st.text(f"Type: {file.type}")
        st.text(f"Grootte: {file.size / 1024:.1f} KB")

    with col2:
        if file.type.startswith('image'):
            try:
                image = Image.open(file)
                st.image(image, caption=file.name, use_column_width=True)
                file.seek(0)  # Reset file pointer
            except Exception as e:
                st.error(f"Kan afbeelding niet tonen: {e}")

        elif file.type == 'application/pdf':
            try:
                # Show PDF preview
                file_bytes = file.read()
                base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
                pdf_display = f'''
                    <iframe src="data:application/pdf;base64,{base64_pdf}"
                            width="100%" height="400" type="application/pdf">
                    </iframe>
                '''
                st.markdown(pdf_display, unsafe_allow_html=True)
                file.seek(0)  # Reset file pointer
            except Exception as e:
                st.warning(f"PDF preview niet beschikbaar: {e}")
                st.info("📄 PDF bestand - preview niet beschikbaar in browser")

def process_uploads(
    files: List,
    auto_categorize: bool = True,
    extract_items: bool = True,
    manual_review: bool = False,
    category_override: str = None
):
    """Process uploaded files with ACTUAL OCR and LLM."""

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    total_files = len(files)
    successful = 0
    failed = 0
    results = []

    # Show info for many files
    if total_files > 10:
        st.info(f"""
        ℹ️ **Let op:** U uploadt {total_files} bestanden.

        De bestanden worden één voor één verwerkt. Bij API-limieten wordt
        automatisch opnieuw geprobeerd met intelligente wachttijden.

        Laat dit venster open tijdens de verwerking.
        """)

    # Initialize services
    processor = ReceiptProcessor()

    for idx, file in enumerate(files):
        # Update progress
        progress = (idx + 1) / total_files
        progress_bar.progress(progress)

        status_text.text(f"Verwerken: {file.name} ({idx + 1}/{total_files})")

        try:
            # Validate file
            is_valid, error_msg = validate_file(file)
            if not is_valid:
                results.append({
                    'file': file.name,
                    'status': 'Mislukt',
                    'error': error_msg,
                    'data': None
                })
                failed += 1
                continue

            # Save file to disk
            file_path = save_uploaded_file(file)

            # Save receipt record to database
            receipt_id = save_receipt_to_db(
                file_path=str(file_path),
                original_filename=file.name,
                file_size=file.size,
                file_type=file.type
            )

            # Process with OCR + LLM pipeline
            result = processor.process_receipt(receipt_id, str(file_path))

            if result['success']:
                # Save to receipts_metadata.json in receipt_data/receipts/
                try:
                    update_receipt_data(receipt_id, result.get('data', {}))
                except Exception as e:
                    logger.error(f"Failed to save receipt to JSON: {e}")

                results.append({
                    'file': file.name,
                    'status': 'Succesvol',
                    'receipt_id': receipt_id,
                    'data': result.get('data', {}),
                    'raw_text': result.get('raw_text', ''),  # Step 1
                    'structured_data_json': result.get('structured_data_json', ''),  # Step 2
                    'extracted_category': result.get('extracted_category', ''),  # Step 3
                    'category': category_override or result['data'].get('category', 'Onbekend')
                })
                successful += 1
            else:
                results.append({
                    'file': file.name,
                    'status': 'Mislukt',
                    'error': result.get('error', 'Onbekende fout'),
                    'data': None
                })
                failed += 1

        except Exception as e:
            logger.error(f"Error processing file {file.name}: {e}")
            results.append({
                'file': file.name,
                'status': 'Mislukt',
                'error': str(e),
                'data': None
            })
            failed += 1

    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()

    # Show results
    display_processing_results(results, successful, failed, total_files, results_container)

def process_zip_file(
    uploaded_zip,
    zip_ref,
    valid_files,
    auto_categorize: bool = True,
    extract_items: bool = True,
    manual_review: bool = False,
    category_override: str = None
):
    """Process ZIP file with multiple receipts."""

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    # Extract ZIP to temp directory
    extract_path = Config.TEMP_FOLDER / f"extract_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    extract_path.mkdir(parents=True, exist_ok=True)

    total_files = len(valid_files)

    # Show info for many files
    if total_files > 10:
        st.info(f"""
        ℹ️ **Let op:** ZIP bevat {total_files} bestanden.

        De bestanden worden één voor één verwerkt. Bij API-limieten wordt
        automatisch opnieuw geprobeerd met intelligente wachttijden.

        Laat dit venster open tijdens de verwerking.
        """)

    try:
        zip_ref.extractall(extract_path)

        # Process each valid file
        processor = ReceiptProcessor()
        successful = 0
        failed = 0
        results = []

        for idx, file_name in enumerate(valid_files):
            progress = (idx + 1) / len(valid_files)
            progress_bar.progress(progress)

            status_text.text(f"Verwerken: {file_name} ({idx + 1}/{len(valid_files)})")

            try:
                file_path = extract_path / file_name

                # Get file info
                file_size = file_path.stat().st_size
                file_type = 'application/pdf' if file_name.lower().endswith('.pdf') else 'image/jpeg'

                # Save receipt record to database
                receipt_id = save_receipt_to_db(
                    file_path=str(file_path),
                    original_filename=file_name,
                    file_size=file_size,
                    file_type=file_type
                )

                # Process with OCR + LLM
                result = processor.process_receipt(receipt_id, str(file_path))

                if result['success']:
                    # Save to receipts_metadata.json in receipt_data/receipts/
                    try:
                        update_receipt_data(receipt_id, result.get('data', {}))
                    except Exception as e:
                        logger.error(f"Failed to save receipt to JSON: {e}")

                    results.append({
                        'file': file_name,
                        'status': 'Succesvol',
                        'receipt_id': receipt_id,
                        'data': result.get('data', {}),
                        'raw_text': result.get('raw_text', ''),  # Step 1
                        'structured_data_json': result.get('structured_data_json', ''),  # Step 2
                        'extracted_category': result.get('extracted_category', ''),  # Step 3
                        'category': category_override or result['data'].get('category', 'Onbekend')
                    })
                    successful += 1
                else:
                    results.append({
                        'file': file_name,
                        'status': 'Mislukt',
                        'error': result.get('error', 'Onbekende fout'),
                        'data': None
                    })
                    failed += 1

            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                results.append({
                    'file': file_name,
                    'status': 'Mislukt',
                    'error': str(e),
                    'data': None
                })
                failed += 1

        # Clear progress
        progress_bar.empty()
        status_text.empty()

        # Show results
        display_processing_results(results, successful, failed, len(valid_files), results_container)

    except Exception as e:
        st.error(f"❌ Fout bij verwerken ZIP: {str(e)}")
        logger.error(f"ZIP processing error: {e}")

def display_processing_results(results, successful, failed, total_files, container):
    """Display processing results with extracted data."""

    with container:
        st.markdown("### 📊 Verwerkingsresultaten")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.success(f"✅ Succesvol: {successful}")
        with col2:
            if failed > 0:
                st.error(f"❌ Mislukt: {failed}")
            else:
                st.info(f"❌ Mislukt: {failed}")
        with col3:
            st.info(f"📁 Totaal: {total_files}")

        st.markdown("---")

        # Show detailed results for each file
        for idx, result in enumerate(results):
            with st.expander(
                f"{'✅' if result['status'] == 'Succesvol' else '❌'} {result['file']}",
                expanded=(result['status'] == 'Succesvol' and idx < 3)  # Expand first 3 successful
            ):
                if result['status'] == 'Succesvol' and result.get('data'):
                    data = result['data']

                    # Show RAW TEXT first (Step 1)
                    if result.get('raw_text'):
                        with st.expander("📄 Ruwe Tekst (Raw Text) - Step 1", expanded=False):
                            st.text_area(
                                "Geëxtraheerde tekst van bon:",
                                value=result['raw_text'],
                                height=200,
                                disabled=True
                            )

                    # Show STRUCTURED DATA (Step 2)
                    if result.get('structured_data_json'):
                        with st.expander("📋 Gestructureerde Data (Structured Data) - Step 2", expanded=False):
                            st.code(result['structured_data_json'], language='json')

                    # Show EXTRACTED CATEGORY (Step 3)
                    if result.get('extracted_category'):
                        with st.expander("🏷️ Geëxtraheerde Categorie (Extracted Category) - Step 3", expanded=False):
                            st.info(f"**Categorie:** {result['extracted_category']}")

                    # Display extracted information
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown("**📋 Algemene Informatie**")
                        st.write(f"**Leverancier:** {data.get('vendor_name', 'N/A')}")
                        st.write(f"**Datum:** {data.get('date', 'N/A')}")
                        st.write(f"**Factuur nr:** {data.get('invoice_number', 'N/A')}")
                        st.write(f"**Categorie:** {data.get('category', 'N/A')}")

                    with col2:
                        st.markdown("**💶 Bedragen**")
                        st.write(f"**Excl. BTW:** € {data.get('amount_excl_vat', 0):.2f}")
                        st.write(f"**BTW 6%:** € {data.get('vat_breakdown', {}).get('6', 0):.2f}")
                        st.write(f"**BTW 9%:** € {data.get('vat_breakdown', {}).get('9', 0):.2f}")
                        st.write(f"**BTW 21%:** € {data.get('vat_breakdown', {}).get('21', 0):.2f}")
                        st.write(f"**Totaal incl. BTW:** € {data.get('total_amount', 0):.2f}")

                    with col3:
                        st.markdown("**📊 Aftrekposten**")
                        st.write(f"**BTW aftrekbaar:** {data.get('vat_deductible_percentage', 0)}%")
                        st.write(f"**IB aftrekbaar:** {data.get('ib_deductible_percentage', 0)}%")
                        st.write(f"**BTW terugvraag:** € {data.get('vat_deductible_amount', 0):.2f}")
                        st.write(f"**Winstaftrek:** € {data.get('profit_deduction', 0):.2f}")

                    # Show confidence
                    confidence = data.get('confidence', 0)
                    if confidence < 0.7:
                        st.warning(f"⚠️ Lage betrouwbaarheid: {confidence:.0%} - Handmatige review aanbevolen")

                        # Offer manual extraction option
                        if st.button(f"✏️ Handmatig invoeren", key=f"manual_extract_{result.get('receipt_id', idx)}", use_container_width=True):
                            st.session_state[f'show_manual_form_{result.get("receipt_id", idx)}'] = True

                        # Show manual extraction form if button was clicked
                        if st.session_state.get(f'show_manual_form_{result.get("receipt_id", idx)}', False):
                            show_manual_extraction_form(result.get('receipt_id'), result['file'], data)
                    else:
                        st.success(f"✓ Betrouwbaarheid: {confidence:.0%}")

                else:
                    st.error(f"**Fout:** {result.get('error', 'Onbekende fout')}")

        st.markdown("---")

        # Action buttons
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📋 Naar Bonnen Beheer", use_container_width=True, key="nav_to_bonnen_beheer"):
                st.session_state['selected_page'] = "Bonnen Beheer"

        with col2:
            if st.button("🆕 Meer Uploaden", use_container_width=True, key="upload_more"):
                st.rerun()
