// Dashboard charts (Chart.js). All numbers are calculated in Python;
// this file only draws them and polls the live API.
const css = getComputedStyle(document.documentElement);
const COLORS = {
  consumption: css.getPropertyValue("--series-consumption").trim(),
  solar: css.getPropertyValue("--series-solar").trim(),
  baseline: css.getPropertyValue("--baseline").trim(),
  grid: "#e9ece8",
  ink: "#57605b",
};
Chart.defaults.color = COLORS.ink;
Chart.defaults.font.family = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
Chart.defaults.plugins.legend.display = false;          // HTML legends are used
Chart.defaults.plugins.tooltip.mode = "index";
Chart.defaults.plugins.tooltip.intersect = false;

const fmt = (v) => Number(v).toLocaleString("en", { maximumFractionDigits: 1 });
const axis = (title) => ({
  grid: { color: COLORS.grid }, border: { display: false },
  title: { display: !!title, text: title },
  ticks: { callback: (v) => fmt(v) },
});
const S = window.SUMMARY;

// 1) Daily consumption vs solar with the benchmark baseline
new Chart(document.getElementById("dailyChart"), {
  data: {
    labels: S.daily.map((d) => d.date.slice(5)),
    datasets: [
      { type: "bar", label: "Consumption", data: S.daily.map((d) => d.consumption),
        backgroundColor: COLORS.consumption, borderRadius: 4, maxBarThickness: 28 },
      { type: "bar", label: "Solar", data: S.daily.map((d) => d.solar),
        backgroundColor: COLORS.solar, borderRadius: 4, maxBarThickness: 28 },
      { type: "line", label: "Benchmark baseline", data: S.daily.map((d) => d.baseline),
        borderColor: COLORS.baseline, borderDash: [6, 4], borderWidth: 2, pointRadius: 0 },
    ],
  },
  options: { maintainAspectRatio: false, scales: { x: { grid: { display: false } }, y: axis("kWh") },
    plugins: { tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y)} kWh` } } } },
});

// 2) Consumption by meter type (single series -> no legend needed)
const consumerTypes = ["hvac", "lighting", "plug_loads"].filter((t) => t in S.by_type_kwh);
new Chart(document.getElementById("typeChart"), {
  type: "bar",
  data: {
    labels: consumerTypes.map((t) => t.replace("_", " ").toUpperCase()),
    datasets: [{ label: "kWh", data: consumerTypes.map((t) => S.by_type_kwh[t]),
      backgroundColor: COLORS.consumption, borderRadius: 4, maxBarThickness: 34 }],
  },
  options: { indexAxis: "y", maintainAspectRatio: false,
    scales: { x: axis("kWh"), y: { grid: { display: false } } } },
});

// 3) Hourly net grid energy for the last 24 hours
new Chart(document.getElementById("hourlyChart"), {
  type: "line",
  data: {
    labels: S.hourly.map((h) => h.time.slice(6)),
    datasets: [{ label: "Net grid energy", data: S.hourly.map((h) => h.net_kwh),
      borderColor: COLORS.consumption, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.25 }],
  },
  options: { maintainAspectRatio: false,
    scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 12 } }, y: axis("kWh") },
    plugins: { tooltip: { callbacks: { label: (c) => `Net: ${fmt(c.parsed.y)} kWh` } } } },
});

// 4) Real-time monitoring: poll POST /api/buildings/<id>/live
const liveChart = new Chart(document.getElementById("liveChart"), {
  type: "line",
  data: { labels: [], datasets: [{ label: "Net grid load", data: [],
    borderColor: COLORS.consumption, borderWidth: 2, pointRadius: 3, tension: 0 }] },
  options: { maintainAspectRatio: false, animation: false,
    scales: { x: { grid: { display: false } }, y: axis("kW") },
    plugins: { tooltip: { callbacks: { label: (c) => `Net load: ${fmt(c.parsed.y)} kW` } } } },
});

const toggle = document.getElementById("liveToggle");
const dot = document.getElementById("liveDot");
const statusEl = document.getElementById("liveStatus");
let timer = null;
let ticks = 0;

function status(m) {
  if (!m.online) return '<span class="text-danger">offline – filtered</span>';
  if (Math.abs(m.power_kw) < 0.05) return '<span class="text-secondary">idle – filtered</span>';
  return '<span class="text-success">online</span>';
}

async function tick() {
  try {
    const res = await fetch(`/api/buildings/${toggle.dataset.building}/live`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || res.statusText);
    ticks += 1;
    document.getElementById("netLoad").textContent = `${fmt(data.net_load_kw)} kW`;
    document.getElementById("meterTable").innerHTML = data.meters.map((m) =>
      `<tr><td>${m.meter_type.replace("_", " ")}</td><td class="text-end">${fmt(m.power_kw)}</td>
       <td>${status(m)}</td></tr>`).join("");
    liveChart.data.labels.push(data.timestamp.slice(11, 19));
    liveChart.data.datasets[0].data.push(data.net_load_kw);
    if (liveChart.data.labels.length > 30) {
      liveChart.data.labels.shift();
      liveChart.data.datasets[0].data.shift();
    }
    liveChart.update();
    statusEl.textContent = `Live · tick ${ticks} · stored ${data.stored}, dropped ${data.dropped} by pipeline filters`;
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
    stop();
  }
}

function start() {
  tick();
  timer = setInterval(tick, 3000);
  dot.classList.add("on");
  toggle.textContent = "⏸ Stop";
  toggle.classList.replace("btn-success", "btn-outline-secondary");
}

function stop() {
  clearInterval(timer);
  timer = null;
  dot.classList.remove("on");
  toggle.textContent = "▶ Start live stream";
  toggle.classList.replace("btn-outline-secondary", "btn-success");
}

toggle.addEventListener("click", () => (timer ? stop() : start()));
