from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, make_response, render_template, request

from app.controller import check_product_url
from checker.config import load_json_config
from scraper.product_scraper import is_valid_url

app = Flask(__name__, template_folder="../templates", static_folder="../static")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.get("/")
def index():
    return render_template(
        "index.html",
        severity_styles=load_json_config("severity_styles.json"),
    )


@app.route("/api/check", methods=["POST", "OPTIONS"])
def check_product():
    if request.method == "OPTIONS":
        return make_response("", 204)

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()

    if not is_valid_url(url):
        return jsonify({"error": "Please enter a valid URL starting with http:// or https://"}), 400

    try:
        product_data, issues = check_product_url(url)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"product": product_data, "issues": issues})


def _is_current_app_url(url: str) -> bool:
    target = urlparse(url)
    current = urlparse(request.host_url)
    forwarded_host = request.headers.get("X-Forwarded-Host", "").split(",", 1)[0].strip()
    target_host = (target.netloc or "").lower()
    current_hosts = {current.netloc.lower(), (request.host or "").lower()}
    if forwarded_host:
        current_hosts.add(forwarded_host.lower())
    return target_host in current_hosts


def _check_internal_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    if path.startswith("/api/link-check"):
        return {
            "ok": True,
            "status_code": 200,
            "message": "OK (internal endpoint skipped to avoid recursive self-check)",
            "final_url": url,
        }

    with app.test_client() as client:
        response = client.get(path, headers={"Host": request.host or parsed.netloc})

    return {
        "ok": 200 <= response.status_code < 400,
        "status_code": response.status_code,
        "message": response.status or "OK",
        "final_url": url,
    }


@app.route("/api/link-check", methods=["POST", "OPTIONS"])
def link_check():
    if request.method == "OPTIONS":
        return make_response("", 204)

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL", "ok": False, "status_code": None, "message": "Invalid URL"}), 400

    if _is_current_app_url(url):
        return jsonify(_check_internal_url(url))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=8)
        if response.status_code in {403, 405}:
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=8, stream=True)
        status_code = response.status_code
        return jsonify(
            {
                "ok": 200 <= status_code < 400,
                "status_code": status_code,
                "message": response.reason or "OK",
                "final_url": response.url,
            }
        )
    except requests.RequestException as exc:
        return jsonify({"ok": False, "status_code": None, "message": str(exc)}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


def main() -> None:
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
