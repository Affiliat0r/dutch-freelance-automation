"""Receipt upload page with batch processing capabilities."""

import streamlit as st
import os
from pathlib import Path
from datetime import datetime
import hashlib
import logging
from typing import List, Tuple
from PIL import Image
import io

from config import Config
from services.ocr_service import OCRService
from services.processing_pipeline import ReceiptProcessor
from utils.file_utils import validate_file, save_uploaded_file
from utils.database_utils import save_receipt_to_db

logger = logging.getLogger(__name__)

def show():
    """Display the receipt upload page."""

    st.title("📤 Bonnen Uploaden")
    st.markdown("Upload uw bonnen voor automatische verwerking")

    # Instructions
    with st.expander("ℹ️ Instructies", expanded=False):
        st.markdown("""
        ### Hoe werkt het uploaden?

        1. **Digitale bonnen**: Upload PDF, PNG, JPG of JPEG bestanden
        2. **Fysieke bonnen**: Maak een foto met uw camera
        3. **Batch upload**: Upload tot 50 bestanden tegelijk
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
        ["📁 Bestanden uploaden", "📸 Foto maken"],
        horizontal=True
    )

    if upload_method == "📁 Bestanden uploaden":
        show_file_upload()
    else:
        show_camera_capture()

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
        st.markdown(f"### 📋 {len(uploaded_files)} bestand(en) geselecteerd")

        # Check batch size limit
        if len(uploaded_files) > Config.MAX_BATCH_SIZE:
            st.error(f"⚠️ Maximaal {Config.MAX_BATCH_SIZE} bestanden tegelijk toegestaan")
            return

        # Preview section
        preview_container = st.container()
        with preview_container:
            st.markdown("#### Voorvertoning")

            # Create columns for preview
            cols = st.columns(min(3, len(uploaded_files)))

            for idx, file in enumerate(uploaded_files[:3]):  # Show max 3 previews
                with cols[idx]:
                    if file.type.startswith('image'):
                        image = Image.open(file)
                        st.image(image, caption=file.name, use_column_width=True)
                    else:
                        st.info(f"📄 {file.name}\n\n{file.type}\n\n{file.size / 1024:.1f} KB")

            if len(uploaded_files) > 3:
                st.caption(f"... en {len(uploaded_files) - 3} meer bestanden")

        st.markdown("---")

        # Processing options
        col1, col2 = st.columns(2)

        with col1:
            auto_categorize = st.checkbox("Automatisch categoriseren", value=True)
            extract_items = st.checkbox("Individuele items extraheren", value=True)

        with col2:
            manual_review = st.checkbox("Handmatige review vereist", value=False)
            send_notification = st.checkbox("Email notificatie na verwerking", value=False)

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

def show_camera_capture():
    """Show camera capture interface."""

    st.subheader("📸 Foto Maken")

    # Camera input
    camera_photo = st.camera_input(
        "Maak een foto van uw bon",
        help="Zorg voor goede belichting en een scherpe foto"
    )

    if camera_photo:
        st.markdown("### Voorvertoning")

        # Display the captured image
        image = Image.open(camera_photo)

        col1, col2 = st.columns(2)

        with col1:
            st.image(image, caption="Originele foto", use_column_width=True)

        with col2:
            # Image enhancement options
            st.markdown("#### Beeldverbetering")

            auto_enhance = st.checkbox("Automatisch verbeteren", value=True)
            auto_crop = st.checkbox("Automatisch bijsnijden", value=True)
            convert_bw = st.checkbox("Zwart-wit conversie", value=False)

            if st.button("Toepassen", use_container_width=True):
                # Apply enhancements (placeholder)
                enhanced_image = enhance_image(image, auto_enhance, auto_crop, convert_bw)
                st.image(enhanced_image, caption="Verbeterde foto", use_column_width=True)

        st.markdown("---")

        # Processing options
        col1, col2 = st.columns(2)

        with col1:
            receipt_date = st.date_input(
                "Bon datum (optioneel):",
                format="DD/MM/YYYY",
                help="Laat leeg voor automatische detectie"
            )

        with col2:
            vendor_name = st.text_input(
                "Leverancier (optioneel):",
                help="Laat leeg voor automatische detectie"
            )

        # Process button
        if st.button("🚀 Verwerk Foto", use_container_width=True, type="primary"):
            process_camera_photo(
                camera_photo,
                receipt_date=receipt_date,
                vendor_name=vendor_name
            )

def process_uploads(
    files: List,
    auto_categorize: bool = True,
    extract_items: bool = True,
    manual_review: bool = False,
    category_override: str = None
):
    """Process uploaded files."""

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    total_files = len(files)
    successful = 0
    failed = 0
    results = []

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
                    'error': error_msg
                })
                failed += 1
                continue

            # Save file
            file_path = save_uploaded_file(file)

            # Process with OCR (placeholder for actual implementation)
            # ocr_result = OCRService.process_receipt(file_path)

            # Save to database (placeholder)
            # receipt_id = save_receipt_to_db(file_path, ocr_result)

            results.append({
                'file': file.name,
                'status': 'Succesvol',
                'receipt_id': f"R{datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}",
                'category': category_override or 'Auto-gecategoriseerd'
            })
            successful += 1

        except Exception as e:
            logger.error(f"Error processing file {file.name}: {e}")
            results.append({
                'file': file.name,
                'status': 'Mislukt',
                'error': str(e)
            })
            failed += 1

    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()

    # Show results
    with results_container:
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

        # Detailed results table
        if results:
            import pandas as pd

            df_results = pd.DataFrame(results)

            # Style the dataframe
            def style_status(val):
                if val == 'Succesvol':
                    return 'background-color: #d4edda'
                else:
                    return 'background-color: #f8d7da'

            styled_df = df_results.style.applymap(
                style_status,
                subset=['status'] if 'status' in df_results.columns else []
            )

            st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Action buttons
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📋 Naar Bonnen Beheer", use_container_width=True):
                st.switch_page("pages/receipt_management.py")

        with col2:
            if st.button("🆕 Meer Uploaden", use_container_width=True):
                st.rerun()

        with col3:
            if successful > 0:
                if st.button("💾 Export Resultaten", use_container_width=True):
                    # Export results to CSV
                    df_results.to_csv('processing_results.csv', index=False)
                    st.success("Resultaten geëxporteerd naar processing_results.csv")

def process_camera_photo(
    photo,
    receipt_date=None,
    vendor_name=None
):
    """Process photo from camera."""

    with st.spinner("Foto wordt verwerkt..."):
        try:
            # Convert camera input to image
            image = Image.open(photo)

            # Save temporarily
            temp_path = Path(Config.TEMP_FOLDER) / f"camera_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            image.save(temp_path)

            # Process with OCR (placeholder)
            st.success("✅ Foto succesvol verwerkt!")

            # Show extracted data (placeholder)
            st.markdown("### Geëxtraheerde gegevens")

            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Datum", value=receipt_date or "01-12-2024")
                st.text_input("Leverancier", value=vendor_name or "Albert Heijn")
                st.selectbox("Categorie", Config.EXPENSE_CATEGORIES)

            with col2:
                st.number_input("Bedrag excl. BTW", value=41.32)
                st.number_input("BTW 21%", value=8.68)
                st.number_input("Totaal incl. BTW", value=50.00)

            if st.button("💾 Opslaan", use_container_width=True, type="primary"):
                st.success("Bon opgeslagen!")
                st.balloons()

        except Exception as e:
            st.error(f"Fout bij verwerken foto: {e}")
            logger.error(f"Camera photo processing error: {e}")

def enhance_image(image, auto_enhance, auto_crop, convert_bw):
    """Apply image enhancements (placeholder implementation)."""
    # This is a placeholder - actual implementation would use
    # OpenCV or similar for real image processing
    return image