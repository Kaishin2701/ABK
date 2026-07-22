let inputFiles = [];
let wmImg = null;
let isCheckingLinks = false;

function toolLog(message) {
  const box = document.getElementById("log-box");
  const time = new Date().toLocaleTimeString();
  box.value += `[${time}] ${message}\n`;
  box.scrollTop = box.scrollHeight;
}

function handleFileSelect(event) {
  const newFiles = Array.from(event.target.files || []);
  inputFiles = [...inputFiles, ...newFiles];
  renderGallery();
  toolLog(`Added ${newFiles.length} image(s).`);
}

function handleDrop(event) {
  event.preventDefault();
  document.getElementById("gallery-area").classList.remove("drag-over");
  const newFiles = Array.from(event.dataTransfer.files || []).filter((file) => file.type.startsWith("image/"));
  inputFiles = [...inputFiles, ...newFiles];
  renderGallery();
  toolLog(`Added ${newFiles.length} image(s).`);
}

function handleWmSelect(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  document.getElementById("wm-path-display").value = file.name;
  const reader = new FileReader();
  reader.onload = (readerEvent) => {
    wmImg = new Image();
    wmImg.src = readerEvent.target.result;
    toolLog(`Loaded watermark: ${file.name}`);
  };
  reader.readAsDataURL(file);
}

function renderGallery() {
  const area = document.getElementById("gallery-area");
  area.textContent = "";
  if (inputFiles.length === 0) {
    const placeholder = document.createElement("p");
    placeholder.id = "gallery-placeholder";
    placeholder.textContent = "Drag images here or select files.";
    area.appendChild(placeholder);
    return;
  }
  inputFiles.forEach((file) => {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    img.className = "g-thumb";
    img.alt = file.name;
    area.appendChild(img);
  });
}

function clearGallery() {
  inputFiles = [];
  document.getElementById("inp-files").value = "";
  renderGallery();
  toolLog("Cleared image gallery.");
}

async function startWatermarkProcess() {
  if (!inputFiles.length) {
    alert("Please select at least one image.");
    return;
  }

  const btn = document.getElementById("btn-start-wm");
  btn.disabled = true;
  btn.textContent = "PROCESSING...";
  document.getElementById("log-box").value = "";
  document.getElementById("p-bar-fill").style.width = "0%";

  const mode = document.getElementById("sel-mode").value;
  const opacity = Number(document.getElementById("rng-opacity").value) / 100;
  const quality = Number(document.getElementById("rng-quality").value) / 100;
  const renameTpl = document.getElementById("inp-rename").value || "{default name}";
  const processedFiles = [];

  toolLog(`Starting ${inputFiles.length} image(s).`);
  if (!wmImg) toolLog("No watermark selected. Images will only be converted to WebP.");

  for (let i = 0; i < inputFiles.length; i += 1) {
    const file = inputFiles[i];
    try {
      const blob = await processImage(file, mode, opacity, quality);
      const baseName = file.name.replace(/\.[^.]+$/, "");
      const name = `${renameTpl.replace("{default name}", baseName).replace(/[<>:"/\\|?*]/g, "_")}.webp`;
      processedFiles.push({ blob, name });
      toolLog(`OK: ${file.name} -> ${name}`);
    } catch (error) {
      toolLog(`Error: ${file.name} - ${error.message || error}`);
    }
    document.getElementById("p-bar-fill").style.width = `${Math.round(((i + 1) / inputFiles.length) * 100)}%`;
    document.getElementById("status-lbl").textContent = `${i + 1}/${inputFiles.length}`;
    await new Promise((resolve) => setTimeout(resolve, 60));
  }

  await downloadProcessedFiles(processedFiles);
  toolLog("Done.");
  btn.disabled = false;
  btn.textContent = "START PROCESSING";
}

function processImage(file, mode, opacity, quality) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = (event) => {
      const img = new Image();
      img.onerror = reject;
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);

        if (wmImg) {
          ctx.globalAlpha = opacity;
          const width = canvas.width;
          const height = canvas.height;
          const ratio = wmImg.width / wmImg.height;

          if (mode === "Fullscreen") {
            ctx.drawImage(wmImg, 0, 0, width, height);
          } else if (mode === "Bottom-right") {
            const wmWidth = Math.max(Math.floor(width * 0.2), 50);
            const wmHeight = Math.floor(wmWidth / ratio);
            ctx.drawImage(wmImg, width - wmWidth - 20, height - wmHeight - 20, wmWidth, wmHeight);
          } else {
            const wmWidth = Math.floor(width * 0.25);
            const wmHeight = Math.floor(wmWidth / ratio);
            for (let x = 0; x < width + wmWidth; x += wmWidth + 50) {
              for (let y = 0; y < height + wmHeight; y += wmHeight + 50) {
                ctx.drawImage(wmImg, x, y, wmWidth, wmHeight);
              }
            }
          }
        }

        canvas.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error("Could not export image."));
        }, "image/webp", quality);
      };
      img.src = event.target.result;
    };
    reader.readAsDataURL(file);
  });
}

async function downloadProcessedFiles(files) {
  if (!files.length) return;
  if (files.length === 1) {
    const url = URL.createObjectURL(files[0].blob);
    triggerDownload(url, files[0].name);
    return;
  }
  if (!window.JSZip) {
    alert("JSZip is not loaded. Multiple image download is unavailable.");
    return;
  }
  const zip = new JSZip();
  files.forEach(({ blob, name }) => zip.file(name, blob));
  const zipBlob = await zip.generateAsync({ type: "blob" });
  triggerDownload(URL.createObjectURL(zipBlob), "processed_images.zip");
}

function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.getElementById("download-area").appendChild(a);
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function setupWatermark() {
  const gallery = document.getElementById("gallery-area");
  document.getElementById("inp-files").addEventListener("change", handleFileSelect);
  document.getElementById("inp-wm").addEventListener("change", handleWmSelect);
  document.getElementById("btn-select-wm").addEventListener("click", () => document.getElementById("inp-wm").click());
  document.getElementById("btn-clear-gallery").addEventListener("click", clearGallery);
  document.getElementById("btn-start-wm").addEventListener("click", startWatermarkProcess);
  document.getElementById("rng-quality").addEventListener("input", (event) => document.getElementById("lbl-quality").textContent = `Quality: ${event.target.value}`);
  document.getElementById("rng-opacity").addEventListener("input", (event) => document.getElementById("lbl-opacity").textContent = `Opacity: ${event.target.value}%`);
  gallery.addEventListener("dragover", (event) => { event.preventDefault(); gallery.classList.add("drag-over"); });
  gallery.addEventListener("dragleave", () => gallery.classList.remove("drag-over"));
  gallery.addEventListener("drop", handleDrop);
}

async function startLinkCheck() {
  const raw = document.getElementById("inp-urls").value;
  const urls = raw.match(/https?:\/\/[^\s<>'"]+/g) || [];
  if (!urls.length) {
    alert("No URLs found.");
    return;
  }

  const tbody = document.querySelector("#tbl-links tbody");
  tbody.textContent = "";
  document.getElementById("link-p-bar").style.width = "0%";
  document.getElementById("btn-check-link").disabled = true;
  document.getElementById("btn-stop-link").disabled = false;
  isCheckingLinks = true;

  const stats = { live: 0, dead: 0, error: 0 };
  updateLinkStats(stats);

  for (let i = 0; i < urls.length; i += 1) {
    if (!isCheckingLinks) break;
    const url = urls[i];
    const row = addLinkRow("...", url, "Checking...");

    try {
      const response = await fetch(apiUrl("/api/link-check"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const payload = await response.json();
      row.remove();
      addLinkRow(payload.status_code || "ERR", url, payload.message || "Checked");
      if (payload.ok) stats.live += 1;
      else if (payload.status_code === 404) stats.dead += 1;
      else stats.error += 1;
    } catch (error) {
      row.remove();
      addLinkRow("ERR", url, error.message || "Request failed");
      stats.error += 1;
    }

    updateLinkStats(stats);
    document.getElementById("link-p-bar").style.width = `${Math.round(((i + 1) / urls.length) * 100)}%`;
    document.getElementById("link-status").textContent = `Checking ${i + 1}/${urls.length}`;
  }

  isCheckingLinks = false;
  document.getElementById("btn-check-link").disabled = false;
  document.getElementById("btn-stop-link").disabled = true;
  document.getElementById("link-status").textContent = "Done.";
  applyLinkFilter();
}

function addLinkRow(code, url, message) {
  const tbody = document.querySelector("#tbl-links tbody");
  const tr = document.createElement("tr");
  const statusCell = document.createElement("td");
  const urlCell = document.createElement("td");
  const messageCell = document.createElement("td");
  const codeText = String(code);
  let color = "#38bdf8";
  if (/^2/.test(codeText)) color = "#00ff88";
  else if (codeText === "404" || codeText === "ERR") color = "#ff5555";
  statusCell.textContent = codeText;
  statusCell.style.color = color;
  statusCell.style.fontWeight = "900";
  urlCell.textContent = url;
  messageCell.textContent = message;
  messageCell.style.color = color;
  tr.append(statusCell, urlCell, messageCell);
  tbody.appendChild(tr);
  return tr;
}

function updateLinkStats(stats) {
  document.getElementById("link-stats").textContent = `Live: ${stats.live} | Dead: ${stats.dead} | Error: ${stats.error}`;
}

function applyLinkFilter() {
  const filter = document.getElementById("sel-filter").value;
  document.querySelectorAll("#tbl-links tbody tr").forEach((row) => {
    const code = row.cells[0].textContent;
    const show = filter === "Show All"
      || (filter === "Live (200)" && code.startsWith("2"))
      || (filter === "Dead (404)" && code === "404")
      || (filter === "Error" && !code.startsWith("2") && code !== "404");
    row.style.display = show ? "" : "none";
  });
}

function setupLinkChecker() {
  document.getElementById("btn-check-link").addEventListener("click", startLinkCheck);
  document.getElementById("btn-stop-link").addEventListener("click", () => isCheckingLinks = false);
  document.getElementById("sel-filter").addEventListener("change", applyLinkFilter);
}

function runHtmlClean() {
  const rawInput = document.getElementById("html-in").value;
  const outputBox = document.getElementById("html-out");
  if (!rawInput.trim()) {
    alert("Please paste HTML into the input box.");
    return;
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(rawInput, "text/html");
  const body = doc.body;
  body.querySelectorAll("div, section, article, header, footer, aside, main, nav").forEach((el) => {
    while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
    el.remove();
  });

  const allowedAttrs = ["style", "href", "target", "src", "alt", "width", "height", "colspan", "rowspan"];
  body.querySelectorAll("*").forEach((el) => {
    Array.from(el.attributes).forEach((attr) => {
      if (!allowedAttrs.includes(attr.name)) el.removeAttribute(attr.name);
    });
  });

  body.querySelectorAll("span").forEach((span) => {
    if (span.attributes.length === 0) {
      while (span.firstChild) span.parentNode.insertBefore(span.firstChild, span);
      span.remove();
    }
  });

  body.querySelectorAll("p, h1, h2, h3, h4, h5, h6, li, ul, ol, blockquote").forEach((el) => {
    if (!el.textContent.trim() && !el.querySelector("img, br, hr, iframe")) el.remove();
  });

  outputBox.value = body.innerHTML.trim();
}

async function copyCleanResult() {
  const output = document.getElementById("html-out");
  if (!output.value) return;
  await navigator.clipboard.writeText(output.value);
}

function setupHtmlCleaner() {
  document.getElementById("btn-clean").addEventListener("click", runHtmlClean);
  document.getElementById("btn-copy-html").addEventListener("click", copyCleanResult);
}

const skuConfig = {
  kidsSizes: ["16", "18", "20", "22", "24", "26", "28"],
  kidsLabels: ["(3-4 yrs)", "(4-5 yrs)", "(5-6 yrs)", "(7-8 yrs)", "(8-9 yrs)", "(10-11 yrs)", "(12-13 yrs)"],
  adultSizes: ["S", "M", "L", "XL", "XXL"]
};

function generateSkuVariants(baseCode) {
  const variants = [];
  if (baseCode.includes("ADK/KD")) {
    skuConfig.kidsSizes.forEach((size, index) => variants.push(`${baseCode}_${size} ${skuConfig.kidsLabels[index]}`));
    skuConfig.adultSizes.forEach((size) => variants.push(`${baseCode}_${size}`));
  } else if (baseCode.includes("KD")) {
    skuConfig.kidsSizes.forEach((size, index) => variants.push(`${baseCode}_${size} ${skuConfig.kidsLabels[index]}`));
  } else if (baseCode.includes("AD")) {
    skuConfig.adultSizes.forEach((size) => variants.push(`${baseCode}_${size}`));
  }
  return variants;
}

function skuGenerate() {
  const baseCode = document.getElementById("sku-base-code").value.trim();
  const output = document.getElementById("sku-output");
  const variants = generateSkuVariants(baseCode);
  output.value = variants.join("\n");
  document.getElementById("sku-info").textContent = variants.length
    ? `Generated ${variants.length} SKU variant(s).`
    : "No variants generated. Use AD, KD, or ADK/KD in the base SKU.";
}

async function skuCopyAll() {
  const output = document.getElementById("sku-output");
  if (output.value) await navigator.clipboard.writeText(output.value);
}

function skuClearForm() {
  document.getElementById("sku-base-code").value = "";
  document.getElementById("sku-output").value = "";
  document.getElementById("sku-info").textContent = "Supported patterns: AD, KD, ADK/KD.";
}

function skuExportCsv() {
  const rows = document.getElementById("sku-output").value.split("\n").filter(Boolean);
  if (!rows.length) return;
  const csv = `SKU\n${rows.map((row) => `"${row.replaceAll('"', '""')}"`).join("\n")}`;
  triggerDownload(URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })), "sku_variants.csv");
}

function setupSkuGenerator() {
  document.getElementById("btn-generate-sku").addEventListener("click", skuGenerate);
  document.getElementById("sku-base-code").addEventListener("keydown", (event) => { if (event.key === "Enter") skuGenerate(); });
  document.getElementById("btn-copy-sku").addEventListener("click", skuCopyAll);
  document.getElementById("btn-export-sku").addEventListener("click", skuExportCsv);
  document.getElementById("btn-clear-sku").addEventListener("click", skuClearForm);
}

setupWatermark();
setupLinkChecker();
setupHtmlCleaner();
setupSkuGenerator();
