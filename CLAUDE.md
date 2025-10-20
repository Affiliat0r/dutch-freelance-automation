# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Dutch Freelance Administration Automation** application built with Streamlit. It automates receipt processing, VAT calculations, and income tax preparation for Dutch freelancers (ZZP'ers) using AI/LLM technology.

**Key Technologies:**
- **Frontend/UI:** Streamlit with custom CSS
- **AI/ML:** Google Gemini API (gemini-2.5-flash-lite model) for end-to-end receipt processing
- **Storage:** Dual system - SQLAlchemy ORM (database) + Local JSON file storage
- **Database:** PostgreSQL (production), SQLite (development)
- **Image Processing:** Pillow, PyPDF2
- **Data Processing:** Pandas, NumPy, openpyxl

## Development Setup

### Environment Configuration

1. Copy `.env.example` to `.env` and configure:
   - `GEMINI_API_KEY`: **Required** - Get from [Google AI Studio](https://aistudio.google.com/app/apikey)
   - `DATABASE_URL`: PostgreSQL connection string (defaults to SQLite if not set)
   - `SECRET_KEY`: Security key for authentication

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   streamlit run app.py
   ```

The app will be available at `http://localhost:8501`

**Note:** Database initialization happens automatically on app startup ([app.py:266-267](app.py#L266-L267)).

## Architecture

### Dual Storage System

**CRITICAL:** The application uses **two parallel storage systems**:

1. **Database Storage** ([database/models.py](database/models.py), [utils/database_utils.py](utils/database_utils.py))
   - SQLAlchemy ORM with User, Receipt, ExtractedData, UserSettings models
   - Used for full relational data with user authentication
   - Currently partially implemented

2. **Local File Storage** ([utils/local_storage.py](utils/local_storage.py)) **← ACTIVELY USED**
   - JSON-based storage in `receipt_data/receipts_metadata.json`
   - Receipt files stored in `receipt_data/receipts/`
   - Simpler, no database setup required
   - Functions: `save_receipt()`, `update_receipt_status()`, `get_all_receipts()`, `filter_receipts()`

**Current modules primarily use local storage.** When adding features, check which storage system the module uses before implementing.

### Four-Step Gemini Processing Pipeline

The application uses a **Gemini-only processing pipeline** ([services/processing_pipeline.py](services/processing_pipeline.py)):

**Step 1: Image/PDF → Raw Text** ([services/llm_service.py:95-122](services/llm_service.py#L95-L122))
- PDFs: Direct text extraction using PyPDF2 (digital receipts)
- Images: Gemini Vision API extracts raw text (physical receipts)
- No Tesseract OCR - Gemini Vision handles everything

**Step 2: Raw Text → Structured Data** ([services/llm_service.py:124-180](services/llm_service.py#L124-L180))
- Gemini parses raw text into JSON structure
- Extracts: vendor, date, items, amounts, VAT breakdown, payment method
- Dutch receipt format aware (BTW, Totaal, etc.)

**Step 3: Structured Data → Category** ([services/llm_service.py:182-234](services/llm_service.py#L182-L234))
- Gemini categorizes expense using Dutch tax categories
- Returns one of 7 predefined categories
- Validates category against allowlist

**Step 4: Category → Tax Percentages** ([services/llm_service.py:236-278](services/llm_service.py#L236-L278))
- Python rule-based logic applies Dutch tax rules FROM DATABASE
- Reads tax percentages from UserSettings (Instellingen page → BTW & Belasting tab)
- Falls back to default rules if database settings don't exist
- Calculates: VAT refund, remainder after VAT, profit deduction

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
2. Receipt saved to **local storage** ([utils/local_storage.py](utils/local_storage.py)) with status="pending"
3. [services/processing_pipeline.py](services/processing_pipeline.py) orchestrates processing:
   - Calls [services/llm_service.py](services/llm_service.py) for 4-step Gemini extraction
   - For local storage: Updates receipt via `update_receipt_data()`
   - For database: Saves via [utils/database_utils.py](utils/database_utils.py)
   - Updates receipt status to "completed" or "failed"
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

**Tax percentages are loaded FROM DATABASE** ([services/llm_service.py:236-278](services/llm_service.py#L236-L278)):
- Function `_apply_tax_rules()` calls `get_category_tax_rules(user_settings_id)` from database
- Users configure percentages in Instellingen page → BTW & Belasting tab
- Default fallback values are hardcoded if database is empty

**Calculation formulas** ([services/llm_service.py:280-308](services/llm_service.py#L280-L308)):
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

### Storage Operations

**For Local File Storage** ([utils/local_storage.py](utils/local_storage.py)) **← PRIMARY SYSTEM**:
- `save_receipt(file_path, filename, file_size, file_type, extracted_data)` - Save receipt
- `update_receipt_status(receipt_id, status, error_message)` - Update status
- `update_receipt_data(receipt_id, extracted_data)` - Update extracted data
- `get_receipt(receipt_id)` - Get single receipt
- `get_all_receipts()` - Get all receipts
- `filter_receipts(start_date, end_date, status, categories, vendor, min_amount, max_amount)` - Filter
- `delete_receipt(receipt_id)` - Delete receipt and file
- `get_statistics(start_date, end_date)` - Get stats

**For Database Operations** ([utils/database_utils.py](utils/database_utils.py)):
- `save_extracted_data(receipt_id, data_dict)` - Save extraction results
- `update_receipt_status(receipt_id, status, error=None)` - Update processing status
- `get_category_tax_rules(user_settings_id)` - Get tax percentages from Instellingen
- `ensure_user_settings_exists(user_id)` - Create default settings if needed

**Database Models** ([database/models.py](database/models.py)):
- `User`, `Receipt`, `ExtractedData`, `UserSettings`, `AuditLog`
- **Important:** Use `Numeric(12, 2)` for currency amounts, never `Float`

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
2. Add default tax rules to [services/llm_service.py:254-261](services/llm_service.py#L254-L261) `default_tax_rules` dict
3. Update Gemini prompt in [services/llm_service.py:204-224](services/llm_service.py#L204-L224) with category guidelines
4. Update Instellingen page ([modules/settings.py](modules/settings.py)) to include new category in tax settings
5. Test with sample receipts

### Adding a New Streamlit Page

1. Create new module in `modules/` folder (e.g., `modules/new_page.py`)
2. Implement `show()` function that renders the page
3. Import module in [app.py](app.py) imports section
4. Add page name to `menu_options` list ([app.py:193-200](app.py#L193-L200))
5. Add icon to `option_menu` icons list ([app.py:215-222](app.py#L215-L222))
6. Add routing logic in main content area ([app.py:247-258](app.py#L247-L258))

### Modifying Gemini Prompts

All prompts are in [services/llm_service.py](services/llm_service.py):
- **Step 1 (Raw Text):** Lines 105-120
- **Step 2 (Structured Data):** Lines 134-178
- **Step 3 (Category):** Lines 204-225

When changing prompts, test with diverse receipt types (Dutch/English, digital/scanned, various vendors).

### Working with Local Storage vs Database

**When to use local storage:**
- Quick prototyping
- Single-user deployments
- No authentication needed
- Simpler deployment without database server

**When to use database:**
- Multi-user with authentication
- Complex queries and relationships
- Need for transactions and data integrity
- Production deployments

**Current state:** Most modules use local storage. Database is set up for future multi-user support.

## Troubleshooting

**Gemini API Errors:**
- Verify `GEMINI_API_KEY` in `.env` file
- Check API quota limits at [Google AI Studio](https://aistudio.google.com/)
- Review error logs: Gemini errors are logged in [services/llm_service.py:89-93](services/llm_service.py#L89-L93)

**Local Storage Issues:**
- Data stored in `receipt_data/receipts_metadata.json`
- Receipt files in `receipt_data/receipts/`
- Use `cleanup_metadata_file()` from [utils/local_storage.py](utils/local_storage.py) to remove duplicates
- Check file permissions on these directories

**Database Connection Issues (if using database):**
- For SQLite: Check file permissions in project directory
- For PostgreSQL: Verify PostgreSQL is running and `DATABASE_URL` is correct
- Database initialization runs on app startup ([app.py:266-267](app.py#L266-L267))

**Streamlit Session State Issues:**
- Use helper functions from [utils/session_state.py](utils/session_state.py)
- Check session state with `st.write(st.session_state)` for debugging
- Clear cache: `st.cache_data.clear()` or restart Streamlit server

**Receipt Processing Failures:**
- Check Gemini API key is valid
- Verify receipt image quality (readable text, good lighting)
- For PDFs: Ensure they contain text (not scanned images embedded in PDF)
- Check processing logs in Streamlit console
- Review extracted data confidence score (< 0.7 requires manual review)
