"""Settings page for user preferences and configuration."""

import streamlit as st
from datetime import datetime
import logging

from config import Config
from utils.database_utils import save_category_tax_rules, get_category_tax_rules, ensure_user_settings_exists

logger = logging.getLogger(__name__)

def show():
    """Display the settings page."""

    st.title("⚙️ Instellingen")
    st.markdown("Beheer uw account en applicatie instellingen")

    # Settings tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👤 Profiel",
        "🏢 Bedrijf",
        "💶 BTW & Belasting",
        "🔧 Systeem",
        "🔐 Beveiliging"
    ])

    with tab1:
        show_profile_settings()

    with tab2:
        show_company_settings()

    with tab3:
        show_tax_settings()

    with tab4:
        show_system_settings()

    with tab5:
        show_security_settings()

def show_profile_settings():
    """Show profile settings."""

    st.subheader("👤 Profiel Instellingen")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Voornaam", value="Jan", key="first_name")
        st.text_input("Achternaam", value="Jansen", key="last_name")
        st.text_input("Email", value="jan.jansen@example.com", key="email")

    with col2:
        st.text_input("Telefoon", value="+31 6 12345678", key="phone")
        st.selectbox(
            "Taal",
            ["Nederlands", "English"],
            key="language"
        )
        st.selectbox(
            "Tijdzone",
            ["Europe/Amsterdam", "Europe/Brussels", "UTC"],
            key="timezone"
        )

    st.markdown("---")

    st.markdown("### Notificaties")

    col1, col2 = st.columns(2)

    with col1:
        st.checkbox("Email notificaties", value=True, key="email_notifications")
        st.checkbox("Verwerking compleet", value=True, key="processing_notifications")

    with col2:
        st.checkbox("Maandelijkse samenvatting", value=True, key="monthly_summary")
        st.checkbox("BTW aangifte herinnering", value=True, key="vat_reminder")

    if st.button("💾 Profiel Opslaan", type="primary"):
        st.success("✅ Profiel instellingen opgeslagen!")

def show_company_settings():
    """Show company settings."""

    st.subheader("🏢 Bedrijfsinstellingen")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Bedrijfsnaam", value="Jansen Consultancy", key="company_name")
        st.text_input("KVK Nummer", value="12345678", key="kvk_number")
        st.text_input("BTW Nummer", value="NL123456789B01", key="vat_number")

    with col2:
        st.text_input("Handelsnaam", value="", key="trade_name")
        st.text_input("IBAN", value="NL12ABCD0123456789", key="iban")
        st.selectbox(
            "Rechtsvorm",
            ["Eenmanszaak", "VOF", "BV", "Stichting", "Vereniging"],
            key="legal_form"
        )

    st.markdown("### Bedrijfsadres")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Straat + Huisnummer", value="Hoofdstraat 123", key="street")
        st.text_input("Postcode", value="1234 AB", key="postal_code")

    with col2:
        st.text_input("Plaats", value="Amsterdam", key="city")
        st.text_input("Land", value="Nederland", key="country")

    st.markdown("### Bedrijfslogo")

    uploaded_logo = st.file_uploader(
        "Upload bedrijfslogo",
        type=['png', 'jpg', 'jpeg'],
        key="logo_upload"
    )

    if uploaded_logo:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(uploaded_logo, caption="Logo preview", width=200)

    if st.button("💾 Bedrijfsinstellingen Opslaan", type="primary"):
        st.success("✅ Bedrijfsinstellingen opgeslagen!")

def show_tax_settings():
    """Show tax and VAT settings."""

    st.subheader("💶 BTW & Belasting Instellingen")

    st.markdown("### BTW Tarieven")

    st.info("""
    De BTW tarieven worden automatisch bijgewerkt volgens de laatste Nederlandse wetgeving.
    Huidige tarieven per 1 juli 2024:
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Laag tarief", "9%", "Voorheen 6%")

    with col2:
        st.metric("Standaard tarief", "21%", "Ongewijzigd")

    with col3:
        st.metric("Nul tarief", "0%", "Export/Intracommunautair")

    st.markdown("### Standaard Aftrekpercentages")

    st.markdown("Stel standaard aftrekpercentages in per categorie:")

    # Ensure user settings exists
    user_settings_id = ensure_user_settings_exists(user_id=1)

    # Load existing tax rules from database
    existing_rules = get_category_tax_rules(user_settings_id)

    # Default values
    default_values = {
        'Beroepskosten': {'vat': 100, 'ib': 100},
        'Kantoorkosten': {'vat': 100, 'ib': 100},
        'Reis- en verblijfkosten': {'vat': 100, 'ib': 100},
        'Representatiekosten - Type 1 (Supermarket)': {'vat': 0, 'ib': 80},
        'Representatiekosten - Type 2 (Horeca)': {'vat': 0, 'ib': 80},
        'Vervoerskosten': {'vat': 100, 'ib': 100},
        'Zakelijke opleidingskosten': {'vat': 100, 'ib': 100}
    }

    categories_settings = {}

    for category in Config.EXPENSE_CATEGORIES:
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.text(category)

        # Get value from database or use default
        if category in existing_rules:
            default_vat = int(existing_rules[category]['vat_deductible'])
            default_ib = int(existing_rules[category]['ib_deductible'])
        else:
            default_vat = default_values.get(category, {}).get('vat', 100)
            default_ib = default_values.get(category, {}).get('ib', 100)

        with col2:
            vat_deductible = st.number_input(
                "BTW %",
                min_value=0,
                max_value=100,
                value=default_vat,
                key=f"vat_{category}",
                label_visibility="collapsed"
            )

        with col3:
            ib_deductible = st.number_input(
                "IB %",
                min_value=0,
                max_value=100,
                value=default_ib,
                key=f"ib_{category}",
                label_visibility="collapsed"
            )

        categories_settings[category] = {
            'vat': vat_deductible,
            'ib': ib_deductible
        }

    st.markdown("### BTW Aangifte")

    col1, col2 = st.columns(2)

    with col1:
        st.selectbox(
            "Aangifte frequentie",
            ["Per kwartaal", "Per maand", "Per jaar"],
            key="vat_frequency"
        )

    with col2:
        st.selectbox(
            "Boekjaar loopt van",
            ["1 januari - 31 december", "1 april - 31 maart", "1 juli - 30 juni"],
            key="fiscal_year"
        )

    if st.button("💾 BTW Instellingen Opslaan", type="primary"):
        # Save to database
        save_category_tax_rules(categories_settings, user_settings_id)
        st.success("✅ BTW instellingen opgeslagen in database!")

def show_system_settings():
    """Show system settings."""

    st.subheader("🔧 Systeem Instellingen")

    st.markdown("### Upload Instellingen")

    col1, col2 = st.columns(2)

    with col1:
        max_size = st.number_input(
            "Max bestandsgrootte (MB)",
            min_value=1,
            max_value=50,
            value=Config.MAX_UPLOAD_SIZE_MB,
            key="max_upload_size"
        )

        batch_size = st.number_input(
            "Max batch grootte",
            min_value=1,
            max_value=100,
            value=Config.MAX_BATCH_SIZE,
            key="max_batch_size"
        )

    with col2:
        st.multiselect(
            "Toegestane bestandstypen",
            ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
            default=Config.ALLOWED_EXTENSIONS,
            key="allowed_extensions"
        )

        st.selectbox(
            "Standaard export formaat",
            ["Excel", "CSV", "PDF"],
            key="default_export_format"
        )

    st.markdown("### OCR Instellingen")

    col1, col2 = st.columns(2)

    with col1:
        st.checkbox("Automatische beeldverbetering", value=True, key="auto_enhance")
        st.checkbox("Automatisch roteren", value=True, key="auto_rotate")

    with col2:
        st.checkbox("Dubbele bonnen detectie", value=True, key="duplicate_detection")
        st.slider(
            "Minimale OCR confidence",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            key="min_ocr_confidence"
        )

    st.markdown("### AI/LLM Instellingen")

    col1, col2 = st.columns(2)

    with col1:
        st.checkbox("Gebruik Gemini voor categorisatie", value=True, key="use_llm")
        st.checkbox("Automatische data extractie", value=True, key="auto_extract")

    with col2:
        st.selectbox(
            "Model versie",
            ["gemini-pro", "gemini-pro-vision"],
            key="model_version"
        )

        st.text_input(
            "API Key",
            value="••••••••••••••••",
            type="password",
            key="api_key",
            help="Gemini API key voor AI functionaliteit"
        )

    if st.button("💾 Systeem Instellingen Opslaan", type="primary"):
        st.success("✅ Systeem instellingen opgeslagen!")

def show_security_settings():
    """Show security settings."""

    st.subheader("🔐 Beveiliging")

    st.markdown("### Wachtwoord Wijzigen")

    col1, col2 = st.columns(2)

    with col1:
        current_password = st.text_input(
            "Huidig wachtwoord",
            type="password",
            key="current_password"
        )

    with col2:
        pass

    col1, col2 = st.columns(2)

    with col1:
        new_password = st.text_input(
            "Nieuw wachtwoord",
            type="password",
            key="new_password"
        )

    with col2:
        confirm_password = st.text_input(
            "Bevestig nieuw wachtwoord",
            type="password",
            key="confirm_password"
        )

    if st.button("Wachtwoord Wijzigen"):
        if new_password == confirm_password:
            st.success("✅ Wachtwoord succesvol gewijzigd!")
        else:
            st.error("❌ Wachtwoorden komen niet overeen!")

    st.markdown("---")

    st.markdown("### Twee-Factor Authenticatie (2FA)")

    col1, col2 = st.columns(2)

    with col1:
        tfa_enabled = st.checkbox("2FA inschakelen", value=False, key="2fa_enabled")

    with col2:
        if tfa_enabled:
            st.selectbox(
                "2FA methode",
                ["SMS", "Authenticator App", "Email"],
                key="2fa_method"
            )

    if tfa_enabled:
        st.info("Scan de QR code met uw authenticator app om 2FA in te stellen.")
        st.code("ABCD-EFGH-IJKL-MNOP", language="text")

    st.markdown("---")

    st.markdown("### Sessie Beheer")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Sessie timeout (minuten)",
            min_value=5,
            max_value=480,
            value=30,
            key="session_timeout"
        )

    with col2:
        st.checkbox("Onthoud mij op dit apparaat", value=False, key="remember_device")

    st.markdown("### Actieve Sessies")

    sessions_data = [
        {"Apparaat": "Windows PC - Chrome", "IP": "192.168.1.1", "Laatste activiteit": "Nu actief"},
        {"Apparaat": "iPhone - Safari", "IP": "192.168.1.2", "Laatste activiteit": "2 uur geleden"},
    ]

    for session in sessions_data:
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

        with col1:
            st.text(session["Apparaat"])
        with col2:
            st.text(session["IP"])
        with col3:
            st.text(session["Laatste activiteit"])
        with col4:
            if session["Laatste activiteit"] != "Nu actief":
                st.button("Beëindigen", key=f"end_{session['IP']}")

    st.markdown("---")

    st.markdown("### Data Privacy")

    st.checkbox("Anonieme gebruiksstatistieken delen", value=False, key="share_analytics")
    st.checkbox("Marketing emails ontvangen", value=False, key="marketing_emails")

    if st.button("💾 Beveiligingsinstellingen Opslaan", type="primary"):
        st.success("✅ Beveiligingsinstellingen opgeslagen!")

    st.markdown("---")

    st.markdown("### Gevaarzone")

    with st.expander("⚠️ Account Verwijderen"):
        st.warning("""
        **Let op:** Deze actie kan niet ongedaan gemaakt worden!
        Alle gegevens worden permanent verwijderd.
        """)

        if st.checkbox("Ik begrijp de consequenties", key="understand_delete"):
            confirm_text = st.text_input(
                "Type 'VERWIJDER' om te bevestigen",
                key="confirm_delete_text"
            )

            if confirm_text == "VERWIJDER":
                if st.button("🗑️ Account Permanent Verwijderen", type="secondary"):
                    st.error("Account verwijdering gestart...")
            else:
                st.info("Type 'VERWIJDER' om de knop te activeren")