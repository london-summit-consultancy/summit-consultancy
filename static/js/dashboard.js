/* Analytics dashboard — renders Chart.js + Plotly from server-aggregated JSON.
   Data arrives via <script type="application/json"> (Django json_script), which
   is safely escaped; we only ever read numbers/enum labels, never raw PII. */
(function () {
  "use strict";

  function readJSON(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  var css = getComputedStyle(document.documentElement);
  var brand = (css.getPropertyValue("--color-brand") || "#f59e0b").trim();
  var ink = (css.getPropertyValue("--color-ink-muted") || "#57534e").trim();
  var palette = ["#94a3b8", brand, "#16a34a", "#dc2626", "#a8a29e"];

  var status = readJSON("chart-status");
  var sector = readJSON("chart-sector");
  var monthly = readJSON("chart-monthly");
  var inquiryStatus = readJSON("chart-inquiry-status");
  var buyerType = readJSON("chart-buyer-type");
  var inquiryMonthly = readJSON("chart-inquiry-monthly");
  var sectorCompare = readJSON("chart-sector-compare");
  var completionStatus = readJSON("chart-completion-status");
  var serviceDemand = readJSON("chart-service-demand");

  if (window.Chart) {
    Chart.defaults.color = ink;
    Chart.defaults.font.family = "Inter, sans-serif";

    if (status && document.getElementById("statusChart")) {
      new Chart(document.getElementById("statusChart"), {
        type: "doughnut",
        data: { labels: status.labels, datasets: [{ data: status.values, backgroundColor: palette }] },
        options: { plugins: { legend: { position: "bottom" } }, cutout: "62%" },
      });
    }

    if (sector && document.getElementById("sectorChart")) {
      new Chart(document.getElementById("sectorChart"), {
        type: "bar",
        data: {
          labels: sector.labels,
          datasets: [{ label: "Pipeline £", data: sector.values, backgroundColor: brand, borderRadius: 6 }],
        },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
      });
    }

    if (inquiryStatus && document.getElementById("inquiryStatusChart")) {
      new Chart(document.getElementById("inquiryStatusChart"), {
        type: "bar",
        data: {
          labels: inquiryStatus.labels,
          datasets: [{ data: inquiryStatus.values, backgroundColor: brand, borderRadius: 6 }],
        },
        options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } },
      });
    }

    if (buyerType && document.getElementById("buyerTypeChart")) {
      new Chart(document.getElementById("buyerTypeChart"), {
        type: "doughnut",
        data: { labels: buyerType.labels, datasets: [{ data: buyerType.values, backgroundColor: palette }] },
        options: { plugins: { legend: { position: "bottom" } }, cutout: "62%" },
      });
    }

    if (sectorCompare && document.getElementById("sectorCompareChart")) {
      new Chart(document.getElementById("sectorCompareChart"), {
        type: "bar",
        data: {
          labels: sectorCompare.labels,
          datasets: [
            { label: "Tenders", data: sectorCompare.tenders, backgroundColor: brand, borderRadius: 6 },
            { label: "Projects", data: sectorCompare.projects, backgroundColor: "#94a3b8", borderRadius: 6 },
          ],
        },
        options: { plugins: { legend: { position: "bottom" } }, scales: { y: { beginAtZero: true } } },
      });
    }

    if (completionStatus && document.getElementById("completionChart")) {
      new Chart(document.getElementById("completionChart"), {
        type: "doughnut",
        data: { labels: completionStatus.labels, datasets: [{ data: completionStatus.values, backgroundColor: palette }] },
        options: { plugins: { legend: { position: "bottom" } }, cutout: "62%" },
      });
    }

    if (serviceDemand && document.getElementById("serviceDemandChart")) {
      new Chart(document.getElementById("serviceDemandChart"), {
        type: "bar",
        data: {
          labels: serviceDemand.labels,
          datasets: [
            { label: "Inquiries", data: serviceDemand.inquiries, backgroundColor: brand, borderRadius: 6 },
            { label: "Delivered on", data: serviceDemand.projects, backgroundColor: "#94a3b8", borderRadius: 6 },
          ],
        },
        options: { indexAxis: "y", plugins: { legend: { position: "bottom" } }, scales: { x: { beginAtZero: true } } },
      });
    }
  }

  if (window.Plotly && monthly && document.getElementById("monthlyChart")) {
    Plotly.newPlot(
      "monthlyChart",
      [{ x: monthly.labels, y: monthly.values, type: "scatter", mode: "lines+markers", line: { color: brand, width: 3 }, marker: { color: brand } }],
      { margin: { t: 10, r: 10, b: 40, l: 30 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent", font: { color: ink }, xaxis: { fixedrange: true }, yaxis: { fixedrange: true, rangemode: "tozero" } },
      { displayModeBar: false, responsive: true }
    );
  }

  if (window.Plotly && inquiryMonthly && document.getElementById("inquiryMonthlyChart")) {
    Plotly.newPlot(
      "inquiryMonthlyChart",
      [{ x: inquiryMonthly.labels, y: inquiryMonthly.values, type: "scatter", mode: "lines+markers", line: { color: "#94a3b8", width: 3 }, marker: { color: "#94a3b8" } }],
      { margin: { t: 10, r: 10, b: 40, l: 30 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent", font: { color: ink }, xaxis: { fixedrange: true }, yaxis: { fixedrange: true, rangemode: "tozero" } },
      { displayModeBar: false, responsive: true }
    );
  }
})();
