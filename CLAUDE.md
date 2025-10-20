# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Dutch Freelance Administration Automation** application built with Streamlit. It automates receipt processing, VAT calculations, and income tax preparation for Dutch freelancers (ZZP'ers) using AI/LLM technology.

**Key Technologies:**
- **Frontend/UI:** Streamlit with custom CSS
- **AI/ML:** Google Gemini API (gemini-2.5-flash-lite model) for end-to-end receipt processing
- **Database:** PostgreSQL (SQLAlchemy ORM), SQLite for development
- **Caching:** Redis (configured but optional)
- **Image Processing:** Pillow, OpenCV (legacy)
- **Data Processing:** Pandas, NumPy, openpyxl

## Development Setup

### Environment Configuration

1. Copy `.env.example` to `.env` and configure:
   - `GEMINI_API_KEY`: **Required** - Get from [Google AI Studio](https://aistudio.google.com/app/apikey)
   - `DATABASE_URL`: PostgreSQL connection string (defaults to SQLite if not set)
   - `REDIS_URL`: Redis connection string (optional, for caching/async processing)
   - `SECRET_KEY`: Security key for authentication

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize database:
   ```bash
   # Database initialization is handled automatically on app startup
   # See app.py:262-263 - calls init_db() from database.connection
   ```

### Running the Application

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

### Running Tests

```bash
pytest                           # Run all tests
pytest -v                        # Verbose mode
pytest tests/test_specific.py    # Single test file
```

### Database Migrations

The project includes Alembic for database migrations:

```bash
# Initialize Alembic (already done)
alembic init alembic

# Create a new migration after model changes
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Architecture

### Four-Step Gemini Processing Pipeline

The application uses a **Gemini-only processing pipeline** ([services/processing_pipeline.py](services/processing_pipeline.py)) with these steps:

**Step 1: Image/PDF → Raw Text** ([services/llm_service.py:94-122](services/llm_service.py#L94-L122))
- For PDFs: Direct text extraction using PyPDF2 (digital receipts)
- For images: Gemini Vision API extracts raw text (physical receipts)
- No Tesseract OCR required - Gemini Vision handles everything

**Step 2: Raw Text → Structured Data** ([services/llm_service.py:123-180](services/llm_service.py#L123-L180))
- Gemini parses raw text into JSON structure
- Extracts: vendor, date, items, amounts, VAT breakdown, payment method
- Dutch receipt format aware (BTW, Totaal, etc.)

**Step 3: Structured Data → Category** ([services/llm_service.py:181-234](services/llm_service.py#L181-L234))
- Gemini categorizes expense using Dutch tax categories
- Returns one of 7 predefined categories (Beroepskosten, Kantoorkosten, etc.)
- Validates category against allowlist

**Step 4: Category → Tax Percentages** ([services/llm_service.py:235-292](services/llm_service.py#L235-L292))
- Python rule-based logic applies Dutch tax rules
- Sets BTW aftrekbaar % and IB aftrekbaar % based on category
- Calculates: VAT refund, remainder after VAT, profit deduction

**Note:** OCR Service ([services/ocr_service.py](services/ocr_service.py)) exists but is **not used** in current pipeline. The Gemini Vision approach proved more accurate and eliminated the need for traditional OCR preprocessing.

### Application Structure

```
app.py                          # Main entry point, navigation, page routing
config.py                       # Centralized configuration management
├── database/
│   ├── models.py               # SQLAlchemy models (User, Receipt, ExtractedData, AuditLog)
│   └── connection.py           # Database session management, init_db(), drop_db()
├── modules/                    # Streamlit page modules (NOT "pages/")
│   ├── dashboard.py            # Main dashboard with KPIs
│   ├── upload_receipts.py      # Batch upload interface
│   ├── receipt_management.py   # Review/edit extracted data
│   ├── analytics.py            # Charts and trend analysis
│   ├── export_reports.py       # Excel/CSV/JSON export
│   └── settings.py             # User preferences
├── services/
│   ├── llm_service.py          # 4-step Gemini processing pipeline
│   ├── processing_pipeline.py  # Orchestrates receipt processing flow
│   ├── export_service.py       # Export functionality
│   └── ocr_service.py          # Legacy Tesseract OCR (not actively used)
└── utils/
    ├── session_state.py        # Streamlit session management
    ├── database_utils.py       # Database CRUD operations
    ├── file_utils.py           # File handling, validation
    ├── calculations.py         # Tax calculation helpers
    └── auth.py                 # Authentication (currently disabled)
```

### Data Flow

1. User uploads receipt(s) via [modules/upload_receipts.py](modules/upload_receipts.py)
2. Receipt saved to database with status="pending"
3. [services/processing_pipeline.py](services/processing_pipeline.py) orchestrates processing:
   - Calls [services/llm_service.py](services/llm_service.py) for 4-step extraction
   - Saves extracted data via [utils/database_utils.py](utils/database_utils.py)
   - Updates receipt status to "completed" or "failed"
   - Creates audit log entry
4. User reviews/edits in [modules/receipt_management.py](modules/receipt_management.py)
5. User exports data in [modules/export_reports.py](modules/export_reports.py)

## Dutch Tax Categories & Rules

The application uses specific Dutch expense categories defined in [config.py:58-66](config.py#L58-L66):

1. **Beroepskosten** - Professional expenses (100% BTW, 100% IB aftrekbaar)
2. **Kantoorkosten** - Office expenses (100% BTW, 100% IB)
3. **Reis- en verblijfkosten** - Travel expenses (100% BTW, 100% IB)
4. **Representatiekosten - Type 1 (Supermarket)** - Business food from supermarkets (0% BTW, 80% IB)
5. **Representatiekosten - Type 2 (Horeca)** - Restaurant expenses (0% BTW, 80% IB)
6. **Vervoerskosten** - Transportation costs (100% BTW, 100% IB)
7. **Zakelijke opleidingskosten** - Business training (100% BTW, 100% IB)

**VAT Rates in Netherlands:**
- 21% (hoog - standard rate)
- 9% (laag - reduced rate for books, magazines; previously 6%)
- 0% (geen BTW - exempt)

### Tax Calculation Logic

Tax rules are defined in [services/llm_service.py:235-261](services/llm_service.py#L235-L261):

```python
tax_rules = {
    'Beroepskosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
    'Kantoorkosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
    'Reis- en verblijfkosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
    'Representatiekosten - Type 1 (Supermarket)': {'btw_aftrekbaar': 0, 'ib_aftrekbaar': 80},
    'Representatiekosten - Type 2 (Horeca)': {'btw_aftrekbaar': 0, 'ib_aftrekbaar': 80},
    'Vervoerskosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100},
    'Zakelijke opleidingskosten': {'btw_aftrekbaar': 100, 'ib_aftrekbaar': 100}
}
```

**Calculation formulas** ([services/llm_service.py:263-292](services/llm_service.py#L263-L292)):
- `amount_excl_vat = total_amount - total_vat`
- `vat_deductible = total_vat × (btw_percentage / 100)`
- `remainder_after_vat = total_amount - vat_deductible`
- `profit_deduction = amount_excl_vat × (ib_percentage / 100)`

## Excel Export Format

The export functionality ([config.py:69-85](config.py#L69-L85)) generates standardized Excel files with these columns:

- Nr, Datum, Winkel/Leverancier, Categorie kosten
- Bedrag excl. BTW, BTW 6%, BTW 9%, BTW 21%, Totaal incl. BTW
- BTW aftrekbaar %, IB aftrekbaar %
- BTW terugvraag, Restant na BTW, Winstaftrek
- Toelichting/motivatie

This format is compatible with Dutch accounting standards and quarterly VAT declarations (BTW aangifte).

## Key Patterns & Conventions

### Configuration Management

All configuration is centralized in [config.py](config.py). The `Config` class:
- Loads environment variables using `python-dotenv`
- Provides default values for all settings
- Has `create_directories()` method for setup (called on import at line 115)
- Has `validate()` method for startup checks (validates API keys, SECRET_KEY)

### Session State Management

Use [utils/session_state.py](utils/session_state.py) for all Streamlit session state operations:
- `init_session_state()` - Initialize all session variables
- `get_session_value(key, default)` - Retrieve values safely
- `set_session_value(key, value)` - Store values
- `cache_analytics_data(key, data, ttl)` - Cache expensive computations

### Database Models

All models use SQLAlchemy declarative base ([database/models.py](database/models.py)):

**Key relationships:**
- `User` → `Receipt` (one-to-many via `receipts`)
- `User` → `UserSettings` (one-to-one via `settings`)
- `Receipt` → `ExtractedData` (one-to-one via `extracted_data`)
- `Receipt` → `AuditLog` (one-to-many via `audit_logs`)

**Important:** Use `Numeric(12, 2)` for all currency amounts to avoid floating-point precision issues. Never use `Float` for money.

### Database Operations

Use helper functions from [utils/database_utils.py](utils/database_utils.py) instead of raw SQLAlchemy:
- `save_extracted_data(receipt_id, data_dict)` - Save extraction results
- `update_receipt_status(receipt_id, status, error=None)` - Update processing status
- `log_audit_event(user_id, action, entity_type, entity_id, ...)` - Create audit trail

### Error Handling in Services

Both LLM and processing services follow this pattern:
```python
try:
    # Main processing
    result = process_data()
    return {'success': True, 'data': result}
except Exception as e:
    logger.error(f"Processing failed: {e}")
    return {'success': False, 'error': str(e)}
```

Always return a dictionary with `success` boolean for consistent error handling.

### Streamlit Page Navigation

Navigation uses `streamlit-option-menu` ([app.py:208-232](app.py#L208-L232)). To programmatically navigate:

```python
import streamlit as st
st.session_state['selected_page'] = 'Bonnen Beheer'
st.rerun()
```

Available page names: "Dashboard", "Upload Bonnen", "Bonnen Beheer", "Analytics", "Export/Rapporten", "Instellingen"

## Important Notes

1. **Authentication Currently Disabled**: See [app.py:177-180](app.py#L177-L180) - authentication is commented out for initial development. Uncomment and configure before production.

2. **File Upload Limits** ([config.py:26-31](config.py#L26-L31)):
   - Max file size: 10MB per file (configurable via `MAX_UPLOAD_SIZE_MB`)
   - Max batch size: 50 files (`MAX_BATCH_SIZE`)
   - Allowed formats: PDF, PNG, JPG, JPEG

3. **7-Year Data Retention**: Dutch tax law (Belastingdienst) requires 7-year retention of financial records. Do not implement automatic deletion before this period.

4. **GDPR Compliance**: The application handles personal and financial data (name, company, KVK number, BTW number, receipts). All processing must be GDPR compliant:
   - Right to access (data export)
   - Right to deletion (user account deletion)
   - Data audit trail ([database/models.py:134-153](database/models.py#L134-L153))

5. **Gemini API Dependency**: The application **requires** Gemini API. There is no fallback. Ensure `GEMINI_API_KEY` is always configured.

6. **Database Defaults to SQLite**: If `DATABASE_URL` contains "sqlite", the app uses SQLite with special connection settings ([database/connection.py:15-22](database/connection.py#L15-L22)). Otherwise, it uses PostgreSQL with connection pooling.

## Common Development Tasks

### Adding a New Expense Category

1. Add category to [config.py:58-66](config.py#L58-L66) `EXPENSE_CATEGORIES` list
2. Add tax rules to [services/llm_service.py:246-254](services/llm_service.py#L246-L254) `tax_rules` dict
3. Update Gemini prompt in [services/llm_service.py:211-222](services/llm_service.py#L211-L222) with category guidelines
4. Test with sample receipts

### Adding a New Database Model

1. Define model in [database/models.py](database/models.py) using SQLAlchemy declarative base
2. Create Alembic migration: `alembic revision --autogenerate -m "Add new model"`
3. Review generated migration in `alembic/versions/`
4. Apply migration: `alembic upgrade head`
5. Add CRUD functions to [utils/database_utils.py](utils/database_utils.py)

### Adding a New Streamlit Page

1. Create new module in `modules/` folder (e.g., `modules/new_page.py`)
2. Implement `show()` function that renders the page
3. Add to navigation menu in [app.py:193-200](app.py#L193-L200)
4. Add icon and routing logic in [app.py:208-254](app.py#L208-L254)

### Modifying Gemini Prompts

All prompts are in [services/llm_service.py](services/llm_service.py):
- **Step 1 (Raw Text):** Lines 104-119
- **Step 2 (Structured Data):** Lines 133-177
- **Step 3 (Category):** Lines 203-224

When changing prompts, test with diverse receipt types (Dutch/English, digital/scanned, various vendors).

## Future Development Areas

Based on [PRD_Administration_Automation.md](PRD_Administration_Automation.md):
- **Phase 1 (MVP - Current)**: Basic receipt upload, Gemini processing, Excel export
- **Phase 2**: Advanced analytics, batch processing improvements, email receipt import
- **Phase 3**: Accounting software integrations (Exact Online, Twinfield)
- **Phase 4**: Predictive analytics, automated tax advice, mobile app

## Troubleshooting

**Gemini API Errors:**
- Verify `GEMINI_API_KEY` in `.env` file
- Check API quota limits at [Google AI Studio](https://aistudio.google.com/)
- Check Gemini API status at [Google Cloud Status](https://status.cloud.google.com/)
- Review error logs: Gemini errors are logged in [services/llm_service.py:88-92](services/llm_service.py#L88-L92)

**Database Connection Issues:**
- For PostgreSQL: Verify PostgreSQL is running and `DATABASE_URL` is correct
- For SQLite: Check file permissions in project directory
- Database initialization runs on app startup ([app.py:262-263](app.py#L262-L263))
- Use `drop_db()` from [database/connection.py](database/connection.py) to reset (caution: deletes all data)

**Streamlit Session State Issues:**
- Use helper functions from [utils/session_state.py](utils/session_state.py)
- Call `init_session_state()` at app startup ([app.py:172](app.py#L172))
- Check session state with `st.write(st.session_state)` for debugging
- Clear cache: `st.cache_data.clear()` or restart Streamlit server

**File Upload Failures:**
- Check file size limit: [config.py:26-27](config.py#L26-L27)
- Verify allowed extensions: [config.py:28-30](config.py#L28-L30)
- Ensure upload directories exist (created automatically by [config.py:88-96](config.py#L88-L96))
- Check file validation logic in [utils/file_utils.py](utils/file_utils.py)

**Receipt Processing Failures:**
- Check Gemini API key is valid
- Verify receipt image quality (readable text, good lighting)
- For PDFs: Ensure they contain text (not scanned images embedded in PDF)
- Check processing logs in Streamlit console
- Review extracted data confidence score (< 0.7 requires manual review)
