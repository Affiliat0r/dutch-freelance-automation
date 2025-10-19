# Administration Automation App for Dutch Freelance Companies

A comprehensive Streamlit application for automating receipt processing, VAT calculations, and tax administration for Dutch freelancers and small businesses.

## 🌟 Features

Based on the Product Requirements Document (PRD), this application provides:

### Core Functionality
- **Smart Receipt Upload**: Batch upload up to 50 receipts at once (PDF, PNG, JPG, JPEG)
- **AI-Powered Processing**:
  - OCR text extraction using Tesseract
  - Intelligent data extraction using Google Gemini LLM
  - Automatic expense categorization
  - Dutch and English language support

### Tax Compliance
- **Dutch VAT Handling**:
  - Support for 9% and 21% VAT rates
  - Automatic VAT calculation and deduction rules
  - Quarterly VAT declaration reports (BTW aangifte)
- **Income Tax Support**:
  - Expense categorization for Dutch tax rules
  - Deductibility calculations
  - Annual reports for income tax filing

### Business Intelligence
- **Interactive Dashboard**: Real-time metrics and KPIs
- **Advanced Analytics**:
  - Expense trends and patterns
  - Category breakdowns
  - Vendor analysis
  - Predictive forecasting
- **Comprehensive Reporting**: Excel, CSV, and JSON exports

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Tesseract OCR installed on your system
- PostgreSQL (optional, SQLite for development)

### Installation

1. Clone the repository:
```bash
cd "c:\Users\hasan.atesci\Documents\VSCode\Personal stuff\Administration Automation"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Tesseract OCR:
   - Windows: Download from [GitHub Tesseract releases](https://github.com/UB-Mannheim/tesseract/wiki)
   - Mac: `brew install tesseract`
   - Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-nld`

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Configure Google Gemini API:
   - Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Add the key to your `.env` file

### Running the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### Demo Access

For testing purposes, use these demo credentials:
- Email: `demo@example.com`
- Password: `demo`

## 📁 Project Structure

```
Administration-Automation/
├── app.py                 # Main Streamlit application
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
│
├── database/            # Database models and connections
│   ├── models.py       # SQLAlchemy models
│   └── connection.py   # Database session management
│
├── services/           # Core business logic
│   ├── ocr_service.py         # OCR processing
│   ├── llm_service.py         # LLM integration
│   ├── processing_pipeline.py # Receipt processing orchestration
│   └── export_service.py      # Export functionality
│
├── pages/              # Streamlit page modules
│   ├── dashboard.py           # Main dashboard
│   ├── upload_receipts.py     # Receipt upload interface
│   ├── receipt_management.py  # Receipt review and editing
│   ├── analytics.py          # Analytics and insights
│   ├── export_reports.py     # Export and reporting
│   └── settings.py           # User settings
│
├── utils/              # Utility functions
│   ├── auth.py              # Authentication
│   ├── calculations.py      # Tax calculations
│   ├── database_utils.py    # Database operations
│   ├── file_utils.py       # File handling
│   └── session_state.py    # Session management
│
└── uploads/            # File storage (auto-created)
    ├── receipts/      # New uploads
    ├── processed/     # Successfully processed
    ├── failed/        # Failed processing
    └── thumbnails/    # Image thumbnails
```

## 🎯 Key Features Explained

### Receipt Processing Pipeline

1. **Upload**: Users upload receipt images or PDFs
2. **OCR**: Text extraction using Tesseract
3. **AI Analysis**: Google Gemini extracts structured data
4. **Categorization**: Automatic expense category assignment
5. **Tax Calculation**: VAT and income tax deductions
6. **Storage**: Save to database with full audit trail

### Expense Categories

The app supports Dutch tax-compliant categories:
- Beroepskosten (Professional expenses)
- Kantoorkosten (Office expenses)
- Reis- en verblijfkosten (Travel and accommodation)
- Representatiekosten Type 1 & 2 (Entertainment expenses)
- Vervoerskosten (Transportation costs)
- Zakelijke opleidingskosten (Business training)

### VAT Handling

- Automatic detection of VAT rates (9%, 21%)
- Deductibility rules per category
- Quarterly VAT declaration preparation
- Export to tax-ready formats

## 🔧 Configuration

### Environment Variables

Key settings in `.env`:
- `GEMINI_API_KEY`: Google Gemini API key
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Application secret for security
- `MAX_UPLOAD_SIZE_MB`: Maximum file size (default: 10MB)
- `MAX_BATCH_SIZE`: Maximum batch upload (default: 50)

### Tax Rules

Configure default tax deduction percentages in Settings:
- VAT deductible percentages per category
- Income tax deductible percentages
- Custom rules for specific vendors

## 📊 Analytics Features

- **Dashboard**: Real-time KPIs and metrics
- **Trend Analysis**: Monthly and yearly patterns
- **Category Breakdown**: Expense distribution
- **VAT Analysis**: Effective rates and savings
- **Predictive Forecasting**: ML-based predictions

## 📥 Export Options

### Available Formats
- **Excel**: Formatted workbooks with multiple sheets
- **CSV**: Semicolon-delimited for Dutch locale
- **JSON**: Structured data for integrations
- **PDF**: Print-ready reports (coming soon)

### Report Types
- Quarterly VAT declaration (BTW aangifte)
- Annual income tax report
- Category summaries
- Vendor reports
- Custom date ranges

## 🔐 Security

- Password hashing with bcrypt
- Session management
- Audit logging for compliance
- File validation and sanitization
- SQL injection protection via ORM

## 🚧 Development

### Running Tests

```bash
pytest tests/
```

### Database Migrations

```bash
alembic init alembic
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Adding New Features

1. Create feature branch
2. Implement changes
3. Add tests
4. Update documentation
5. Submit pull request

## 📝 License

This project is proprietary software for internal use.

## 🤝 Support

For issues or questions:
- Email: support@example.com
- Documentation: See `/docs` folder
- Issues: GitHub Issues

## 🎯 Roadmap

### Phase 1 (Current)
- ✅ Core receipt processing
- ✅ OCR and LLM integration
- ✅ Basic analytics
- ✅ Export functionality

### Phase 2 (Q1 2025)
- [ ] Multi-user support with roles
- [ ] Advanced duplicate detection
- [ ] Email receipt import
- [ ] Mobile app

### Phase 3 (Q2 2025)
- [ ] Bank integration
- [ ] Automated bookkeeping
- [ ] Advanced ML predictions
- [ ] API for third-party integrations

## 🏆 Credits

Developed based on the comprehensive Product Requirements Document for Dutch freelance administration automation.

---

**Note**: This application is designed specifically for Dutch tax compliance. Consult with a tax professional for official tax advice.