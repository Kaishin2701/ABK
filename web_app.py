from __future__ import annotations

import os
from typing import Any

import requests
from flask import Flask, jsonify, make_response, render_template, request

from app.controller import check_product_url
from checker.config import load_json_config
from scraper.product_scraper import is_valid_url

app = Flask(__name__)


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


@app.route("/api/link-check", methods=["POST", "OPTIONS"])
def link_check():
    if request.method == "OPTIONS":
        return make_response("", 204)

    payload: dict[str, Any] = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL", "ok": False, "status_code": None, "message": "Invalid URL"}), 400

    headers = {"User-Agent": "ABK-Tool-LinkChecker/1.0"}
    try:
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=12)
        if response.status_code in {403, 405}:
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=12, stream=True)
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


if __name__ == "__main__":
    main()
