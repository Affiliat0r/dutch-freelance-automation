"""Session state management for Streamlit app."""

import streamlit as st
from datetime import datetime
from typing import Any, Dict

def init_session_state():
    """Initialize session state variables."""

    # User session
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

    if 'user_email' not in st.session_state:
        st.session_state.user_email = None

    if 'user_name' not in st.session_state:
        st.session_state.user_name = "Demo User"

    if 'company_name' not in st.session_state:
        st.session_state.company_name = "Demo Company"

    # Upload session
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []

    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}

    if 'current_batch_id' not in st.session_state:
        st.session_state.current_batch_id = None

    # Filters and selections
    if 'date_range' not in st.session_state:
        st.session_state.date_range = {
            'start': None,
            'end': None
        }

    if 'selected_categories' not in st.session_state:
        st.session_state.selected_categories = []

    if 'selected_receipts' not in st.session_state:
        st.session_state.selected_receipts = []

    # Analytics cache
    if 'analytics_cache' not in st.session_state:
        st.session_state.analytics_cache = {}

    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()

    # Settings
    if 'user_settings' not in st.session_state:
        st.session_state.user_settings = {
            'language': 'nl',
            'timezone': 'Europe/Amsterdam',
            'date_format': 'DD-MM-YYYY',
            'currency': 'EUR',
            'auto_categorize': True,
            'auto_extract': True,
            'email_notifications': True
        }

    # Temporary data
    if 'temp_data' not in st.session_state:
        st.session_state.temp_data = {}

def get_session_value(key: str, default: Any = None) -> Any:
    """
    Get value from session state.

    Args:
        key: Key to retrieve
        default: Default value if key doesn't exist

    Returns:
        Value from session state or default
    """
    return st.session_state.get(key, default)

def set_session_value(key: str, value: Any) -> None:
    """
    Set value in session state.

    Args:
        key: Key to set
        value: Value to store
    """
    st.session_state[key] = value

def update_session_values(updates: Dict[str, Any]) -> None:
    """
    Update multiple session values at once.

    Args:
        updates: Dictionary of key-value pairs to update
    """
    for key, value in updates.items():
        st.session_state[key] = value

def clear_session_state():
    """Clear all session state variables."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()

def clear_temp_data():
    """Clear temporary session data."""
    if 'temp_data' in st.session_state:
        st.session_state.temp_data = {}

def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return st.session_state.get('authenticated', False)

def get_user_info() -> Dict[str, Any]:
    """Get current user information from session."""
    return {
        'user_id': st.session_state.get('user_id'),
        'email': st.session_state.get('user_email'),
        'name': st.session_state.get('user_name'),
        'company': st.session_state.get('company_name')
    }

def set_user_info(user_data: Dict[str, Any]):
    """Set user information in session."""
    st.session_state.authenticated = True
    st.session_state.user_id = user_data.get('id')
    st.session_state.user_email = user_data.get('email')
    st.session_state.user_name = user_data.get('name')
    st.session_state.company_name = user_data.get('company')

def logout():
    """Logout user and clear session."""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.user_name = None
    st.session_state.company_name = None
    clear_temp_data()

def cache_analytics_data(key: str, data: Any, ttl_seconds: int = 300):
    """
    Cache analytics data with TTL.

    Args:
        key: Cache key
        data: Data to cache
        ttl_seconds: Time to live in seconds
    """
    if 'analytics_cache' not in st.session_state:
        st.session_state.analytics_cache = {}

    st.session_state.analytics_cache[key] = {
        'data': data,
        'timestamp': datetime.now(),
        'ttl': ttl_seconds
    }

def get_cached_analytics(key: str) -> Any:
    """
    Get cached analytics data if still valid.

    Args:
        key: Cache key

    Returns:
        Cached data or None if expired/not found
    """
    if 'analytics_cache' not in st.session_state:
        return None

    if key not in st.session_state.analytics_cache:
        return None

    cache_entry = st.session_state.analytics_cache[key]
    age_seconds = (datetime.now() - cache_entry['timestamp']).total_seconds()

    if age_seconds > cache_entry['ttl']:
        # Cache expired
        del st.session_state.analytics_cache[key]
        return None

    return cache_entry['data']

def add_uploaded_file(file_info: Dict[str, Any]):
    """Add file to uploaded files list."""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []

    st.session_state.uploaded_files.append({
        **file_info,
        'timestamp': datetime.now()
    })

def get_uploaded_files():
    """Get list of uploaded files."""
    return st.session_state.get('uploaded_files', [])

def clear_uploaded_files():
    """Clear uploaded files list."""
    st.session_state.uploaded_files = []

def update_processing_status(file_id: str, status: str, details: Dict = None):
    """
    Update processing status for a file.

    Args:
        file_id: File identifier
        status: Processing status
        details: Additional status details
    """
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}

    st.session_state.processing_status[file_id] = {
        'status': status,
        'details': details or {},
        'updated_at': datetime.now()
    }

def get_processing_status(file_id: str) -> Dict:
    """Get processing status for a file."""
    if 'processing_status' not in st.session_state:
        return None

    return st.session_state.processing_status.get(file_id)