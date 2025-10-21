# Deployment Guide - Streamlit Cloud

This guide explains how to deploy the Dutch Freelance Administration Automation app to Streamlit Community Cloud.

## Prerequisites

1. **GitHub Account**: Your code is already on GitHub at `https://github.com/Affiliat0r/dutch-freelance-automation.git`
2. **Streamlit Cloud Account**: Sign up at [share.streamlit.io](https://share.streamlit.io) using your GitHub account
3. **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Deployment Steps

### Step 1: Sign Up for Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "Continue with GitHub"
3. Authorize Streamlit to access your GitHub repositories

### Step 2: Deploy Your App

1. Click "New app" button
2. Fill in the deployment form:
   - **Repository**: `Affiliat0r/dutch-freelance-automation`
   - **Branch**: `master`
   - **Main file path**: `app.py`
   - **App URL**: Choose a custom subdomain (e.g., `dutch-freelance-admin`)

3. Click "Advanced settings" to configure secrets

### Step 3: Configure Secrets

In the "Secrets" section, paste the following (replace with your actual values):

```toml
GEMINI_API_KEY = "your-actual-gemini-api-key-here"
SECRET_KEY = "your-secret-key-at-least-32-chars-long"
```

**Important Notes:**
- The `GEMINI_API_KEY` is **required** for the app to function
- Generate a secure `SECRET_KEY` (you can use: `python -c "import secrets; print(secrets.token_hex(32))"`)
- Database defaults to SQLite (stored in Streamlit Cloud's ephemeral storage)
- For persistent database, add `DATABASE_URL` with a PostgreSQL connection string

### Step 4: Deploy

1. Click "Deploy!"
2. Wait 2-5 minutes for the app to build and start
3. Your app will be available at: `https://your-subdomain.streamlit.app`

## Post-Deployment

### Data Persistence

**Important:** Streamlit Cloud uses ephemeral storage. This means:
- Files in `receipt_data/` and `invoice_data/` will be reset on app restarts
- SQLite database will be lost on restarts

**For production use, you should:**
1. Set up a PostgreSQL database (free options: [Neon](https://neon.tech), [Supabase](https://supabase.com))
2. Add `DATABASE_URL` to secrets
3. Consider using cloud storage (S3, Google Cloud Storage) for receipt/invoice files

### Monitoring

- View logs: Click "Manage app" → "Logs"
- Restart app: Click "Manage app" → "Reboot app"
- Update secrets: Click "Manage app" → "Settings" → "Secrets"

### Updating the App

The app auto-deploys when you push to the `master` branch on GitHub:

```bash
git add .
git commit -m "Your changes"
git push origin master
```

Streamlit Cloud will automatically rebuild and redeploy within 1-2 minutes.

## Troubleshooting

### Build Failures

**Error: Missing system packages**
- Check [packages.txt](packages.txt) contains all required system packages
- The file is already configured with tesseract and OpenCV dependencies

**Error: Python package installation fails**
- Check [requirements.txt](requirements.txt) for version conflicts
- Try pinning specific versions

**Error: Import errors**
- Ensure all modules are in the repository
- Check that `__init__.py` files exist in package directories

### Runtime Errors

**Error: "GEMINI_API_KEY not found"**
- Go to "Manage app" → "Settings" → "Secrets"
- Add your `GEMINI_API_KEY`
- Reboot the app

**Error: Database connection fails**
- If using PostgreSQL, verify `DATABASE_URL` is correct
- For SQLite (default), no configuration needed

**Error: File upload fails**
- Check Streamlit Cloud's file size limits (200MB per app)
- Verify `receipt_data/` and `invoice_data/` directories exist

### Performance Issues

**App is slow or times out**
- Gemini API calls can be slow for large batches
- Consider reducing batch sizes
- Check Gemini API quota limits

**Out of memory**
- Streamlit Cloud free tier has 1GB RAM limit
- Optimize image processing (reduce resolution before OCR)
- Clear session state periodically

## Limits - Streamlit Community Cloud (Free Tier)

- **Resources**: 1 GB RAM, 2 CPU cores
- **Apps**: Up to 3 apps per account
- **Storage**: No persistent storage (use external database)
- **Bandwidth**: Unlimited
- **Uptime**: Apps sleep after inactivity, wake on request

## Upgrading to Paid Plans

For production use with more resources:
- **Streamlit Cloud Teams**: $250/month (more apps, resources, support)
- Or deploy to your own infrastructure (AWS, GCP, Azure, Heroku)

## Security Recommendations

1. **Never commit secrets** - Already configured in [.gitignore](.gitignore)
2. **Use strong SECRET_KEY** - Generate with `secrets.token_hex(32)`
3. **Enable authentication** - Uncomment auth code in [app.py](app.py) before production
4. **HTTPS only** - Streamlit Cloud provides this automatically
5. **Regular updates** - Keep dependencies updated for security patches

## Support

- **Streamlit Docs**: [docs.streamlit.io](https://docs.streamlit.io)
- **Community Forum**: [discuss.streamlit.io](https://discuss.streamlit.io)
- **GitHub Issues**: Report bugs in your repository
