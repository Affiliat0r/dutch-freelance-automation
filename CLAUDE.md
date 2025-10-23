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

### Invoice System (Omzet/Income Side)

The application now includes a complete invoice system for tracking revenue alongside expense tracking:

**Storage** ([utils/invoice_storage.py](utils/invoice_storage.py)):
- JSON-based storage in `invoice_data/invoices_metadata.json`
- Invoice PDFs stored in `invoice_data/invoices/`
- Client data in `invoice_data/clients.json`
- Settings in `invoice_data/settings.json`
- Functions: `save_invoice()`, `get_next_invoice_number()`, `filter_invoices()`, `get_invoice_statistics()`

**Invoice Services**:
1. **Invoice Service** ([services/invoice_service.py](services/invoice_service.py))
   - `calculate_line_item_totals()`: Calculate subtotal, VAT, total per line
   - `calculate_invoice_totals()`: Sum all items, break down VAT by rate (0%, 9%, 21%)
   - `validate_invoice_data()`: Validate required fields, amounts, VAT rates
   - `create_invoice_from_form()`: Convert UI form data to invoice structure

2. **PDF Generator** ([services/pdf_generator.py](services/pdf_generator.py))
   - `generate_invoice_pdf()`: Create professional Dutch-compliant PDF invoices
   - Includes: company logo, client info, line items table, VAT breakdown, payment terms
   - Uses ReportLab library

**Invoice Module** ([modules/invoices.py](modules/invoices.py)):
- **New Invoice Tab**: Multi-line item editor with real-time calculations
- **Overview Tab**: List all invoices with filtering
- **Unpaid Tab**: Track unpaid and overdue invoices
- **Clients Tab**: Manage client information

**Integration Points**:
- Dashboard now shows both income and expense metrics
- Analytics includes revenue analysis and profit/loss reports
- Export/Reports includes P&L and revenue reports
- Settings has dedicated Invoice Settings tab

### Multi-Step Gemini Processing Pipeline

The application uses a **Gemini-only processing pipeline** ([services/processing_pipeline.py](services/processing_pipeline.py)):

**Step 1: Image/PDF → Raw Text** ([services/llm_service.py:95-122](services/llm_service.py#L95-L122))
- PDFs: Direct text extraction using PyPDF2 (digital receipts)
- Images: Gemini Vision API extracts raw text (physical receipts)
- No Tesseract OCR - Gemini Vision handles everything

**Step 2: Raw Text → Structured Data** ([services/llm_service.py:124-180](services/llm_service.py#L124-L180))
- Gemini parses raw text into JSON structure
- Extracts: vendor, date, items, amounts, VAT breakdown, payment method
- Dutch receipt format aware (BTW, Totaal, etc.)

**Step 2.5: Currency Conversion** ([services/llm_service.py:244-383](services/llm_service.py#L244-L383))
- Detects foreign language receipts (Turkish, English, etc.)
- Infers currency from language (TRY for Turkish, USD/GBP for English)
- Converts all amounts to EUR using Frankfurter API
- Adds conversion metadata (rate, date, original currency)
- See "Currency Conversion System" section below for details

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
│   ├── models.py               # SQLAlchemy models (User, Receipt, ExtractedData, Invoice, InvoiceSettings, etc.)
│   └── connection.py           # Database session management, init_db(), drop_db()
├── modules/                    # Streamlit page modules (NOT "pages/")
│   ├── dashboard.py            # Main dashboard with KPIs (income + expenses)
│   ├── upload_receipts.py      # Batch upload interface
│   ├── receipt_management.py   # Review/edit extracted data
│   ├── invoices.py             # Invoice builder and management (NEW)
│   ├── analytics.py            # Charts and trend analysis (includes revenue & P&L)
│   ├── export_reports.py       # Excel/CSV/JSON export (includes P&L & revenue reports)
│   └── settings.py             # User preferences (includes invoice settings tab)
├── services/
│   ├── llm_service.py          # Multi-step Gemini processing pipeline (with currency conversion)
│   ├── processing_pipeline.py  # Orchestrates receipt processing flow
│   ├── invoice_service.py      # Invoice calculations and validation
│   ├── pdf_generator.py        # Invoice PDF generation with ReportLab
│   ├── exchange_rate_service.py # Currency conversion via Frankfurter API (NEW)
│   ├── export_service.py       # Export functionality
│   └── ocr_service.py          # Legacy Tesseract OCR (not actively used)
└── utils/
    ├── session_state.py        # Streamlit session management
    ├── database_utils.py       # Database CRUD operations
    ├── local_storage.py        # Receipt local JSON storage
    ├── invoice_storage.py      # Invoice local JSON storage
    ├── reset_utils.py          # Hard reset utility for development (NEW)
    ├── file_utils.py           # File handling, validation
    ├── calculations.py         # Tax calculation helpers
    └── auth.py                 # Authentication (currently disabled)
```

### Data Flow

**Expense (Kosten) Side:**
1. User uploads receipt(s) via [modules/upload_receipts.py](modules/upload_receipts.py)
2. Receipt saved to **local storage** ([utils/local_storage.py](utils/local_storage.py)) with status="pending"
3. [services/processing_pipeline.py](services/processing_pipeline.py) orchestrates processing:
   - Calls [services/llm_service.py](services/llm_service.py) for 4-step Gemini extraction
   - For local storage: Updates receipt via `update_receipt_data()`
   - For database: Saves via [utils/database_utils.py](utils/database_utils.py)
   - Updates receipt status to "completed" or "failed"
4. User reviews/edits in [modules/receipt_management.py](modules/receipt_management.py)
5. User exports data in [modules/export_reports.py](modules/export_reports.py)

**Income (Omzet) Side:**
1. User creates invoice via [modules/invoices.py](modules/invoices.py) New Invoice tab
2. Invoice data validated by [services/invoice_service.py](services/invoice_service.py)
3. Invoice saved to **local storage** ([utils/invoice_storage.py](utils/invoice_storage.py))
4. PDF generated via [services/pdf_generator.py](services/pdf_generator.py) if requested
5. User manages invoices in Overview/Unpaid tabs
6. User exports revenue reports in [modules/export_reports.py](modules/export_reports.py)

**Combined Analysis:**
- Dashboard combines income and expense metrics for profit calculation
- Analytics provides P&L reports merging both datasets
- Export/Reports generates comprehensive financial reports

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

## Currency Conversion System

The application automatically detects and converts foreign currency receipts to EUR ([services/exchange_rate_service.py](services/exchange_rate_service.py)):

### How It Works

**Language Detection → Currency Inference** ([services/llm_service.py:244-383](services/llm_service.py#L244-L383)):
- Detects receipt language from `structured_data['language']` field
- Maps languages to currencies:
  - Turkish (`tr`) → TRY (Turkish Lira)
  - English (`en`) → USD (US Dollar) or GBP (British Pound)
  - Dutch (`nl`) → EUR (no conversion needed)
- Uses receipt date for historical exchange rates

### Exchange Rate Service ([services/exchange_rate_service.py](services/exchange_rate_service.py))

**API Source:** [Frankfurter API](https://www.frankfurter.app/docs/)
- Free, open-source API for European Central Bank exchange rates
- No API key required
- Supports historical rates and all major currencies

**Key Features:**
- `get_exchange_rate(from_currency, to_currency, rate_date)` - Fetch exchange rate
- `convert_amount(amount, from_currency, to_currency, rate_date)` - Convert amount
- **90-day caching** - Exchange rates cached in `temp/exchange_rates_cache.json`
- **Fallback mechanism** - Uses recent cached rate if API unavailable

**Converted Data Structure:**
```python
{
    'original_currency': 'TRY',
    'original_amounts': {
        'total_amount': 500.00,
        'total_vat': 90.00,
        'amount_excl_vat': 410.00
    },
    'exchange_rate': 0.028,
    'exchange_rate_date': '2025-01-15',
    'total_amount': 14.00,      # Converted to EUR
    'total_vat': 2.52,          # Converted to EUR
    'amount_excl_vat': 11.48,   # Converted to EUR
    'currency': 'EUR'
}
```

**Error Handling:**
- If conversion fails, receipt marked for `manual_review_required`
- Original amounts preserved in `original_amounts` field
- Error message stored in `currency_conversion_error` field

### Testing Currency Conversion

To test with foreign receipts:
1. Upload a Turkish receipt → Should auto-convert TRY to EUR
2. Upload an English receipt → Should auto-convert USD/GBP to EUR
3. Check `exchange_rates_cache.json` for cached rates
4. Review converted amounts in Receipt Management module

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

Available page names: "Dashboard", "Upload Bonnen", "Bonnen Beheer", "Facturen", "Analytics", "Export/Rapporten", "Instellingen"

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

7. **Invoice System Status**: The invoice system (Facturen module) is fully implemented with all core features (invoice creation, PDF generation, client management, unpaid tracking). Remaining work focuses on integration with dashboard, analytics, and export modules. See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for details.

8. **Currency Conversion**: Foreign currency receipts are automatically detected and converted to EUR using the Frankfurter API. No additional API key needed. Exchange rates are cached for 90 days. If you're working with receipts from Turkey, UK, or US, currency conversion happens automatically in Step 2.5 of the processing pipeline.

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

### Resetting Application Data (Development)

For development and testing, use [utils/reset_utils.py](utils/reset_utils.py) to completely reset all data:

```python
from utils.reset_utils import hard_reset_all_data, get_data_statistics

# Get current data statistics before reset
stats = get_data_statistics()
print(f"Current data: {stats['receipt_count']} receipts, {stats['invoice_count']} invoices")

# Perform hard reset (WARNING: Deletes ALL data!)
results = hard_reset_all_data()

if results['success']:
    print("All data successfully reset")
else:
    print(f"Reset completed with errors: {results}")
```

**What gets deleted:**
- All receipt files and `receipts_metadata.json`
- All invoice files, `invoices_metadata.json`, and client data
- Exchange rate cache (`temp/exchange_rates_cache.json`)
- Database (dropped and recreated)

**WARNING:** This is irreversible! Only use during development/testing. Never use in production.

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

**Currency Conversion Issues:**
- Frankfurter API requires no authentication, but needs internet connection
- Check network connectivity if conversions fail
- Exchange rates are cached for 90 days in `temp/exchange_rates_cache.json`
- If API is down, system uses fallback from cache (last 30 days)
- Manual review required if conversion fails (check `currency_conversion_error` field)
- To clear cache: Delete `temp/exchange_rates_cache.json` file
- Verify receipt language detection is working correctly (language field should be `tr`, `en`, `nl`, etc.)
