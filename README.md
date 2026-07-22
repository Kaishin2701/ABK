# ABK Product Checker App

ABK Product Checker is a desktop Tkinter application for checking Replica Football Shirt product listings from product URLs.

The project is now App-first and contains only the desktop application plus the scraper/checker core.

## Features

- Check one or many product URLs in a single run.
- Display one result row per product with URL, SKU, issue count, and PASS/FAIL evaluation.
- Click a result row to inspect detailed issues and extracted product data.
- Extract product information from HTML pages:
  - Title
  - SKU
  - Tags
  - Categories
  - Short description
  - Review count
  - Base price and size-level prices/SKUs
  - Global form options
  - Image count and image metadata
  - Long description
  - Additional information
- Run configurable test cases from `checker/cases/`.
- Keep rules editable in JSON under `config/`.

## Project Structure

```text
ABK_CHECKER_2/
├── app/                  # Desktop GUI and controller layer
├── checker/              # Test engine, issue model, and cases
│   └── cases/            # Individual product test cases
├── config/               # Editable JSON rules
├── data/                 # Reference category data
├── scraper/              # HTML scraper and parser
├── tests/                # Test files
├── main.py               # Desktop app entry point
└── requirements.txt      # Runtime dependencies
```

## Local Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the app:

```powershell
python main.py
```

## Notes

The scraper uses HTML page requests only. If a source website blocks a server/datacenter IP, run the desktop app from a network that can access that website, or configure an approved proxy through:

```text
SCRAPER_PROXY_URL=http://user:password@proxy-host:port
```

