"""Authentication utilities for user management."""

import streamlit as st
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

from database.models import User
from database.connection import get_db
from utils.session_state import set_user_info, logout

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def authenticate_user(email: str, password: str) -> Optional[Dict]:
    """
    Authenticate user with email and password.

    Args:
        email: User email
        password: Plain text password

    Returns:
        User data if authenticated, None otherwise
    """
    try:
        db = next(get_db())

        user = db.query(User).filter(User.email == email).first()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'name': user.full_name,
            'company': user.company_name,
            'username': user.username
        }

    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None

def check_authentication() -> bool:
    """Check if user is authenticated."""
    return st.session_state.get('authenticated', False)

def login_page():
    """Display login page."""

    st.title("🔐 Inloggen")
    st.markdown("Welkom bij de Administratie Automatisering App")

    # Login form
    with st.form("login_form"):
        st.markdown("### Inloggegevens")

        email = st.text_input(
            "Email",
            placeholder="uw.email@bedrijf.nl",
            help="Voer uw geregistreerde email adres in"
        )

        password = st.text_input(
            "Wachtwoord",
            type="password",
            placeholder="••••••••",
            help="Voer uw wachtwoord in"
        )

        col1, col2 = st.columns(2)

        with col1:
            remember = st.checkbox("Onthoud mij", value=False)

        with col2:
            submitted = st.form_submit_button(
                "Inloggen",
                use_container_width=True,
                type="primary"
            )

        if submitted:
            if not email or not password:
                st.error("Vul alle velden in")
            else:
                # For demo, use hardcoded credentials
                if email == "demo@example.com" and password == "demo":
                    user_data = {
                        'id': 1,
                        'email': email,
                        'name': 'Demo User',
                        'company': 'Demo Company BV'
                    }
                    set_user_info(user_data)
                    st.success("✅ Succesvol ingelogd!")
                    st.rerun()
                else:
                    # Try actual authentication
                    user_data = authenticate_user(email, password)
                    if user_data:
                        set_user_info(user_data)
                        st.success("✅ Succesvol ingelogd!")
                        st.rerun()
                    else:
                        st.error("❌ Ongeldige inloggegevens")

    # Demo credentials info
    with st.expander("ℹ️ Demo Toegang"):
        st.info("""
        **Voor demo doeleinden kunt u inloggen met:**

        Email: `demo@example.com`
        Wachtwoord: `demo`
        """)

    st.markdown("---")

    # Additional options
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔑 Wachtwoord vergeten?", use_container_width=True):
            show_password_reset()

    with col2:
        if st.button("📝 Registreren", use_container_width=True):
            show_registration()

    with col3:
        if st.button("❓ Hulp", use_container_width=True):
            show_login_help()

def show_password_reset():
    """Show password reset dialog."""
    st.markdown("### Wachtwoord Resetten")

    email = st.text_input(
        "Voer uw email adres in",
        placeholder="uw.email@bedrijf.nl"
    )

    if st.button("Reset link versturen"):
        if email:
            st.success(f"✅ Reset link verstuurd naar {email}")
            st.info("Controleer uw email voor verdere instructies")
        else:
            st.error("Voer een geldig email adres in")

def show_registration():
    """Show registration form."""
    st.markdown("### Nieuwe Account Aanmaken")

    with st.form("registration_form"):
        col1, col2 = st.columns(2)

        with col1:
            first_name = st.text_input("Voornaam")
            last_name = st.text_input("Achternaam")
            email = st.text_input("Email")

        with col2:
            company_name = st.text_input("Bedrijfsnaam")
            kvk_number = st.text_input("KVK Nummer")
            phone = st.text_input("Telefoon")

        password = st.text_input("Wachtwoord", type="password")
        confirm_password = st.text_input("Bevestig wachtwoord", type="password")

        terms = st.checkbox(
            "Ik ga akkoord met de algemene voorwaarden en privacy policy"
        )

        if st.form_submit_button("Registreren", type="primary"):
            if password != confirm_password:
                st.error("Wachtwoorden komen niet overeen")
            elif not terms:
                st.error("U moet akkoord gaan met de voorwaarden")
            else:
                st.success("✅ Account succesvol aangemaakt!")
                st.info("U kunt nu inloggen met uw email en wachtwoord")

def show_login_help():
    """Show login help information."""
    st.markdown("### Hulp bij Inloggen")

    st.markdown("""
    #### Veelgestelde vragen:

    **Ik ben mijn wachtwoord vergeten**
    - Klik op 'Wachtwoord vergeten?' om een reset link te ontvangen

    **Ik heb geen account**
    - Klik op 'Registreren' om een nieuw account aan te maken

    **Mijn account is geblokkeerd**
    - Neem contact op met support@example.com

    **Ik krijg een foutmelding**
    - Controleer of uw email en wachtwoord correct zijn
    - Probeer het opnieuw na enkele minuten

    #### Contact Support:
    - Email: support@example.com
    - Telefoon: +31 20 123 4567
    - Chat: Beschikbaar ma-vr 9:00-17:00
    """)

def create_user(
    email: str,
    password: str,
    full_name: str,
    company_name: str = None,
    kvk_number: str = None,
    btw_number: str = None
) -> Optional[int]:
    """
    Create a new user.

    Args:
        Various user parameters

    Returns:
        User ID if successful, None otherwise
    """
    try:
        db = next(get_db())

        # Check if user exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.warning(f"User with email {email} already exists")
            return None

        # Create new user
        user = User(
            email=email,
            username=email.split('@')[0],
            hashed_password=get_password_hash(password),
            full_name=full_name,
            company_name=company_name,
            kvk_number=kvk_number,
            btw_number=btw_number,
            is_active=True
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"User created: {user.id}")
        return user.id

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        db.rollback()
        return None

def update_user_password(user_id: int, new_password: str) -> bool:
    """
    Update user password.

    Args:
        user_id: User ID
        new_password: New password

    Returns:
        True if successful
    """
    try:
        db = next(get_db())

        user = db.query(User).filter(User.id == user_id).first()

        if user:
            user.hashed_password = get_password_hash(new_password)
            user.updated_at = datetime.now()
            db.commit()
            logger.info(f"Password updated for user {user_id}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error updating password: {e}")
        db.rollback()
        return False

def deactivate_user(user_id: int) -> bool:
    """
    Deactivate a user account.

    Args:
        user_id: User ID

    Returns:
        True if successful
    """
    try:
        db = next(get_db())

        user = db.query(User).filter(User.id == user_id).first()

        if user:
            user.is_active = False
            user.updated_at = datetime.now()
            db.commit()
            logger.info(f"User {user_id} deactivated")
            return True

        return False

    except Exception as e:
        logger.error(f"Error deactivating user: {e}")
        db.rollback()
        return False