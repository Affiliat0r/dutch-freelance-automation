# Setup Instructions

## First Time Setup

When you clone this repository for the first time, follow these steps to set up your local environment:

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy the `.env.example` file to `.env` and configure your settings:

```bash
cp .env.example .env
```

**Required configuration:**
- `GEMINI_API_KEY`: Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

**Optional configuration:**
- `DATABASE_URL`: PostgreSQL connection string (defaults to SQLite if not set)
- `SECRET_KEY`: Security key for authentication (generate a secure random string)

### 3. Initialize Data Files

The application will automatically create the necessary JSON data files on first run. However, if you want to initialize them manually, you can copy the template files:

**Receipt Data:**
```bash
cp receipt_data/receipts_metadata.json.template receipt_data/receipts_metadata.json
```

**Invoice Data:**
```bash
cp invoice_data/invoices_metadata.json.template invoice_data/invoices_metadata.json
cp invoice_data/clients.json.template invoice_data/clients.json
cp invoice_data/invoice_settings.json.template invoice_data/invoice_settings.json
```

**Note:** The application will automatically create these files with default values if they don't exist, so manual copying is optional.

### 4. Run the Application

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## Data Storage

This application uses **local file storage** by default:
- **Receipts:** Stored in `receipt_data/receipts/`
- **Receipt metadata:** `receipt_data/receipts_metadata.json`
- **Invoices:** Stored in `invoice_data/invoices/`
- **Invoice metadata:** `invoice_data/invoices_metadata.json`
- **Client data:** `invoice_data/clients.json`
- **Invoice settings:** `invoice_data/invoice_settings.json`

**Important:** These data files are excluded from Git via `.gitignore` to protect your privacy. Each user will have their own separate data.

## Directory Structure

After setup, your directory structure should look like this:

```
Administration Automation/
├── receipt_data/
│   ├── receipts/              # Your receipt files (PDF, PNG, JPG)
│   └── receipts_metadata.json # Receipt metadata (auto-created)
├── invoice_data/
│   ├── invoices/              # Generated invoice PDFs
│   ├── logos/                 # Company logo files
│   ├── invoices_metadata.json # Invoice metadata (auto-created)
│   ├── clients.json          # Client information (auto-created)
│   └── invoice_settings.json # Invoice settings (auto-created)
└── ...
```

## Database Setup (Optional)

If you want to use PostgreSQL instead of local file storage:

1. Install PostgreSQL
2. Create a database:
   ```sql
   CREATE DATABASE admin_automation;
   ```
3. Update `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/admin_automation
   ```
4. Run the application - tables will be created automatically

## Troubleshooting

### "GEMINI_API_KEY not set" error
- Make sure you've created a `.env` file and added your API key
- Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### "Directory not found" errors
- The application should create directories automatically
- If issues persist, create them manually:
  ```bash
  mkdir -p receipt_data/receipts
  mkdir -p invoice_data/invoices
  mkdir -p invoice_data/logos
  ```

### Data files not being created
- Check file permissions in the project directory
- Ensure the application has write access to `receipt_data/` and `invoice_data/` directories

## Privacy and Data Security

- **Your data stays local:** All receipt and invoice data is stored locally on your machine
- **Not tracked in Git:** Personal data files are excluded via `.gitignore`
- **Gemini API:** Receipt processing uses Google Gemini API - receipt images are sent to Google for text extraction
- **Database option:** If using PostgreSQL, ensure proper security measures for your database

## Need Help?

- Check the main [README.md](README.md) for detailed documentation
- Review [CLAUDE.md](CLAUDE.md) for development guidelines
- Open an issue on GitHub for bugs or feature requests
