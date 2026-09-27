const pptxgen = require("pptxgenjs");

// Palette (matches the Slides artifact)
const NAVY = "0F1733";
const NAVY2 = "16214A";
const TEAL = "2DD4BF";
const TEALDARK = "06231F";
const BLUE = "4F8CFF";
const AMBER = "F5A524";
const INK = "E8ECFF";
const MUTE = "9AA7D6";
const BODY = "C9D3F5";
const LINE = "2A3A75";

const HEAD = "Cambria";
const MONO = "Consolas";
const SANS = "Calibri";

function footer(slide, page) {
  slide.addText("Aurelia Retail Group  ·  Marketing & Demand", {
    x: 0.5, y: 6.95, w: 8, h: 0.35, fontFace: MONO, fontSize: 11,
    color: slide._darkFooter ? TEALDARK : MUTE, isTextBox: true, margin: 0,
  });
  slide.addText(`${page} / 8`, {
    x: 12.1, y: 6.95, w: 0.9, h: 0.35, fontFace: MONO, fontSize: 11, align: "right",
    color: slide._darkFooter ? TEALDARK : MUTE, isTextBox: true, margin: 0,
  });
}

function card(slide, x, y, w, h, opts = {}) {
  slide.addShape("roundRect", {
    x, y, w, h, rectRadius: 0.12,
    fill: { color: opts.fill || NAVY2 },
    line: opts.line === false ? { type: "none" } : { color: opts.lineColor || LINE, width: 1 },
  });
}

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5 in

// ---------- 1. Cover ----------
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("ARCHITHON 2026  ·  RETAIL  ·  MARKETING & DEMAND", {
    x: 0.6, y: 0.5, w: 12, h: 0.4, fontFace: MONO, fontSize: 14, color: TEAL,
    charSpacing: 2, isTextBox: true, margin: 0,
  });
  s.addText("Demand Command", {
    x: 0.6, y: 2.1, w: 12, h: 1.6, fontFace: HEAD, fontSize: 60, bold: true, color: INK,
    isTextBox: true, margin: 0,
  });
  s.addShape("rect", { x: 0.6, y: 3.75, w: 4.5, h: 0.05, fill: { color: TEAL }, line: { type: "none" } });
  s.addText("Agentic AI that senses demand and commits a campaign only when the supply chain can serve it.", {
    x: 0.6, y: 4.05, w: 10.5, h: 0.9, fontFace: SANS, fontSize: 22, color: BODY, isTextBox: true, margin: 0,
  });
  s.addText("Sector: multi-sector retail. Context: Aurelia Retail Group, 600 stores and e-commerce across 8 markets, 18-month transformation.", {
    x: 0.6, y: 6.2, w: 11.5, h: 0.7, fontFace: SANS, fontSize: 14, color: MUTE, isTextBox: true, margin: 0,
  });
}

// ---------- 2. Problem ----------
{
  const s = pres.addSlide();
  s._darkFooter = false;
  s.background = { color: NAVY };
  s.addText("BURNING PLATFORM: DEMAND VOLATILITY", {
    x: 0.6, y: 0.45, w: 12, h: 0.35, fontFace: MONO, fontSize: 13, color: TEAL, charSpacing: 2, isTextBox: true, margin: 0,
  });
  s.addText("Demand shifts in days. Campaigns commit without seeing stock.", {
    x: 0.6, y: 0.85, w: 11.5, h: 0.9, fontFace: HEAD, fontSize: 32, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  const cols = [
    ["Signals move fast", "Value-seeking behavior changes by market, channel and category within days.", TEAL],
    ["Campaigns commit early", "Spend, offers and creative are approved without live inventory or sourcing data.", BLUE],
    ["Costs land late", "Stockouts, wasted spend and markdowns appear weeks after the decision was made.", AMBER],
  ];
  const cw = 3.9, gap = 0.25, x0 = 0.6, y0 = 2.1, h = 2.3;
  cols.forEach((c, i) => {
    const x = x0 + i * (cw + gap);
    card(s, x, y0, cw, h);
    s.addText(c[0], { x: x + 0.3, y: y0 + 0.25, w: cw - 0.6, h: 0.5, fontFace: HEAD, fontSize: 18, bold: true, color: c[2], isTextBox: true, margin: 0 });
    s.addText(c[1], { x: x + 0.3, y: y0 + 0.8, w: cw - 0.6, h: 1.3, fontFace: SANS, fontSize: 14, color: BODY, isTextBox: true, margin: 0 });
  });
  s.addText("Our answer: predict value-seeking demand across 8 markets and channels, then act only on what the supply chain can deliver.", {
    x: 0.6, y: 4.85, w: 11.8, h: 0.9, fontFace: SANS, fontSize: 17, color: INK, isTextBox: true, margin: 0,
  });
  footer(s, 2);
}

// ---------- 3. Architecture diagram ----------
{
  const s = pres.addSlide();
  s._darkFooter = false;
  s.background = { color: NAVY };
  s.addText("Architecture at a glance", {
    x: 0.6, y: 0.35, w: 11, h: 0.6, fontFace: HEAD, fontSize: 26, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  s.addText("SIGNALS IN:  POS · web and app · search and social · weather and events · competitor prices", {
    x: 0.6, y: 0.95, w: 12, h: 0.35, fontFace: MONO, fontSize: 11, color: MUTE, isTextBox: true, margin: 0,
  });

  // Column 1: Signals & data
  card(s, 0.6, 1.5, 2.55, 4.4);
  s.addText("SIGNALS AND DATA", { x: 0.85, y: 1.7, w: 2.1, h: 0.3, fontFace: MONO, fontSize: 11, color: TEAL, charSpacing: 1, isTextBox: true, margin: 0 });
  ["POS and e-commerce sales", "Web and app clickstream", "Search, social, weather, events", "Competitor prices", "Inventory and sourcing feed, read-only"].forEach((t, i) => {
    s.addText(t, { x: 0.85, y: 2.15 + i * 0.65, w: 2.1, h: 0.6, fontFace: SANS, fontSize: 12, color: INK, isTextBox: true, margin: 0 });
  });

  // Column 2: Domain agents
  card(s, 3.4, 1.5, 3.35, 4.4);
  s.addText("DOMAIN AGENTS", { x: 3.65, y: 1.7, w: 2.8, h: 0.3, fontFace: MONO, fontSize: 11, color: TEAL, charSpacing: 1, isTextBox: true, margin: 0 });
  const agents = ["Demand Sensing", "Segmentation", "Campaign Planning", "Creative & Localization", "Promo & Price Signal", "Measurement"];
  agents.forEach((t, i) => {
    const y = 2.15 + i * 0.6;
    s.addShape("roundRect", { x: 3.65, y, w: 2.85, h: 0.5, rectRadius: 0.07, fill: { color: NAVY }, line: { color: i === 5 ? AMBER : BLUE, width: 1 } });
    s.addText(t, { x: 3.8, y: y + 0.06, w: 2.55, h: 0.4, fontFace: SANS, fontSize: 13, bold: true, color: INK, isTextBox: true, margin: 0 });
  });

  // Column 3: Orchestrator + guardrails
  card(s, 7.1, 1.5, 2.6, 2.9, { fill: TEAL, lineColor: TEAL });
  s.addText("Demand Orchestrator", { x: 7.35, y: 1.7, w: 2.1, h: 0.5, fontFace: HEAD, fontSize: 16, bold: true, color: TEALDARK, isTextBox: true, margin: 0 });
  s.addText("Optimizes shared goals: incremental margin, sell-through, service level, waste.", {
    x: 7.35, y: 2.25, w: 2.15, h: 1.0, fontFace: SANS, fontSize: 11.5, color: TEALDARK, isTextBox: true, margin: 0,
  });
  s.addText("Rule: no campaign without stock to serve it.", {
    x: 7.35, y: 3.35, w: 2.15, h: 0.9, fontFace: SANS, fontSize: 11.5, bold: true, color: TEALDARK, isTextBox: true, margin: 0,
  });
  card(s, 7.1, 4.55, 2.6, 1.35, { fill: NAVY, lineColor: AMBER });
  s.addText("GUARDRAILS", { x: 7.3, y: 4.68, w: 2.2, h: 0.3, fontFace: MONO, fontSize: 11, color: AMBER, charSpacing: 1, isTextBox: true, margin: 0 });
  s.addText("Margin floor, budget caps, consent, approval above EUR 15k", {
    x: 7.3, y: 5.0, w: 2.2, h: 0.85, fontFace: SANS, fontSize: 11.5, color: INK, isTextBox: true, margin: 0,
  });

  // Column 4: downstream teams
  const teams = [
    ["Merchandising", "Allocation and assortment requests"],
    ["Sourcing", "Replenishment requests"],
    ["Logistics and CX", "Demand-shaped service levels"],
  ];
  teams.forEach((t, i) => {
    const y = 1.5 + i * 1.5;
    card(s, 10.05, y, 2.65, 1.3);
    s.addText(t[0], { x: 10.3, y: y + 0.15, w: 2.15, h: 0.4, fontFace: HEAD, fontSize: 14, bold: true, color: INK, isTextBox: true, margin: 0 });
    s.addText(t[1], { x: 10.3, y: y + 0.55, w: 2.15, h: 0.6, fontFace: SANS, fontSize: 11.5, color: BODY, isTextBox: true, margin: 0 });
  });

  s.addText("Feedback loop: Measurement results retrain the sensing and promo models", {
    x: 0.6, y: 6.05, w: 12.1, h: 0.35, fontFace: SANS, fontSize: 13, italic: true, color: AMBER, align: "center", isTextBox: true, margin: 0,
  });
  footer(s, 3);
}

// ---------- 4. Architecture (agents table) ----------
{
  const s = pres.addSlide();
  s._darkFooter = false;
  s.background = { color: NAVY2 };
  s.addText("Six agents, one orchestrator, two hand-offs", {
    x: 0.6, y: 0.35, w: 12, h: 0.6, fontFace: HEAD, fontSize: 26, bold: true, color: INK, isTextBox: true, margin: 0,
  });
  const grid = [
    ["Demand Sensing", "Fuses signals into one curve"],
    ["Segmentation", "Finds value-seeking shoppers"],
    ["Campaign Planning", "Channel mix, budget, timing"],
    ["Creative & Localization", "On-brand content per market"],
    ["Promo & Price Signal", "Offer depth above margin floor"],
    ["Measurement", "Incrementality tests, feedback"],
  ];
  const cw = 3.9, ch = 1.0, gx = 0.2, gy = 0.2, x0 = 0.6, y0 = 1.15;
  grid.forEach((g, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = x0 + col * (cw + gx), y = y0 + row * (ch + gy);
    card(s, x, y, cw, ch, { fill: NAVY });
    s.addText(g[0], { x: x + 0.25, y: y + 0.12, w: cw - 0.5, h: 0.4, fontFace: HEAD, fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0 });
    s.addText(g[1], { x: x + 0.25, y: y + 0.53, w: cw - 0.5, h: 0.4, fontFace: SANS, fontSize: 12, color: MUTE, isTextBox: true, margin: 0 });
  });
  card(s, 0.6, 3.75, 12.1, 1.15, { fill: TEAL, lineColor: TEAL });
  s.addText("Demand Orchestrator", { x: 0.9, y: 3.9, w: 5, h: 0.4, fontFace: HEAD, fontSize: 18, bold: true, color: TEALDARK, isTextBox: true, margin: 0 });
  s.addText("Optimizes shared goals: incremental margin, sell-through, service level, waste. Rule: no campaign without stock to serve it.", {
    x: 0.9, y: 4.3, w: 11.5, h: 0.55, fontFace: SANS, fontSize: 13.5, color: TEALDARK, isTextBox: true, margin: 0,
  });
  const hand = [["To Merchandising:", "allocation and assortment requests"], ["To Sourcing:", "replenishment requests"]];
  hand.forEach((h, i) => {
    const x = 0.6 + i * 6.15;
    s.addShape("roundRect", { x, y: 5.15, w: 6.0, h: 0.85, rectRadius: 0.1, fill: { type: "none" }, line: { color: BLUE, width: 2 } });
    s.addText([{ text: h[0] + " ", options: { bold: true } }, { text: h[1] }], {
      x: x + 0.3, y: 5.3, w: 5.4, h: 0.55, fontFace: SANS, fontSize: 14.5, color: INK, isTextBox: true, margin: 0,
    });
  });
  footer(s, 4);
}

// ---------- 5. Scenario ----------
{
  const s = pres.addSlide();
  s._darkFooter = false;
  s.background = { color: NAVY };
  s.addText("LIVE DEMO · SYNTHETIC DATA", { x: 0.6, y: 0.4, w: 12, h: 0.35, fontFace: MONO, fontSize: 13, color: TEAL, charSpacing: 2, isTextBox: true, margin: 0 });
  s.addText("Home demand spike in Market C", { x: 0.6, y: 0.8, w: 11.5, h: 0.75, fontFace: HEAD, fontSize: 30, bold: true, color: INK, isTextBox: true, margin: 0 });
  const steps = [
    ["1 · Sense", "Competitor price cut lifts Home demand. +5,000 units projected.", TEAL],
    ["2 · Segment", "About 68% of the uplift is price-sensitive repeat buyers.", TEAL],
    ["3 · Check stock", "Stock covers 60% of the lift: 3,000 of 5,000 units.", TEAL],
    ["4 · Decide", "Campaign scaled to EUR 24k of 40k. EUR 9.6k moves to a surplus category.", TEAL],
    ["5 · Govern", "A change above EUR 15k needs human approval. 2,000 units requested from Sourcing.", AMBER],
  ];
  const cw = (12.1 - 4 * 0.2) / 5, y0 = 1.85, h = 3.5;
  steps.forEach((st, i) => {
    const x = 0.6 + i * (cw + 0.2);
    card(s, x, y0, cw, h, { lineColor: st[2] === AMBER ? AMBER : LINE });
    s.addText(st[0], { x: x + 0.2, y: y0 + 0.25, w: cw - 0.4, h: 0.4, fontFace: MONO, fontSize: 13, color: st[2], isTextBox: true, margin: 0 });
    s.addText(st[1], { x: x + 0.2, y: y0 + 0.75, w: cw - 0.4, h: h - 1.0, fontFace: SANS, fontSize: 13, color: INK, isTextBox: true, margin: 0 });
  });
  s.addText("Without the orchestrator, EUR 16k of spend chases 2,000 units that cannot be delivered.", {
    x: 0.6, y: 5.6, w: 11.8, h: 0.6, fontFace: SANS, fontSize: 16, color: BODY, isTextBox: true, margin: 0,
  });
  footer(s, 5);
}

// ---------- 6. Impact ----------
{
  const s = pres.addSlide();
  s._darkFooter = true;
  s.background = { color: TEAL };
  s.addText("BUSINESS IMPACT · BACKTEST ON SYNTHETIC DATA", { x: 0.6, y: 0.4, w: 12, h: 0.35, fontFace: MONO, fontSize: 13, color: TEALDARK, charSpacing: 2, isTextBox: true, margin: 0 });
  s.addText("Less wasted spend, modest margin gain", { x: 0.6, y: 0.8, w: 11.8, h: 0.75, fontFace: HEAD, fontSize: 30, bold: true, color: TEALDARK, isTextBox: true, margin: 0 });

  const rows = [
    [{ text: "Per demand spike", options: { bold: true } }, { text: "Campaign alone", options: { bold: true, align: "right" } }, { text: "With orchestrator", options: { bold: true, align: "right" } }],
    ["Spend chasing unservable demand", { text: "EUR 7,480", options: { align: "right" } }, { text: "EUR 5,590 (-25%)", options: { align: "right", bold: true } }],
    ["Incremental margin", { text: "EUR 199.9k", options: { align: "right" } }, { text: "+EUR 1.2k to +2.2k", options: { align: "right", bold: true } }],
    ["Demand lost to stockouts", { text: "1,971 units", options: { align: "right" } }, { text: "1,992 (no change)", options: { align: "right", bold: true } }],
    ["Spikes detected", { text: "n/a", options: { align: "right" } }, { text: "477 of 480 (99%)", options: { align: "right", bold: true } }],
  ].map(r => r.map(c => (typeof c === "string" ? { text: c } : c)));

  s.addTable(rows, {
    x: 0.6, y: 1.75, w: 12.1, h: 2.6,
    fontFace: SANS, fontSize: 15, color: TEALDARK,
    border: { type: "solid", color: "0FA898", pt: 0.5 },
    fill: { color: "2DD4BF" },
    colW: [4.6, 3.6, 3.9],
    autoPage: false,
  });

  s.addText(
    "20 held-out synthetic worlds, 480 spikes, 95% confidence intervals above zero. Margin range: conservative to assuming 1.8x return on reallocated spend. Gain sits in stock-short spikes (+EUR 2.7k to 4.3k); stock-sufficient spikes lose EUR 0.7k to 0.8k. Synthetic and assumption-driven, not a forecast.",
    { x: 0.6, y: 4.65, w: 12.1, h: 1.4, fontFace: SANS, fontSize: 13.5, color: TEALDARK, isTextBox: true, margin: 0 }
  );
  footer(s, 6);
}

// ---------- 7. Assets ----------
{
  const s = pres.addSlide();
  s._darkFooter = false;
  s.background = { color: NAVY };
  s.addText("CAPGEMINI ASSETS · TO CONFIRM WITH MENTOR", { x: 0.6, y: 0.4, w: 12, h: 0.35, fontFace: MONO, fontSize: 13, color: TEAL, charSpacing: 2, isTextBox: true, margin: 0 });
  s.addText("Where Capgemini accelerators plug in", { x: 0.6, y: 0.8, w: 11.5, h: 0.75, fontFace: HEAD, fontSize: 30, bold: true, color: INK, isTextBox: true, margin: 0 });

  const rows = [
    [{ text: "Layer", options: { bold: true, color: TEAL } }, { text: "What it does", options: { bold: true, color: TEAL } }, { text: "Capgemini asset", options: { bold: true, color: TEAL } }],
    ["Signal layer", "Unified demand, inventory and customer events", { text: "[Asset to confirm]", options: { color: AMBER } }],
    ["Agent runtime", "Six domain agents plus the orchestrator", { text: "[Asset to confirm]", options: { color: AMBER } }],
    ["Governance", "Autonomy tiers, audit trail, consent checks", { text: "[Asset to confirm]", options: { color: AMBER } }],
    ["Delivery", "Pilot in 2 markets, then scale to all 8", { text: "[Asset to confirm]", options: { color: AMBER } }],
  ].map(r => r.map(c => (typeof c === "string" ? { text: c, options: { color: INK } } : c)));

  s.addTable(rows, {
    x: 0.6, y: 1.7, w: 12.1, h: 2.7,
    fontFace: SANS, fontSize: 14,
    border: { type: "solid", color: LINE, pt: 0.75 },
    fill: { color: NAVY2 },
    colW: [2.4, 5.8, 3.9],
    autoPage: false,
  });

  s.addText(
    "Autonomy tiers: auto-execute for low-risk changes, human approval above EUR 15k, human-led for brand-sensitive decisions.",
    { x: 0.6, y: 4.7, w: 11.8, h: 0.7, fontFace: SANS, fontSize: 15, color: BODY, isTextBox: true, margin: 0 }
  );
  footer(s, 7);
}

// ---------- 8. Roadmap ----------
{
  const s = pres.addSlide();
  s._darkFooter = false;
  s.background = { color: NAVY2 };
  s.addText("18-MONTH ROADMAP · ONE TEAM", { x: 0.6, y: 0.4, w: 12, h: 0.35, fontFace: MONO, fontSize: 13, color: TEAL, charSpacing: 2, isTextBox: true, margin: 0 });
  s.addText("From decision support to a closed loop", { x: 0.6, y: 0.8, w: 11.8, h: 0.75, fontFace: HEAD, fontSize: 30, bold: true, color: INK, isTextBox: true, margin: 0 });

  const phases = [
    ["Months 0-6", TEAL, ["Unified demand signal layer", "Sensing Agent as decision support", "Two pilot markets"]],
    ["Months 7-12", BLUE, ["Campaign, Promo and Creative agents", "Orchestrator with stock guardrail", "Human-approved actions"]],
    ["Months 13-18", AMBER, ["All 8 markets", "Auto-execute for low-risk tiers", "Closed loop with Merchandising and Sourcing"]],
  ];
  const cw = 3.9, gap = 0.2, x0 = 0.6, y0 = 1.75, h = 2.9;
  phases.forEach((p, i) => {
    const x = x0 + i * (cw + gap);
    card(s, x, y0, cw, h, { fill: NAVY });
    s.addText(p[0], { x: x + 0.28, y: y0 + 0.22, w: cw - 0.56, h: 0.45, fontFace: HEAD, fontSize: 17, bold: true, color: p[1], isTextBox: true, margin: 0 });
    const bullets = p[2].map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < p[2].length - 1, color: INK, fontSize: 13.5, paraSpaceAfter: 8 } }));
    s.addText(bullets, { x: x + 0.28, y: y0 + 0.8, w: cw - 0.56, h: h - 1.0, fontFace: SANS, isTextBox: true, margin: 0 });
  });

  card(s, 0.6, 4.95, 12.1, 1.55, { fill: NAVY, lineColor: TEAL });
  s.addText("One Team interfaces", { x: 0.9, y: 5.15, w: 5, h: 0.4, fontFace: HEAD, fontSize: 16, bold: true, color: TEAL, isTextBox: true, margin: 0 });
  s.addText("Merchandising receives allocation requests. Sourcing receives replenishment requests. Logistics and Commerce receive demand-shaped service levels.", {
    x: 0.9, y: 5.6, w: 11.5, h: 0.75, fontFace: SANS, fontSize: 14.5, color: INK, isTextBox: true, margin: 0,
  });
  footer(s, 8);
}

pres.writeFile({ fileName: "aurelia-demand-command-deck.pptx" }).then(() => console.log("done"));
