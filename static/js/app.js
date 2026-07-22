const pageTitle = document.getElementById("pageTitle");
const statusPill = document.getElementById("statusPill");

const fallbackSeverityStyles = {
  CRITICAL: { bg: "#7f1d1d", fg: "#ffffff" },
  MAJOR: { bg: "#dc2626", fg: "#ffffff" },
  WARNING: { bg: "#f97316", fg: "#111827" },
  NOTICE: { bg: "#facc15", fg: "#111827" },
  IMPROVEMENT: { bg: "#38bdf8", fg: "#0f172a" }
};

const apiBaseUrl = ["3000", "5500"].includes(window.location.port)
  ? "http://127.0.0.1:5000"
  : "";

function apiUrl(path) {
  return `${apiBaseUrl}${path}`;
}

function setStatus(text) {
  statusPill.textContent = text;
}

function setupNavigation() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      const tool = button.dataset.tool;
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".tool-view").forEach((view) => {
        const active = view.id === `tool-${tool}`;
        view.classList.toggle("active", active);
        if (active) pageTitle.textContent = view.dataset.title || button.textContent.trim().toUpperCase();
      });
      setStatus("Ready");
    });
  });
}

const urlInput = document.getElementById("urlInput");
const checkButton = document.getElementById("checkButton");
const checkerOutput = document.getElementById("checkerOutput");
const batchResults = document.getElementById("batchResults");
const productResultTableBody = document.querySelector("#productResultTable tbody");
const productDetail = document.getElementById("productDetail");
const logOutput = document.getElementById("logOutput");
const errorText = document.getElementById("errorText");

const summaryResult = document.getElementById("summaryResult");
const summaryIssues = document.getElementById("summaryIssues");
const summarySku = document.getElementById("summarySku");
const summaryReviews = document.getElementById("summaryReviews");

let batchProducts = [];

const severityConfigNode = document.getElementById("severity-config");
let severityStyles = fallbackSeverityStyles;
try {
  const parsed = JSON.parse(severityConfigNode?.textContent || "{}");
  if (Object.keys(parsed).length > 0) severityStyles = parsed;
} catch (_error) {
  severityStyles = fallbackSeverityStyles;
}

function colorsForSeverity(severity) {
  return severityStyles[severity] || { bg: "#facc15", fg: "#111827" };
}

function renderLegend() {}

function parseProductUrls() {
  const urls = urlInput.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return [...new Set(urls)];
}

function issueCountFor(result) {
  if (result.status === "error") return 1;
  return (result.issues || []).length;
}

function updateSummaryForBatch(results) {
  const completed = results.filter((item) => item.status === "done" || item.status === "error");
  const failed = results.filter((item) => item.status === "error" || (item.issues || []).length > 0);
  const totalIssues = results.reduce((sum, item) => sum + issueCountFor(item), 0);
  summaryResult.textContent = completed.length ? `${completed.length}/${results.length}` : "Waiting";
  summaryIssues.textContent = String(totalIssues);
  summarySku.textContent = results.length === 1 ? (results[0].product?.sku || "-") : `${failed.length} Fail`;
  summaryReviews.textContent = results.length === 1 ? (results[0].product?.review_count ?? "-") : `${results.length - failed.length} Pass`;
}

function resetSummary() {
  summaryResult.textContent = "Waiting";
  summaryIssues.textContent = "0";
  summarySku.textContent = "-";
  summaryReviews.textContent = "-";
}

function setBatchMode(message) {
  checkerOutput.classList.add("empty-state");
  checkerOutput.textContent = message;
  batchResults.hidden = false;
  productResultTableBody.textContent = "";
  productDetail.className = "product-detail empty-state";
  productDetail.textContent = "Click a product row to view issue details.";
}

function renderBatchTable(results) {
  productResultTableBody.textContent = "";
  results.forEach((result, index) => {
    const tr = document.createElement("tr");
    tr.className = "product-result-row";
    tr.dataset.index = String(index);
    if (result.status === "checking") tr.classList.add("is-checking");
    if (result.status === "error" || (result.issues || []).length > 0) tr.classList.add("is-fail");
    if (result.status === "done" && !(result.issues || []).length) tr.classList.add("is-pass");

    const urlCell = document.createElement("td");
    const skuCell = document.createElement("td");
    const issuesCell = document.createElement("td");
    const evaluationCell = document.createElement("td");

    urlCell.textContent = result.url;
    skuCell.textContent = result.product?.sku || (result.status === "checking" ? "Checking..." : "-");
    issuesCell.textContent = result.status === "checking" ? "-" : String(issueCountFor(result));
    evaluationCell.textContent = evaluationFor(result);
    evaluationCell.className = evaluationCell.textContent === "PASS" ? "eval-pass" : evaluationCell.textContent === "FAIL" ? "eval-fail" : "";

    tr.append(urlCell, skuCell, issuesCell, evaluationCell);
    tr.addEventListener("click", () => showProductDetail(index));
    productResultTableBody.appendChild(tr);
  });
}

function evaluationFor(result) {
  if (result.status === "checking") return "CHECKING";
  if (result.status === "error") return "FAIL";
  return (result.issues || []).length === 0 ? "PASS" : "FAIL";
}

function showProductDetail(index) {
  const result = batchProducts[index];
  if (!result) return;

  document.querySelectorAll(".product-result-row").forEach((row) => {
    row.classList.toggle("selected", row.dataset.index === String(index));
  });

  productDetail.classList.remove("empty-state");
  productDetail.textContent = "";

  const heading = document.createElement("div");
  heading.className = "detail-heading";
  heading.textContent = `${result.product?.sku || "No SKU"} - ${evaluationFor(result)}${result.status === "error" ? " - Fetch error" : ""}`;
  productDetail.appendChild(heading);

  if (result.error) {
    const error = document.createElement("div");
    error.className = "error-text";
    error.textContent = result.error;
    productDetail.appendChild(error);
  } else {
    renderIssuesInto(productDetail, result.issues || []);
  }

  logOutput.textContent = JSON.stringify({ url: result.url, product: result.product || null, issues: result.issues || [], error: result.error || null }, null, 2);
}

function renderIssuesInto(container, issues) {
  if (!issues.length) {
    const passCard = document.createElement("div");
    passCard.className = "pass-card";
    const passTitle = document.createElement("div");
    passTitle.className = "pass-message";
    passTitle.textContent = "PASS";
    const passCopy = document.createElement("div");
    passCopy.textContent = "No issues were found by the current test cases.";
    passCard.append(passTitle, passCopy);
    container.appendChild(passCard);
    return;
  }

  issues.forEach((issue, index) => {
    const article = document.createElement("article");
    article.className = "issue compact-issue";

    const header = document.createElement("div");
    header.className = "issue-header";

    const severity = document.createElement("div");
    const style = colorsForSeverity(issue.severity);
    severity.className = "issue-severity";
    severity.textContent = issue.severity || "NOTICE";
    severity.style.backgroundColor = style.bg;
    severity.style.color = style.fg;

    const title = document.createElement("h2");
    title.className = "issue-title";
    title.textContent = `${index + 1}. [${issue.code || "NO_CODE"}] ${issue.title || "Unnamed issue"}`;

    const viewMore = document.createElement("button");
    viewMore.className = "view-more-button";
    viewMore.type = "button";
    viewMore.textContent = "View more";

    const meta = document.createElement("div");
    meta.className = "issue-meta issue-meta-collapsed";
    meta.hidden = true;
    meta.append(
      metaLine("Test case", issue.case_name),
      metaLine("Found", issue.found),
      metaLine("Expected", issue.expected),
      metaLine("Explanation", issue.explanation)
    );

    viewMore.addEventListener("click", () => {
      const expanded = !meta.hidden;
      meta.hidden = expanded;
      viewMore.textContent = expanded ? "View more" : "View less";
    });

    header.append(severity, title, viewMore);
    article.append(header, meta);
    container.appendChild(article);
  });
}

function metaLine(label, value) {
  const row = document.createElement("div");
  const labelNode = document.createElement("b");
  labelNode.textContent = `${label}: `;
  row.append(labelNode, document.createTextNode(value || ""));
  return row;
}

async function checkOneProduct(url) {
  try {
    return await checkProductByServer(url);
  } catch (error) {
    if (!shouldTryBrowserProxy(error)) throw error;
    setStatus("Browser proxy");
    return checkProductByBrowserProxy(url);
  }
}

async function checkProductByServer(url) {
  const response = await fetch(apiUrl("/api/check"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });
  return parseJsonResponse(response, "Product check failed.");
}

async function checkProductByBrowserProxy(url) {
  const proxyUrl = `https://corsproxy.io/?${encodeURIComponent(url)}`;
  const htmlResponse = await fetch(proxyUrl, {
    method: "GET",
    headers: { "Accept": "text/html,application/xhtml+xml" }
  });
  if (!htmlResponse.ok) {
    throw new Error(`Browser proxy failed: ${htmlResponse.status} ${htmlResponse.statusText}`);
  }

  const html = await htmlResponse.text();
  if (!html || html.length < 500) {
    throw new Error("Browser proxy returned an empty or invalid product page.");
  }

  const response = await fetch(apiUrl("/api/check-html"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, html })
  });
  return parseJsonResponse(response, "Product HTML check failed.");
}

async function parseJsonResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("The checker API did not return JSON. Make sure the Flask backend is running at http://127.0.0.1:5000.");
  }

  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || fallbackMessage);
  return payload;
}

function shouldTryBrowserProxy(error) {
  const message = String(error?.message || "").toLowerCase();
  return message.includes("403")
    || message.includes("forbidden")
    || message.includes("source site may be blocking")
    || message.includes("scraper_proxy_url");
}

async function runCheck() {
  const urls = parseProductUrls();
  errorText.textContent = "";

  if (!urls.length) {
    errorText.textContent = "Please paste at least one product URL.";
    return;
  }

  const invalidUrl = urls.find((url) => !/^https?:\/\//i.test(url));
  if (invalidUrl) {
    errorText.textContent = `Invalid URL: ${invalidUrl}`;
    return;
  }

  checkButton.disabled = true;
  setStatus("Checking");
  resetSummary();
  logOutput.textContent = "";
  batchProducts = urls.map((url) => ({ url, status: "pending", product: null, issues: [] }));
  setBatchMode(`Checking ${urls.length} product(s)...`);
  renderBatchTable(batchProducts);

  for (let index = 0; index < batchProducts.length; index += 1) {
    batchProducts[index].status = "checking";
    renderBatchTable(batchProducts);
    setStatus(`${index + 1}/${batchProducts.length}`);

    try {
      const payload = await checkOneProduct(batchProducts[index].url);
      batchProducts[index] = {
        ...batchProducts[index],
        status: "done",
        product: payload.product || {},
        issues: payload.issues || []
      };
    } catch (error) {
      batchProducts[index] = {
        ...batchProducts[index],
        status: "error",
        error: error.message,
        product: null,
        issues: []
      };
    }

    renderBatchTable(batchProducts);
    updateSummaryForBatch(batchProducts);
  }

  const failCount = batchProducts.filter((item) => evaluationFor(item) === "FAIL").length;
  checkerOutput.classList.remove("empty-state");
  checkerOutput.textContent = `Finished ${batchProducts.length} product(s): ${batchProducts.length - failCount} PASS, ${failCount} FAIL.`;
  setStatus("Complete");
  checkButton.disabled = false;

  if (batchProducts.length) showProductDetail(0);
}

function setupProductChecker() {
  checkButton.addEventListener("click", runCheck);
  urlInput.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key === "Enter") runCheck();
  });

  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((item) => {
        const isActive = item === button;
        item.classList.toggle("active", isActive);
        item.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === button.dataset.tab);
      });
    });
  });

  renderLegend();
}

setupNavigation();
setupProductChecker();



