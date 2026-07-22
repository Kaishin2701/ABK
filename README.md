# ABK Tool

ABK Tool is a Flask web application for checking and preparing Replica Football Shirt product listings. The app combines the product QA checker with supporting listing utilities in one browser-based dashboard.

## Main Features

- Product Checker: paste one or more product URLs, run all configured test cases, and review PASS/FAIL results per product.
- Detailed issue view: click a product row, then use View more to inspect the test case, found value, expected value, and explanation.
- Auto Watermark: batch process product images in the browser and export WebP files or a ZIP package.
- Link Checker: check multiple URLs through the Flask backend.
- HTML Cleaner: clean pasted HTML by removing unnecessary wrapper tags and unsafe/unneeded attributes.
- SKU Generator: generate size variant SKUs for AD, KD, and ADK/KD product patterns.

## Source Structure

```text
ABK_CHECKER_2/
├── app/                  # Flask app, web routes, and API endpoints
├── checker/              # Test case engine and checker models
│   └── cases/            # Individual product test cases
├── config/               # Editable JSON rules for prices, categories, sizes, descriptions, etc.
├── data/                 # Reference data such as RFS category mapping
├── scraper/              # HTML scraping and parsing logic
├── static/               # CSS, JavaScript, logo, and watermark assets
├── templates/            # Flask HTML template
├── main.py               # Local entry point
├── web_app.py            # Compatibility entry point for gunicorn
├── requirements.txt      # Python dependencies
├── Procfile              # Platform start command
└── render.yaml           # Render deployment config
```

## Scraping Policy

The Product Checker uses HTML page scraping only. It does not use the RFS WooCommerce or WordPress API.

If the source website blocks the Render server IP with `403 Forbidden`, configure a permitted proxy/VPN endpoint with this environment variable:

```text
SCRAPER_PROXY_URL=http://user:password@proxy-host:port
```

The same proxy is used by Product Checker and backend Link Checker requests.

## Local Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the web app:

```powershell
python main.py
```

Open:

```text
http://127.0.0.1:5000/
```

## API Endpoints

- `GET /` renders the web dashboard.
- `GET /health` returns a simple health check.
- `POST /api/check` checks one product URL.
- `POST /api/link-check` checks one generic URL for the Link Checker tool.

## Deploy From GitHub

This project needs a Python backend because the scraper and checker run server-side. GitHub Pages is static-only and cannot run the Python scraper.

Recommended deployment flow:

1. Push this repository to GitHub.
2. Create a new Web Service on Render or another Python-friendly host.
3. Connect the GitHub repository.
4. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn --workers 2 --threads 4 --timeout 120 web_app:app`

`render.yaml` and `Procfile` are included for deployment-friendly hosting.
