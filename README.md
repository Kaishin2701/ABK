# ABK Tool App

ABK Tool App is a desktop Tkinter application for product listing work. It keeps the functionality from the previous web version, but runs locally as an app.

## Features

- Product Checker: check one or many product URLs, show SKU, issue count, PASS/FAIL, detailed issues, and extracted product JSON log.
- Auto Watermark: select images, choose watermark logo, mode, quality, opacity, rename template, and export WebP files.
- Link Checker: scan multiple URLs, check status, filter live/dead/error results.
- HTML Cleaner: clean pasted HTML by removing wrapper layout tags and unsupported attributes.
- SKU Generator: generate AD, KD, and ADK/KD size SKU variants, copy output, or export CSV.

## Project Structure

```text
ABK_CHECKER_2/
├── app/                  # Desktop GUI and controller layer
├── checker/              # Product test engine and cases
├── config/               # Editable JSON rules
├── data/                 # Reference data
├── scraper/              # Product HTML scraper and parser
├── static/assets/        # Desktop app logo
├── static/watermark/     # Default watermark assets
├── main.py               # Desktop app entry point
└── requirements.txt      # Runtime dependencies
```

## Run Locally

```powershell
pip install -r requirements.txt
python main.py
```

The app uses direct HTML requests for product and link checks. If a website blocks your network, run the app from a network/VPN that can access that website.
