# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Dutch Freelance Administration Automation** application built with Streamlit. It automates receipt processing, VAT calculations, and income tax preparation for Dutch freelancers (ZZP'ers) using AI/LLM technology.

**Key Technologies:**
- **Frontend/UI:** Streamlit with custom CSS
- **AI/ML:** Google Gemini API (gemini-2.5-flash-lite model) for OCR and text extraction
- **Database:** PostgreSQL (SQLAlchemy ORM)
- **Caching:** Redis
- **Image Processing:** OpenCV, Tesseract OCR, Pillow
- **Data Processing:** Pandas, NumPy, openpyxl

## Development Setup

### Environment Configuration

1. Copy `.env.example` to `.env` and configure:
   - `GEMINI_API_KEY`: Required for AI-powered receipt processing
   - `DATABASE_URL`: PostgreSQL connection string
   - `REDIS_URL`: Redis connection string (for caching/async processing)
   - `SECRET_KEY`: Security key for authentication

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize database:
   ```bash
   # Database initialization is handled automatically on app startup
   # See app.py line 242: init_db()
   ```

### Running the Application

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

### Running Tests

```bash
pytest
pytest -v  # verbose mode
pytest tests/test_specific.py  # single test file
```

## Architecture

### Three-Layer Processing Pipeline

1. **OCR Service** ([services/ocr_service.py](services/ocr_service.py))
   - Preprocesses images (grayscale, threshold, deskew)
   - Extracts raw text using Tesseract OCR
   - Supports Dutch (nld) and English (eng) languages
   - Provides confidence scoring

2. **LLM Service** ([services/llm_service.py](services/llm_service.py))
   - Uses Google Gemini 2.5 Flash Lite model for intelligent text extraction
   - Categorizes expenses into Dutch tax categories
   - Calculates VAT and income tax deductions
   - Falls back to rule-based processing if API unavailable

3. **Data Layer** ([database/models.py](database/models.py))
   - User management with multi-tenancy support
   - Receipt storage with processing status tracking
   - ExtractedData model stores all financial information
   - AuditLog tracks all changes for compliance
   - ExportHistory maintains export records

### Application Structure

```
app.py                  # Main entry point, navigation, page routing
config.py               # Centralized configuration management
├── database/
│   ├── models.py       # SQLAlchemy models (User, Receipt, ExtractedData, AuditLog)
│   └── connection.py   # Database initialization and session management
├── pages/              # Streamlit pages (modular UI components)
│   ├── dashboard.py
│   ├── upload_receipts.py
│   ├── receipt_management.py
│   ├── analytics.py
│   ├── export_reports.py
│   └── settings.py
├── services/
│   ├── ocr_service.py  # Tesseract OCR + image preprocessing
│   └── llm_service.py  # Google Gemini integration
└── utils/
    └── session_state.py # Streamlit session state management
```

## Dutch Tax Categories & Rules

The application uses specific Dutch expense categories defined in [config.py](config.py):

1. **Beroepskosten** - Professional expenses (100% VAT, 100% IB deductible)
2. **Kantoorkosten** - Office expenses (100% VAT, 100% IB)
3. **Reis- en verblijfkosten** - Travel expenses (100% VAT, 100% IB)
4. **Representatiekosten - Type 1 (Supermarket)** - Business food from supermarkets (0% VAT, 80% IB)
5. **Representatiekosten - Type 2 (Horeca)** - Restaurant expenses (0% VAT, 80% IB)
6. **Vervoerskosten** - Transportation costs (100% VAT, 100% IB)
7. **Zakelijke opleidingskosten** - Business training (100% VAT, 100% IB)

**VAT Rates in Netherlands:**
- 21% (high/standard rate)
- 9% (reduced rate - books, magazines, previously 6%)
- 0% (exempt)

### Tax Calculation Logic

See [services/llm_service.py:88-125](services/llm_service.py#L88-L125) for the `calculate_tax_deductions()` method which implements Dutch tax rules.

## Excel Export Format

The export functionality ([config.py:69-85](config.py#L69-L85)) generates standardized Excel files with these columns:

- Nr, Datum, Winkel/Leverancier, Categorie kosten
- Bedrag excl. BTW, BTW 6%, BTW 9%, BTW 21%, Totaal incl. BTW
- BTW aftrekbaar %, IB aftrekbaar %
- BTW terugvraag, Restant na BTW, Winstaftrek
- Toelichting/motivatie

## Key Patterns & Conventions

### Configuration Management

All configuration is centralized in [config.py](config.py). The `Config` class:
- Loads environment variables using `python-dotenv`
- Provides default values for all settings
- Has `create_directories()` method for setup (called on import)
- Has `validate()` method for startup checks

### Session State Management

Use [utils/session_state.py](utils/session_state.py) for all Streamlit session state operations:
- `init_session_state()` - Initialize all session variables
- `get_session_value(key, default)` - Retrieve values safely
- `set_session_value(key, value)` - Store values
- `cache_analytics_data(key, data, ttl)` - Cache expensive computations

### Database Models

All models use SQLAlchemy declarative base. Key relationships:
- User → Receipts (one-to-many)
- User → UserSettings (one-to-one)
- Receipt → ExtractedData (one-to-one)
- Receipt → AuditLog (one-to-many)

Use `Numeric(12, 2)` for all currency amounts to avoid floating-point issues.

### Error Handling in Services

Both OCR and LLM services follow this pattern:
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

## Important Notes

1. **Authentication Currently Disabled**: See [app.py:168-171](app.py#L168-L171) - authentication is commented out for initial development

2. **File Upload Limits**:
   - Max file size: 10MB per file (configurable)
   - Max batch size: 50 files
   - Allowed formats: PDF, PNG, JPG, JPEG

3. **7-Year Data Retention**: Dutch tax law requires 7-year retention of financial records - ensure this is maintained

4. **GDPR Compliance**: The application handles personal and financial data - all processing must be GDPR compliant

5. **Gemini API Dependency**: The LLM service gracefully degrades to rule-based processing when Gemini API is unavailable

## Future Development Areas

Based on [PRD_Administration_Automation.md](PRD_Administration_Automation.md):
- **Phase 1 (MVP)**: Basic receipt upload, OCR, Excel export
- **Phase 2**: Advanced analytics, batch processing improvements
- **Phase 3**: Accounting software integrations (e.g., Exact Online)
- **Phase 4**: Predictive analytics, automated tax advice

## Troubleshooting

**OCR Not Working:**
- Ensure Tesseract is installed and in PATH
- Check language data files are available (nld, eng)
- Verify image preprocessing in [services/ocr_service.py:66-97](services/ocr_service.py#L66-L97)

**Gemini API Errors:**
- Verify `GEMINI_API_KEY` in `.env`
- Check API quota limits
- LLM service will fall back to rule-based processing

**Database Connection Issues:**
- Verify PostgreSQL is running
- Check `DATABASE_URL` format in `.env`
- Database initialization runs on app startup ([app.py:242](app.py#L242))

**Streamlit Session State Issues:**
- Use helper functions from [utils/session_state.py](utils/session_state.py)
- Call `init_session_state()` at app startup
- Clear cache with `clear_temp_data()` if needed
