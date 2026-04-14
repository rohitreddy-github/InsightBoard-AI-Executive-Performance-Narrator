const form = document.getElementById("report-form");
const submitButton = document.getElementById("submit-button");
const loadingIndicator = document.getElementById("loading-indicator");
const validationMessage = document.getElementById("validation-message");
const errorPanel = document.getElementById("error-panel");
const errorMessage = document.getElementById("error-message");
const resultsPanel = document.getElementById("results-panel");

const resultTitle = document.getElementById("result-title");
const resultMeta = document.getElementById("result-meta");
const executiveSummary = document.getElementById("executive-summary");
const recommendedActions = document.getElementById("recommended-actions");
const anomalyCommentary = document.getElementById("anomaly-commentary");
const trendNarrative = document.getElementById("trend-narrative");
const processingSummary = document.getElementById("processing-summary");
const metricSnapshots = document.getElementById("metric-snapshots");
const chartImagePreview = document.getElementById("chart-image-preview");
const chartEmptyState = document.getElementById("chart-empty-state");
const chartMeta = document.getElementById("chart-meta");

const csvFileInput = document.getElementById("csv-file");
const chartImageInput = document.getElementById("chart-image");

function showValidation(message) {
  validationMessage.textContent = message;
  validationMessage.classList.remove("hidden");
}

function clearValidation() {
  validationMessage.textContent = "";
  validationMessage.classList.add("hidden");
}

function showError(message) {
  errorMessage.textContent = message;
  errorPanel.classList.remove("hidden");
}

function clearError() {
  errorMessage.textContent = "";
  errorPanel.classList.add("hidden");
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  loadingIndicator.classList.toggle("hidden", !isLoading);
}

function validateFiles() {
  const csvFile = csvFileInput.files[0];
  const chartFile = chartImageInput.files[0];

  if (!csvFile) {
    showValidation("Please choose a KPI CSV file before generating a report.");
    return false;
  }

  const csvName = csvFile.name.toLowerCase();
  if (!csvName.endsWith(".csv")) {
    showValidation("The KPI upload must be a .csv file.");
    return false;
  }

  if (chartFile && !chartFile.type.startsWith("image/")) {
    showValidation("The optional chart upload must be an image file.");
    return false;
  }

  clearValidation();
  return true;
}

function renderList(target, items, emptyMessage) {
  target.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = emptyMessage;
    target.appendChild(li);
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    target.appendChild(li);
  });
}

function renderProcessingSummary(report) {
  const rows = [
    ["Records analyzed", report.records_analyzed],
    ["Periods analyzed", report.periods_analyzed],
    ["Aggregation", report.preprocessing_summary?.aggregation_granularity ?? "N/A"],
    ["Missing strategy", report.preprocessing_summary?.missing_value_strategy ?? "N/A"],
    ["Duplicates removed", report.preprocessing_summary?.exact_duplicate_rows_removed ?? "N/A"],
    ["Values imputed", report.preprocessing_summary?.missing_values_imputed ?? "N/A"],
  ];

  processingSummary.innerHTML = rows
    .map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`)
    .join("");
}

function formatNumber(value) {
  return typeof value === "number"
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value)
    : "N/A";
}

function renderMetricSnapshots(snapshots) {
  metricSnapshots.innerHTML = "";

  if (!Array.isArray(snapshots) || snapshots.length === 0) {
    metricSnapshots.innerHTML = "<p>No metric snapshots were returned.</p>";
    return;
  }

  snapshots.forEach((snapshot) => {
    const article = document.createElement("article");
    article.className = "metric-card";

    const direction = snapshot.trend_direction || "flat";
    article.innerHTML = `
      <div class="metric-card-header">
        <span>${snapshot.metric}</span>
        <span class="trend-badge trend-${direction}">${direction}</span>
      </div>
      <div class="metric-card-meta">
        <span>Latest: ${formatNumber(snapshot.latest_value)}</span>
        <span>Previous: ${formatNumber(snapshot.previous_value)}</span>
        <span>Change: ${formatNumber(snapshot.absolute_change)}</span>
        <span>Mean: ${formatNumber(snapshot.mean_value)}</span>
      </div>
    `;
    metricSnapshots.appendChild(article);
  });
}

function renderChart(report) {
  const hasChart = Boolean(report.chart_base64 && report.chart_mime_type);
  if (!hasChart) {
    chartImagePreview.classList.add("hidden");
    chartImagePreview.removeAttribute("src");
    chartEmptyState.classList.remove("hidden");
    chartMeta.textContent = "No chart payload was returned by the API.";
    return;
  }

  chartImagePreview.src = `data:${report.chart_mime_type};base64,${report.chart_base64}`;
  chartImagePreview.classList.remove("hidden");
  chartEmptyState.classList.add("hidden");
  chartMeta.textContent = `${report.chart_explanation?.summary ?? "Chart available"} (${report.chart_mime_type})`;
}

function renderReport(report) {
  resultTitle.textContent = report.report_title || "Executive Report";
  resultMeta.textContent = `${report.source_name} • ${report.periods_analyzed} periods • ${report.records_analyzed} records`;
  executiveSummary.textContent = report.executive_summary || "No executive summary returned.";

  renderList(
    recommendedActions,
    report.recommended_actions,
    "No recommended actions were returned.",
  );
  renderList(
    anomalyCommentary,
    report.anomaly_commentary,
    "No anomaly commentary was returned.",
  );
  renderList(
    trendNarrative,
    report.trend_narrative,
    "No trend narrative was returned.",
  );

  renderProcessingSummary(report);
  renderMetricSnapshots(report.metric_snapshots);
  renderChart(report);

  resultsPanel.classList.remove("hidden");
}

async function submitReport(event) {
  event.preventDefault();
  clearError();

  if (!validateFiles()) {
    return;
  }

  const formData = new FormData(form);

  try {
    setLoading(true);
    const response = await fetch("/api/v1/generate-report", {
      method: "POST",
      body: formData,
    });

    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
      ? await response.json()
      : { detail: "The server returned a non-JSON response." };

    if (!response.ok) {
      const detail = typeof body.detail === "string"
        ? body.detail
        : "Report generation failed. Please review the upload and try again.";
      throw new Error(detail);
    }

    renderReport(body);
    resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(error instanceof Error ? error.message : "Unexpected error while generating the report.");
  } finally {
    setLoading(false);
  }
}

csvFileInput.addEventListener("change", validateFiles);
chartImageInput.addEventListener("change", validateFiles);
form.addEventListener("submit", submitReport);
