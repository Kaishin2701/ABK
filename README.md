# ABK Product Checker

Web app for checking RFS product listings from a product URL.

## Local Run

```powershell
pip install -r requirements.txt
python main.py
```

Open:

```text
http://localhost:5000
```

## Deploy From GitHub

This project needs a Python backend because the scraper runs server-side. GitHub Pages is static-only and cannot run the Python scraper.

Recommended deployment flow:

1. Push this repo to GitHub.
2. Create a new Web Service on Render.
3. Connect the GitHub repository.
4. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn web_app:app`

`render.yaml` and `Procfile` are included for platform-friendly deployment.
