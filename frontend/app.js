const state = { options: null, lastResult: null };
const $ = (id) => document.getElementById(id);

function fmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(digits);
}

function signedFmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  const numeric = Number(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(digits)}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function setLoading(show) {
  $("loading").classList.toggle("hidden", !show);
  $("analyzeBtn").disabled = show;
}

async function api(path, options = {}) {
  const apiBaseUrl = (window.API_BASE_URL || "").replace(/\/$/, "");
  const url = path.startsWith("http") ? path : `${apiBaseUrl}${path}`;
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function syncDoseInputs() {
  [["doseA", "doseASlider"], ["doseB", "doseBSlider"]].forEach(([numberId, sliderId]) => {
    const num = $(numberId);
    const slider = $(sliderId);
    num.addEventListener("input", () => {
      slider.value = Math.min(Number(slider.max), Math.max(Number(slider.min), Number(num.value || 0)));
    });
    slider.addEventListener("input", () => {
      num.value = slider.value;
    });
  });
}

function setupTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
}

function setupHelpModal() {
  const modal = $("helpModal");
  const open = () => modal.classList.remove("hidden");
  const close = () => modal.classList.add("hidden");
  $("helpBtn").addEventListener("click", open);
  $("closeHelpBtn").addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
}

function switchTab(name) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  });
}

function setReportLinks(url) {
  const enabled = Boolean(url);
  ["reportLink", "topReportLink", "reportPanelLink"].forEach((id) => {
    const link = $(id);
    if (!link) return;
    link.href = enabled ? url : "#";
    link.classList.toggle("disabled", !enabled);
    link.setAttribute("aria-disabled", enabled ? "false" : "true");
  });
  const badge = $("reportStatusBadge");
  if (badge) {
    badge.textContent = enabled ? "报告状态：已生成" : "报告状态：待生成";
    badge.classList.toggle("ready", enabled);
  }
  const copyButton = $("copyReportSummaryBtn");
  if (copyButton) copyButton.disabled = !enabled;
  $("reportState").textContent = enabled
    ? "系统已根据当前分析条件生成科研报告草稿，内容包括预测结果、剂量响应、结构贡献、通路机制和科研用途声明。"
    : "完成一次分析后，系统将生成包含预测结果、剂量响应、结构贡献、通路机制和科研用途声明的报告草稿。";
}

function buildReportSummary(result) {
  if (!result) return ["完成分析后，将自动生成当前组合的预测结论、剂量解释、结构贡献和通路机制摘要。"];
  const input = result.input || {};
  const p = result.prediction || {};
  const doseText = result.doseAnalysis ? doseConclusionText(result.doseAnalysis) : "剂量响应分析结果待生成。";
  const pathwayText = result.pathwayAnalysis?.pathways?.length
    ? `VNN 通路结果提示高贡献节点主要集中在${pathwayCategoryText(result.pathwayAnalysis.pathways)}。`
    : "当前未生成稳定的 VNN 通路机制结果。";
  return [
    `当前药物组合 ${input.drugA || "药物 A"} + ${input.drugB || "药物 B"} 在 ${input.cellLine || "当前"} 细胞系和给定剂量下预测为${levelText(p.level)}。${doseText}`,
    pathwayText,
    "该报告可作为后续候选组合筛选、剂量探索和实验设计参考。",
  ];
}

function renderReportSummary(result) {
  const summary = $("reportSummaryText");
  if (!summary) return;
  const lines = buildReportSummary(result);
  summary.innerHTML = lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
}

function setReportPreview(result) {
  const preview = $("reportPreview");
  if (!result) {
    preview.innerHTML = `
      <div><span>报告对象</span><b>待分析</b></div>
      <div><span>细胞背景</span><b>待分析</b></div>
      <div><span>预测结论</span><b>待分析</b></div>
      <div><span>通路机制</span><b>待分析</b></div>
    `;
    renderReportSummary(null);
    return;
  }
  const input = result.input;
  const p = result.prediction;
  const pathwayCount = result.pathwayAnalysis?.pathways?.length || 0;
  preview.innerHTML = `
    <div><span>报告对象</span><b>${escapeHtml(input.drugA)} + ${escapeHtml(input.drugB)}</b></div>
    <div><span>细胞背景</span><b>${escapeHtml(input.cellLine)}</b></div>
    <div><span>预测结论</span><b>${escapeHtml(levelText(p.level))}</b></div>
    <div><span>通路机制</span><b>${pathwayCount} 条通路</b></div>
  `;
  renderReportSummary(result);
}

async function copyReportSummary() {
  const lines = Array.from($("reportSummaryText")?.querySelectorAll("li") || []).map((item) => item.textContent.trim()).filter(Boolean);
  const text = lines.join("\n");
  if (!text || !state.lastResult) return;
  const button = $("copyReportSummaryBtn");
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    if (button) {
      const original = button.textContent;
      button.textContent = "已复制摘要";
      setTimeout(() => { button.textContent = original; }, 1400);
    }
  } catch (err) {
    alert("复制失败，请手动选择报告摘要文本进行复制。");
  }
}

function fillOptions(options) {
  const drugOptions = options.drugs.map((x) => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join("");
  const cellOptions = options.cellLines.map((x) => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join("");
  $("drugA").innerHTML = `<option value="">请选择药物 A</option>${drugOptions}`;
  $("drugB").innerHTML = `<option value="">请选择药物 B</option>${drugOptions}`;
  $("cellLine").innerHTML = `<option value="">请选择细胞系</option>${cellOptions}`;
  const example = options.examples.find((x) => x.drugA === "AZD1775") || options.examples[0];
  if (example) loadExample(example);
  const modelStatus = $("modelStatus");
  const dataStatus = $("dataStatus");
  if (modelStatus) {
    modelStatus.textContent = `模型状态：已加载 ${options.model.device || "CPU"}`;
    modelStatus.classList.add("ok");
  }
  if (dataStatus) {
    dataStatus.textContent = "数据状态：已加载";
    dataStatus.classList.add("ok");
  }
}

function loadExample(example) {
  $("drugA").value = example.drugA;
  $("drugB").value = example.drugB;
  $("cellLine").value = example.cellLine;
  $("doseA").value = example.doseA;
  $("doseB").value = example.doseB;
  $("doseASlider").value = Math.max(0.0001, example.doseA);
  $("doseBSlider").value = Math.max(0.0001, example.doseB);
}

function resetInputs() {
  $("drugA").value = "";
  $("drugB").value = "";
  $("cellLine").value = "";
  $("doseA").value = "0.2";
  $("doseB").value = "1.15";
  $("doseASlider").value = "0.2";
  $("doseBSlider").value = "1.15";
  $("includeFragments").checked = true;
  $("includePathway").checked = true;
  resetResults();
}

function resetResults() {
  state.lastResult = null;
  $("finalScore").textContent = "--";
  $("responseLevel").textContent = "等待输入";
  $("hpbScore").textContent = "--";
  $("idbScore").textContent = "--";
  $("confidenceScore").textContent = "--";
  $("confidenceBar").style.width = "0";
  $("medicalSummary").innerHTML = "<li>请选择药物、细胞系和剂量后开始分析。</li>";
  setGaugeValue(null);
  renderEvidenceTags(null);
  $("theta1Bar").style.width = "0";
  $("theta2Bar").style.width = "0";
  $("epsilonBar").style.width = "0";
  $("theta1Text").textContent = "--";
  $("theta2Text").textContent = "--";
  $("epsilonText").textContent = "--";
  $("warnings").innerHTML = "";
  $("doseSummary").textContent = "候选阈值仅用于模型筛选，不代表临床疗效判断标准。";
  $("doseConclusion").textContent = "结论：完成分析后，将显示剂量响应结论。";
  $("doseCurrentScore").textContent = "--";
  $("doseBestScore").textContent = "--";
  $("doseImprovement").textContent = "--";
  $("doseHighRegion").textContent = "--";
  drawOverviewDoseMini(null);
  renderOverviewMechanism(null);
  renderFragments(null);
  drawSankey(null);
  $("pathwayList").innerHTML = "";
  $("pathwayExplainTable").className = "pathway-explain-table empty";
  $("pathwayExplainTable").textContent = "等待 VNN 通路结果。";
  const rangeWarning = $("doseRangeWarning");
  if (rangeWarning) rangeWarning.classList.add("hidden");
  const canvas = $("doseCanvas");
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
  setReportLinks(null);
  setReportPreview(null);
}

function levelText(level) {
  return { high: "高响应", medium: "中等响应", low: "低响应" }[level] || "不确定";
}

function interactionStrengthText(epsilon) {
  const value = Math.abs(Number(epsilon) || 0);
  if (value >= 0.18) return "较明显";
  if (value >= 0.08) return "一定程度";
  return "较弱";
}

function warningHtml(warnings) {
  return warnings
    .filter((w) => w.title !== "科研用途")
    .map((w) => `<div class="warning-item ${w.level}"><b>${w.title}</b><br>${w.message}</div>`)
    .join("");
}

function mixColor(light, dark, strength) {
  const value = Math.max(0, Math.min(1, Number(strength) || 0));
  const left = light.match(/\w\w/g).map((hex) => parseInt(hex, 16));
  const right = dark.match(/\w\w/g).map((hex) => parseInt(hex, 16));
  const mixed = left.map((channel, index) => Math.round(channel + (right[index] - channel) * value));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

function fragmentColor(direction, strength) {
  return direction === "negative"
    ? mixColor("#93c5fd", "#1d4ed8", strength)
    : mixColor("#fca5a5", "#b91c1c", strength);
}

function renderMedicalSupport(support) {
  const supportIcon = (type) => {
    if (type === "evidence") {
      return `<span class="support-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M7 3h7l4 4v14H7z"></path>
          <path d="M14 3v5h5"></path>
          <path d="M9 13h6"></path>
          <path d="M9 17h4"></path>
        </svg>
      </span>`;
    }
    return `<span class="support-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" focusable="false">
        <path d="M10 4h4"></path>
        <path d="M12 4v5"></path>
        <path d="M9 9h6"></path>
        <path d="M10 9l-4 8"></path>
        <path d="M14 9l4 8"></path>
        <path d="M6 17h12"></path>
        <path d="M8 21h8"></path>
        <circle cx="12" cy="14" r="2"></circle>
      </svg>
    </span>`;
  };
  if (!support) {
    return `<div class="fragment-support">
      <section>${supportIcon("mechanism")}<div><h5>医学支持说明</h5><p>暂无该药物的机制支持说明。</p></div></section>
    </div>`;
  }
  const levels = (support.levels || []).map((item) => `
    <span class="evidence-level"><b>${escapeHtml(item.label)}</b>${escapeHtml(item.value)}</span>
  `).join("");
  const refs = (support.references || []).map((ref, index) => `
    <a href="${escapeHtml(ref.url)}" target="_blank" rel="noreferrer">${index + 1}. ${escapeHtml(ref.label)}</a>
  `).join("") || `<span class="reference-empty">暂无可展示参考依据</span>`;
  const targets = (support.targets || []).map((target) => `<span>${escapeHtml(target)}</span>`).join("");
  const targetBlock = targets ? `<div class="target-chips"><b>主要靶点</b>${targets}</div>` : "";
  return `<div class="fragment-support">
    <section>
      ${supportIcon("mechanism")}
      <div><h5>医学支持说明</h5><p>${escapeHtml(support.mechanism)}</p>${targetBlock}</div>
    </section>
    <section>
      ${supportIcon("evidence")}
      <div>
        <h5>证据边界与参考依据</h5>
        <p>${escapeHtml(support.boundary)}</p>
        <div class="evidence-levels">${levels}</div>
        <div class="reference-links">${refs}</div>
      </div>
    </section>
  </div>`;
}

function renderModelEvidence(result) {
  const area = $("medicalSummary");
  const p = result.prediction || {};
  const input = result.input || {};
  const responseLevel = levelText(p.level);
  const strongerDrug = Number(p.theta1 || 0) >= Number(p.theta2 || 0) ? "药物 A" : "药物 B";
  const interaction = interactionStrengthText(p.epsilon);
  const cellLine = escapeHtml(input.cellLine || "当前");
  area.innerHTML = [
    `当前组合在 <strong>${cellLine}</strong> 细胞系和给定剂量下预测为 <strong>${escapeHtml(responseLevel)}</strong>。`,
    `模型结果显示，两种药物均对预测结果产生贡献，其中 <strong>${strongerDrug}</strong> 的相对作用贡献更高。剂量依赖交互评分提示当前剂量组合可能存在 <strong>${interaction}</strong> 的双药剂量依赖影响。`,
  ].map((text) => `<li>${text}</li>`).join("");
}

function setGaugeValue(value, level) {
  const gauge = $("responseGauge");
  if (!gauge) return;
  const numeric = Number(value);
  const percent = Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric * 100)) : 0;
  const arcPercent = percent * 0.78;
  const color = level === "high" ? "var(--green)" : level === "medium" ? "var(--cyan)" : level === "low" ? "var(--blue)" : "var(--teal)";
  gauge.style.setProperty("--score", `${arcPercent}%`);
  gauge.style.setProperty("--gauge-color", color);
}

function renderEvidenceTags(result) {
  const area = $("evidenceTags");
  if (!area) return;
  if (!result) {
    area.innerHTML = `<span class="evidence-tag muted">等待分析</span>`;
    return;
  }
  const p = result.prediction;
  const warnings = result.warnings || [];
  const tags = [];
  tags.push({ text: levelText(p.level), cls: p.level === "high" ? "" : p.level === "medium" ? "info" : "warn" });
  if (p.confidence >= 0.75) {
    tags.push({ text: "数据覆盖较好", cls: "" });
  } else if (p.confidence >= 0.55) {
    tags.push({ text: "数据覆盖中等", cls: "warn" });
  } else {
    tags.push({ text: "外推需谨慎", cls: "risk" });
  }
  if (warnings.some((w) => w.level === "danger")) {
    tags.push({ text: "存在风险提示", cls: "risk" });
  } else if (warnings.some((w) => w.level === "warning")) {
    tags.push({ text: "存在注意标记", cls: "warn" });
  } else {
    tags.push({ text: "未见明显风险", cls: "" });
  }
  if (result.doseAnalysis?.improvement > 0.08) {
    tags.push({ text: "剂量可优化", cls: "info" });
  } else {
    tags.push({ text: "当前剂量可参考", cls: "info" });
  }
  area.innerHTML = tags.map((tag) => `<span class="evidence-tag ${tag.cls}">${tag.text}</span>`).join("");
}

function renderPrediction(result) {
  const p = result.prediction;
  $("finalScore").textContent = fmt(p.final, 3);
  $("responseLevel").textContent = levelText(p.level);
  $("hpbScore").textContent = fmt(p.hpb, 3);
  $("idbScore").textContent = fmt(p.epsilon, 3);
  const confidencePct = Math.max(0, Math.min(100, Math.round(p.confidence * 100)));
  $("confidenceScore").textContent = `${confidencePct}%`;
  $("confidenceBar").style.width = `${confidencePct}%`;
  renderModelEvidence(result);
  setGaugeValue(p.final, p.level);
  renderEvidenceTags(result);
  drawOverviewDoseMini(result.doseAnalysis);
  renderOverviewMechanism(result.pathwayAnalysis);
  $("theta1Bar").style.width = `${Math.max(0, Math.min(100, p.theta1 * 100))}%`;
  $("theta2Bar").style.width = `${Math.max(0, Math.min(100, p.theta2 * 100))}%`;
  $("epsilonBar").style.width = `${Math.max(5, Math.min(100, Math.abs(p.epsilon) * 180))}%`;
  $("theta1Text").textContent = fmt(p.theta1, 3);
  $("theta2Text").textContent = fmt(p.theta2, 3);
  $("epsilonText").textContent = fmt(p.epsilon, 3);
  $("warnings").innerHTML = warningHtml(result.warnings);
  setReportLinks(result.reportUrl);
  setReportPreview(result);
}

function colorFor(value) {
  const v = Math.max(0, Math.min(1, value));
  const stops = [
    [0.00, "#e8f7ff"],
    [0.25, "#c7e9ff"],
    [0.45, "#63c7e9"],
    [0.60, "#2dd4bf"],
    [0.65, "#b8f13b"],
    [0.75, "#43c75a"],
    [0.88, "#15803d"],
    [1.00, "#075e2b"],
  ];
  for (let i = 1; i < stops.length; i += 1) {
    const [rightStop, rightColor] = stops[i];
    const [leftStop, leftColor] = stops[i - 1];
    if (v <= rightStop) {
      const ratio = (v - leftStop) / Math.max(0.001, rightStop - leftStop);
      const left = leftColor.match(/\w\w/g).map((hex) => parseInt(hex, 16));
      const right = rightColor.match(/\w\w/g).map((hex) => parseInt(hex, 16));
      const mixed = left.map((channel, index) => Math.round(channel + (right[index] - channel) * ratio));
      return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
    }
  }
  return stops[stops.length - 1][1];
}

function doseConclusionText(analysis) {
  const current = analysis.current || {};
  const threshold = Number(analysis.threshold ?? 0.65);
  const improvement = Number(analysis.improvement || 0);
  if (Number(current.prediction) >= threshold) {
    return "当前剂量已达候选阈值，可结合实验可操作性进一步验证。";
  }
  if (improvement > 0.12 || Number(analysis.highResponseCount || 0) > 0) {
    return "当前剂量响应较低，扫描范围内存在更高响应区域。";
  }
  return "本次扫描未见明显高响应候选区域。";
}

function drawOverviewDoseMini(analysis) {
  const canvas = $("overviewDoseCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  if (!analysis || !analysis.values) {
    ctx.fillStyle = "#64748b";
    ctx.font = "bold 18px Arial";
    ctx.fillText("等待剂量扫描结果", 132, 132);
    $("overviewDoseSummary").textContent = "完成分析后，将展示当前剂量在响应扫描中的位置。";
    return;
  }

  const pad = 24;
  const plotW = w - pad * 2;
  const plotH = h - pad * 2 - 18;
  const rows = analysis.values.length;
  const cols = analysis.values[0].length;
  const cellW = plotW / cols;
  const cellH = plotH / rows;
  const threshold = Number(analysis.threshold ?? 0.65);
  analysis.values.forEach((row, r) => {
    row.forEach((val, c) => {
      ctx.fillStyle = colorFor(val);
      ctx.fillRect(pad + c * cellW, pad + (rows - 1 - r) * cellH, cellW + 0.5, cellH + 0.5);
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.lineWidth = 1.2;
      ctx.strokeRect(pad + c * cellW + 0.6, pad + (rows - 1 - r) * cellH + 0.6, cellW - 1.2, cellH - 1.2);
    });
  });
  ctx.strokeStyle = "#102033";
  ctx.lineWidth = 1.4;
  ctx.strokeRect(pad, pad, plotW, plotH);

  const current = analysis.current;
  const best = analysis.best || {};
  const minA = analysis.axisA[0], maxA = analysis.axisA[analysis.axisA.length - 1];
  const minB = analysis.axisB[0], maxB = analysis.axisB[analysis.axisB.length - 1];
  const pointFor = (doseA, doseB) => ({
    x: pad + ((Math.log(Math.max(doseA, minA)) - Math.log(minA)) / (Math.log(maxA) - Math.log(minA))) * plotW,
    y: pad + plotH - ((Math.log(Math.max(doseB, minB)) - Math.log(minB)) / (Math.log(maxB) - Math.log(minB))) * plotH,
  });
  if (best.doseA && best.doseB) {
    const bestPoint = pointFor(best.doseA, best.doseB);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(bestPoint.x - 6, bestPoint.y - 6, 12, 12);
    ctx.strokeStyle = "#16a34a";
    ctx.lineWidth = 3;
    ctx.strokeRect(bestPoint.x - 6, bestPoint.y - 6, 12, 12);
  }
  if (current) {
    const currentPoint = pointFor(current.doseA, current.doseB);
    ctx.beginPath();
    ctx.arc(currentPoint.x, currentPoint.y, 8, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.strokeStyle = "#102033";
    ctx.lineWidth = 4;
    ctx.stroke();
  }
  ctx.fillStyle = "#334155";
  ctx.font = "bold 14px Arial";
  ctx.fillText("低响应", pad, h - 10);
  ctx.fillText("高响应", w - pad - 46, h - 10);
  $("overviewDoseSummary").textContent = analysis.conclusion || "已生成剂量空间位置判断。";
}

function renderOverviewMechanism(data) {
  const svg = $("overviewMechanismSvg");
  if (!svg) return;
  svg.innerHTML = "";
  const summary = $("overviewMechanismSummary");
  const add = (name, attrs = {}) => {
    const el = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
    svg.appendChild(el);
    return el;
  };
  if (!data || !data.pathways || !data.pathways.length) {
    add("text", { x: 132, y: 135, fill: "#64748b", "font-size": 18, "font-weight": 800 }).textContent = "等待通路机制结果";
    if (summary) summary.textContent = "完成分析后，将展示主要通路节点和预测响应之间的关系。";
    return;
  }
  const pathways = data.pathways.slice(0, 3);
  const nodes = [
    { x: 96, y: 74, r: 32, label: pathways[0]?.categoryZh || pathways[0]?.name || "通路1", color: "#0e9fbc" },
    { x: 96, y: 178, r: 30, label: pathways[1]?.categoryZh || pathways[1]?.name || "通路2", color: "#16a34a" },
    { x: 236, y: 126, r: 34, label: pathways[2]?.categoryZh || pathways[2]?.name || "通路3", color: "#f59e0b" },
    { x: 340, y: 126, r: 38, label: "预测响应", color: "#0b2540" },
  ];
  [[0, 3], [1, 3], [2, 3], [0, 2], [1, 2]].forEach(([a, b]) => {
    add("line", { x1: nodes[a].x, y1: nodes[a].y, x2: nodes[b].x, y2: nodes[b].y, stroke: "#b9ced6", "stroke-width": 4, "stroke-linecap": "round" });
  });
  nodes.forEach((node) => {
    add("circle", { cx: node.x, cy: node.y, r: node.r, fill: node.color, opacity: 0.95 });
    const text = add("text", { x: node.x, y: node.y + 5, fill: "#ffffff", "font-size": 14, "font-weight": 800, "text-anchor": "middle" });
    const label = node.label.length > 5 ? `${node.label.slice(0, 5)}…` : node.label;
    text.textContent = label;
  });
  if (summary) summary.textContent = data.mechanismSummary || data.summary || "已生成通路机制摘要。";
}

function drawDoseHeatmap(analysis) {
  const canvas = $("doseCanvas");
  const rangeWarning = $("doseRangeWarning");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  if (!analysis || !analysis.values) {
    if (rangeWarning) rangeWarning.classList.add("hidden");
    $("doseCurrentScore").textContent = "--";
    $("doseBestScore").textContent = "--";
    $("doseImprovement").textContent = "--";
    $("doseHighRegion").textContent = "--";
    return;
  }

  const padL = 78, padB = 60, padT = 26, padR = 32;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const rows = analysis.values.length;
  const cols = analysis.values[0].length;
  const cellW = plotW / cols;
  const cellH = plotH / rows;
  const threshold = Number(analysis.threshold ?? 0.65);
  analysis.values.forEach((row, r) => {
    row.forEach((val, c) => {
      ctx.fillStyle = colorFor(val);
      ctx.fillRect(padL + c * cellW, padT + (rows - 1 - r) * cellH, cellW + 0.5, cellH + 0.5);
      ctx.strokeStyle = "rgba(255,255,255,0.94)";
      ctx.lineWidth = 2;
      ctx.strokeRect(padL + c * cellW + 1, padT + (rows - 1 - r) * cellH + 1, cellW - 2, cellH - 2);
    });
  });

  ctx.strokeStyle = "#102033";
  ctx.lineWidth = 1.3;
  ctx.strokeRect(padL, padT, plotW, plotH);
  ctx.fillStyle = "#334155";
  ctx.font = "26px Arial";
  ctx.fillText("药物 A 剂量 (uM)", padL + plotW / 2 - 92, h - 18);
  ctx.save();
  ctx.translate(24, padT + plotH / 2 + 82);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("药物 B 剂量 (uM)", 0, 0);
  ctx.restore();
  ctx.fillStyle = "#111827";
  ctx.font = "23px Arial";
  ctx.fillText(String(analysis.axisA[0]), padL, h - 38);
  ctx.fillText(String(analysis.axisA[analysis.axisA.length - 1]), padL + plotW - 74, h - 38);
  ctx.fillText(String(analysis.axisB[0]), 28, padT + plotH);
  ctx.fillText(String(analysis.axisB[analysis.axisB.length - 1]), 28, padT + 10);

  const current = analysis.current;
  const best = analysis.best || {};
  const minA = analysis.axisA[0], maxA = analysis.axisA[analysis.axisA.length - 1];
  const minB = analysis.axisB[0], maxB = analysis.axisB[analysis.axisB.length - 1];
  const outOfRange = current.doseA < minA || current.doseA > maxA || current.doseB < minB || current.doseB > maxB;
  if (rangeWarning) rangeWarning.classList.toggle("hidden", !outOfRange);
  const clampDose = (dose, min, max) => Math.max(min, Math.min(max, dose));
  const pointFor = (doseA, doseB) => ({
    x: padL + ((Math.log(clampDose(doseA, minA, maxA)) - Math.log(minA)) / (Math.log(maxA) - Math.log(minA))) * plotW,
    y: padT + plotH - ((Math.log(clampDose(doseB, minB, maxB)) - Math.log(minB)) / (Math.log(maxB) - Math.log(minB))) * plotH,
  });
  const { x, y } = pointFor(current.doseA, current.doseB);
  if (best.doseA && best.doseB) {
    const pBest = pointFor(best.doseA, best.doseB);
    ctx.lineWidth = 5;
    ctx.strokeStyle = "#ef4444";
    ctx.strokeRect(pBest.x - 9, pBest.y - 9, 18, 18);
    ctx.fillStyle = "#b91c1c";
    ctx.font = "bold 26px Arial";
    const labelX = Math.max(padL + 6, Math.min(pBest.x - 86, padL + plotW - 112));
    const labelY = Math.max(padT + 24, Math.min(pBest.y + 24, padT + plotH - 8));
    ctx.fillText("最高响应", labelX, labelY);
  }
  ctx.beginPath();
  ctx.arc(x, y, 8, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#102033";
  ctx.stroke();
  ctx.fillStyle = "#102033";
  ctx.font = "bold 26px Arial";
  ctx.fillText("当前", x + 12, y - 8);
  $("doseCurrentScore").textContent = fmt(current.prediction, 3);
  $("doseBestScore").textContent = fmt(best.prediction, 3);
  $("doseImprovement").textContent = fmt(analysis.improvement, 3);
  $("doseHighRegion").textContent = `${analysis.highResponseCount || 0} 个点`;
  $("doseSummary").textContent = "候选阈值仅用于模型筛选，不代表临床疗效判断标准。";
  $("doseConclusion").textContent = `结论：${doseConclusionText(analysis)}`;
}

function renderFragments(data) {
  const area = $("fragmentArea");
  if (!data || !data.drugs) {
    area.className = "fragment-area empty";
    area.textContent = "等待结构贡献结果。";
    return;
  }
  area.className = "fragment-area";
  area.innerHTML = data.drugs.map((drug) => {
    const max = Math.max(...drug.fragments.map((f) => f.absImportance), 0.001);
    const significantFragments = drug.fragments.filter((f) => Number(f.absImportance || 0) >= 0.001).slice(0, 3);
    const rows = significantFragments.map((f, index) => {
      const width = Math.max(4, (f.absImportance / max) * 100);
      const strength = Number.isFinite(Number(f.strength)) ? Number(f.strength) : Math.min(1, f.absImportance / max);
      const color = fragmentColor(f.direction, strength);
      return `<div class="frag-row ${f.direction === "negative" ? "negative" : ""}" style="--frag-color:${color}">
        <span class="frag-name">敏感片段 ${index + 1}</span>
        <div class="frag-track"><i style="width:${width}%"></i></div>
        <b>${signedFmt(f.importance, 3)}</b>
      </div>`;
    }).join("") || `<div class="frag-empty-note">未检测到绝对扰动影响不为 0 的敏感片段。</div>`;
    const tag = drug.tag === "drugA" ? "药物 A" : "药物 B";
    return `<div class="fragment-card">
      <h3>${tag}：${escapeHtml(drug.drug)} 预测敏感子结构</h3>
      <div class="fragment-card-body">
        <div class="mol-svg">${drug.svg || "分子图生成失败"}</div>
        <div class="frag-panel">
          <h4>敏感片段排序</h4>
          <div class="frag-bars">${rows}</div>
        </div>
      </div>
      ${renderMedicalSupport(drug.medicalSupport)}
    </div>`;
  }).join("");
}

function pathwayCategories(pathways) {
  const categories = [];
  (pathways || []).forEach((p) => {
    const category = p.categoryZh || "相关生物过程";
    if (!categories.includes(category)) categories.push(category);
  });
  return categories;
}

function pathwayCategoryText(pathways) {
  const categories = pathwayCategories(pathways);
  const primary = categories.filter((c) => c !== "发育相关过程").slice(0, 3);
  const selected = primary.length ? primary : categories.slice(0, 3);
  return selected.length ? selected.join("、") : "相关生物过程";
}

function renderMechanismNarrative(data) {
  const pathways = data?.pathways || [];
  const categories = pathwayCategories(pathways);
  const mainText = pathwayCategoryText(pathways);
  const hasDevelopment = categories.includes("发育相关过程");
  const modelTip = pathways.length
    ? `VNN 结果显示，当前预测的高贡献节点主要集中在${mainText}。`
    : "当前样本未形成稳定的高贡献通路归因结果，机制解释应谨慎参考。";
  const biology = hasDevelopment
    ? "这些过程可能与肿瘤细胞应激反应、微环境适应、增殖调控或迁移能力变化有关；同时出现部分发育相关 GO 术语，需结合具体基因和实验背景谨慎解释。"
    : "这些过程可能与肿瘤细胞应激反应、微环境适应、增殖调控或迁移能力变化有关。";
  const validation = "建议结合关键基因表达、通路富集分析、文献证据或体外实验进一步验证该机制假设。";
  $("pathwayNarrative").innerHTML = [
    ["模型提示", modelTip],
    ["生物学含义", biology],
    ["验证建议", validation],
  ].map(([title, text]) => `<section><b>${title}</b><p>${text}</p></section>`).join("");
}

function wrapSvgText(label, maxChars = 24, maxLines = 2) {
  const words = String(label || "").split(/\s+/).filter(Boolean);
  if (!words.length) return [String(label || "")];
  const lines = [];
  let current = "";
  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });
  if (current) lines.push(current);
  if (lines.length > maxLines) {
    const kept = lines.slice(0, maxLines);
    kept[maxLines - 1] = `${kept[maxLines - 1].slice(0, maxChars - 3)}...`;
    return kept;
  }
  return lines;
}

function appendSvgLabel(group, label, x, y, options = {}) {
  const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
  const lines = wrapSvgText(label, options.maxChars || 22, options.maxLines || 2);
  const fontSize = options.fontSize || 14;
  text.setAttribute("x", x);
  text.setAttribute("y", y - ((lines.length - 1) * fontSize * 0.48));
  text.setAttribute("text-anchor", "middle");
  text.setAttribute("font-size", String(fontSize));
  text.setAttribute("font-weight", options.weight || "700");
  text.setAttribute("fill", options.fill || "#172033");
  lines.forEach((line, index) => {
    const tspan = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
    tspan.setAttribute("x", x);
    tspan.setAttribute("dy", index === 0 ? "0" : String(fontSize + 2));
    tspan.textContent = line;
    text.appendChild(tspan);
  });
  group.appendChild(text);
}

function ellipsizeLabel(label, maxChars) {
  const text = String(label || "");
  return text.length > maxChars ? `${text.slice(0, Math.max(0, maxChars - 3))}...` : text;
}

function splitTooltipText(text, maxChars = 62) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  if (!words.length) return [String(text || "")];
  const lines = [];
  let current = "";
  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  });
  if (current) lines.push(current);
  return lines.slice(0, 3);
}

function drawSankey(data) {
  const svg = $("sankeySvg");
  svg.innerHTML = "";
  if (!data || !data.nodes || !data.links) {
    $("pathwayBars").className = "pathway-bars empty";
    $("pathwayBars").textContent = "等待 VNN 通路结果。";
    $("pathwaySummary").textContent = "本模块用于展示模型在当前药物组合预测中关注的高贡献生物过程，并将关键基因特征、GO 功能节点与预测响应进行关联。通路结果为模型解释线索，不等同于已验证作用机制。";
    $("pathwayNarrative").innerHTML = `<section><b>模型提示</b><p>完成分析后，将展示模型归因得到的主要通路节点和机制假设。</p></section>`;
    $("pathwayList").innerHTML = "";
    $("pathwayExplainTable").className = "pathway-explain-table empty";
    $("pathwayExplainTable").textContent = "等待 VNN 通路结果。";
    return;
  }
  renderPathwayBars(data);
  renderPathwayExplanation(data);

  const ns = "http://www.w3.org/2000/svg";
  const height = 540;
  const viewWidth = 1240;
  const layers = {
    gene: data.nodes.filter((n) => n.type === "gene").slice(0, 8),
    pathway: data.nodes
      .filter((n) => n.type === "pathway")
      .sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0))
      .slice(0, 8),
    prediction: data.nodes.filter((n) => n.type === "prediction"),
  };
  const pos = {};
  const widths = { gene: 190, pathway: 390, prediction: 170 };
  const header = [
    { x: 140, label: "关键基因特征" },
    { x: 620, label: "高贡献 GO 生物过程" },
    { x: 1080, label: "预测响应" },
  ];
  header.forEach((item) => {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", item.x);
    text.setAttribute("y", "24");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("font-size", "22");
    text.setAttribute("font-weight", "900");
    text.setAttribute("fill", "#0b2540");
    text.textContent = item.label;
    svg.appendChild(text);
  });
  function place(items, x, top = 42) {
    const usableHeight = height - top - 12;
    const gap = usableHeight / (items.length + 1);
    items.forEach((node, i) => { pos[node.id] = { x, y: top + gap * (i + 1), node }; });
  }
  place(layers.gene, 140);
  place(layers.pathway, 620);
  place(layers.prediction, 1080);

  const tooltip = document.createElementNS(ns, "g");
  tooltip.setAttribute("class", "sankey-tooltip hidden");
  const tooltipBg = document.createElementNS(ns, "rect");
  tooltipBg.setAttribute("rx", "8");
  tooltipBg.setAttribute("height", "40");
  const tooltipText = document.createElementNS(ns, "text");
  tooltip.appendChild(tooltipBg);
  tooltip.appendChild(tooltipText);

  function showTooltip(text, x, y) {
    const lines = splitTooltipText(text);
    const fontSize = 18;
    const width = Math.min(720, Math.max(220, Math.max(...lines.map((line) => line.length)) * 9.2 + 30));
    const heightBox = 22 + lines.length * 24;
    const left = Math.min(Math.max(12, x - width / 2), viewWidth - width - 12);
    const top = Math.max(12, y - heightBox - 16);
    tooltipBg.setAttribute("x", left);
    tooltipBg.setAttribute("y", top);
    tooltipBg.setAttribute("width", width);
    tooltipBg.setAttribute("height", heightBox);
    tooltipText.innerHTML = "";
    lines.forEach((line, index) => {
      const tspan = document.createElementNS(ns, "tspan");
      tspan.setAttribute("x", left + 15);
      tspan.setAttribute("y", top + 27 + index * 24);
      tspan.textContent = line;
      tooltipText.appendChild(tspan);
    });
    tooltip.classList.remove("hidden");
    svg.appendChild(tooltip);
  }

  function hideTooltip() {
    tooltip.classList.add("hidden");
  }

  const visibleIds = new Set(Object.keys(pos));
  const links = data.links.filter((link) => visibleIds.has(link.source) && visibleIds.has(link.target));
  const maxValue = Math.max(...links.map((l) => Number(l.value) || 0), 0.0001);
  links.forEach((link) => {
    const a = pos[link.source], b = pos[link.target];
    if (!a || !b) return;
    const ratio = Math.min(1, (Number(link.value) || 0) / maxValue);
    const path = document.createElementNS(ns, "path");
    const aWidth = widths[a.node.type] || 170;
    const bWidth = widths[b.node.type] || 170;
    path.setAttribute("d", `M${a.x + aWidth / 2},${a.y} C${a.x + 160},${a.y} ${b.x - 160},${b.y} ${b.x - bWidth / 2},${b.y}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", link.target === "prediction" ? "#0f766e" : "#2563eb");
    path.setAttribute("stroke-opacity", String(0.18 + ratio * 0.44));
    const baseWidth = Math.max(2, ratio * 18);
    path.setAttribute("stroke-width", String(baseWidth));
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("class", "sankey-link");
    const title = document.createElementNS(ns, "title");
    title.textContent = `${a.node.label} → ${b.node.label}，贡献强度 ${fmt(link.value, 5)}。线条越粗，表示该路径对当前预测的归因贡献越高。`;
    path.appendChild(title);
    path.addEventListener("mouseenter", () => {
      path.setAttribute("stroke-opacity", "0.86");
      path.setAttribute("stroke-width", String(baseWidth + 4));
      showTooltip(`贡献强度：${fmt(link.value, 5)}｜${a.node.label} → ${b.node.label}`, (a.x + b.x) / 2, (a.y + b.y) / 2);
    });
    path.addEventListener("mouseleave", () => {
      path.setAttribute("stroke-opacity", String(0.18 + ratio * 0.44));
      path.setAttribute("stroke-width", String(baseWidth));
      hideTooltip();
    });
    svg.appendChild(path);
  });

  [...layers.gene, ...layers.pathway, ...layers.prediction].forEach((node) => {
    const p = pos[node.id];
    if (!p) return;
    const group = document.createElementNS(ns, "g");
    group.setAttribute("class", "sankey-node");
    const width = widths[node.type] || 170;
    const heightBox = node.type === "pathway" ? 36 : 34;
    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("x", p.x - width / 2);
    rect.setAttribute("y", p.y - heightBox / 2);
    rect.setAttribute("width", width);
    rect.setAttribute("height", heightBox);
    rect.setAttribute("rx", node.type === "prediction" ? 7 : 8);
    rect.setAttribute("fill", node.type === "prediction" ? "#0f766e" : node.type === "pathway" ? "#e8f8fb" : "#f6f9fc");
    rect.setAttribute("stroke", node.type === "pathway" ? "#b9e2eb" : "#cbd5e1");
    rect.setAttribute("stroke-width", node.type === "prediction" ? "0" : "1.2");
    group.appendChild(rect);
    const title = document.createElementNS(ns, "title");
    title.textContent = node.label;
    group.appendChild(title);
    appendSvgLabel(group, ellipsizeLabel(node.label, node.type === "pathway" ? 46 : 18), p.x, p.y + 4, {
      maxChars: node.type === "pathway" ? 48 : 18,
      maxLines: 1,
      fontSize: 16,
      fill: node.type === "prediction" ? "#ffffff" : "#102033",
      weight: node.type === "prediction" ? "900" : "800",
    });
    group.addEventListener("mouseenter", () => showTooltip(node.label, p.x, p.y - heightBox / 2));
    group.addEventListener("mouseleave", hideTooltip);
    svg.appendChild(group);
  });
  svg.appendChild(tooltip);
  $("pathwayList").innerHTML = "";
}

function renderPathwayBars(data) {
  const pathways = data.pathways || [];
  const maxScore = Math.max(...pathways.map((p) => Number(p.score) || 0), 0.0001);
  $("pathwaySummary").textContent = "本模块用于展示模型在当前药物组合预测中关注的高贡献生物过程，并将关键基因特征、GO 功能节点与预测响应进行关联。通路结果为模型解释线索，不等同于已验证作用机制。";
  renderMechanismNarrative(data);
  if (!pathways.length) {
    $("pathwayBars").className = "pathway-bars empty";
    $("pathwayBars").textContent = "未生成高贡献生物过程结果。";
    return;
  }
  $("pathwayBars").className = "pathway-bars";
  $("pathwayBars").innerHTML = pathways.slice(0, 8).map((p) => {
    const width = Math.max(4, (Number(p.score) / maxScore) * 100);
    const category = p.categoryZh || "相关生物过程";
    const caution = category.includes("发育") ? " caution" : "";
    return `<div class="pathway-bar-row" title="${escapeHtml(p.name)}">
      <span class="pathway-name">${escapeHtml(p.name)}</span>
      <span class="pathway-category${caution}">${escapeHtml(category)}</span>
      <div class="pathway-bar-track"><i style="width:${width}%"></i></div>
      <b>${fmt(p.score, 5)}</b>
    </div>`;
  }).join("");
}

function renderPathwayExplanation(data) {
  const pathways = data.pathways || [];
  if (!pathways.length) {
    $("pathwayExplainTable").className = "pathway-explain-table empty";
    $("pathwayExplainTable").textContent = "未生成 GO 术语解释。";
    return;
  }
  $("pathwayExplainTable").className = "pathway-explain-table";
  const rows = pathways.slice(0, 6).map((p) => {
    const category = p.categoryZh || "相关生物过程";
    const interpretation = p.interpretation || "该 GO 术语为模型归因得到的高贡献节点，需结合具体基因和实验背景解释。";
    return `<div class="pathway-explain-row">
      <b>${escapeHtml(p.name)}</b>
      <span class="pathway-category">${escapeHtml(category)}</span>
      <span class="pathway-score">${fmt(p.score, 5)}</span>
      <span>${escapeHtml(interpretation)}</span>
    </div>`;
  }).join("");
  $("pathwayExplainTable").innerHTML = `
    <div class="pathway-explain-head">
      <span>GO 术语</span>
      <span>中文归类</span>
      <span>贡献分数</span>
      <span>可能生物学含义</span>
    </div>
    ${rows}
  `;
}

async function runAnalysis() {
  const payload = {
    drugA: $("drugA").value.trim(),
    drugB: $("drugB").value.trim(),
    cellLine: $("cellLine").value.trim(),
    doseA: Number($("doseA").value),
    doseB: Number($("doseB").value),
    includeFragments: $("includeFragments").checked,
    includePathway: $("includePathway").checked,
    gridSize: 8,
  };
  if (!payload.drugA || !payload.drugB || !payload.cellLine) {
    alert("请先填写药物 A、药物 B 和细胞系。");
    return;
  }
  setLoading(true);
  try {
    const result = await api("/api/analyze", { method: "POST", body: JSON.stringify(payload) });
    state.lastResult = result;
    renderPrediction(result);
    drawDoseHeatmap(result.doseAnalysis);
    renderFragments(result.fragmentAnalysis);
    drawSankey(result.pathwayAnalysis);
    switchTab("overview");
  } catch (err) {
    alert(`分析失败：${err.message}`);
  } finally {
    setLoading(false);
  }
}

async function init() {
  syncDoseInputs();
  setupTabs();
  setupHelpModal();
  setReportLinks(null);
  setReportPreview(null);
  $("analyzeBtn").addEventListener("click", runAnalysis);
  $("resetBtn").addEventListener("click", resetInputs);
  $("copyReportSummaryBtn").addEventListener("click", copyReportSummary);
  $("exampleBtn").addEventListener("click", () => {
    if (!state.options) return;
    const example = state.options.examples[Math.floor(Math.random() * state.options.examples.length)];
    loadExample(example);
  });
  try {
    state.options = await api("/api/options");
    fillOptions(state.options);
  } catch (err) {
    const modelStatus = $("modelStatus");
    const dataStatus = $("dataStatus");
    if (modelStatus) {
      modelStatus.textContent = "模型状态：加载失败";
      modelStatus.classList.add("warning");
    }
    if (dataStatus) {
      dataStatus.textContent = "数据状态：加载失败";
      dataStatus.classList.add("warning");
    }
    console.error(err);
  }
}

init();
