/**
 * tests/test_streamlit_app.mjs
 * ============================
 * Drive the running Streamlit app in headless Chromium and assert it actually
 * renders and filters. Complements tests/test_streamlit_measures.py, which
 * checks the maths without a browser.
 *
 * Usage:
 *   streamlit run streamlit_app.py --server.headless true &
 *   node tests/test_streamlit_app.mjs
 */
import { chromium } from "playwright";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(import.meta.dirname, "..");
const URL = process.env.APP_URL || "http://127.0.0.1:8501";
const SHOTS = path.join(ROOT, "assets");
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, pass, detail = "") => {
  results.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
const page = await browser.newPage({
  viewport: { width: 1500, height: 1000 },
  deviceScaleFactor: 2,
});

const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

await page.goto(URL, { waitUntil: "networkidle", timeout: 90_000 });
// Streamlit streams the script result in; wait for the last tab to exist.
await page.waitForSelector('[data-testid="stTab"]', { timeout: 60_000 });
await page.waitForTimeout(6000);

check("app loads with no page errors", errors.length === 0, errors.slice(0, 3).join(" | "));

// ---- title + scope line ---------------------------------------------------
const h1 = await page.textContent("h1");
check("title renders", /Zomato Restaurant Analytics/.test(h1 || ""), h1);

const body = await page.textContent("body");
check("scope line shows the unfiltered row count", body.includes("8,652 of 8,652"),
  (body.match(/[\d,]+ of [\d,]+ restaurants in scope/) || ["not found"])[0]);

// ---- KPI tiles ------------------------------------------------------------
// Streamlit keeps every tab's DOM mounted and hides the inactive panels, so a
// bare querySelectorAll would collect tiles from all five pages. Everything
// below is scoped to what is actually visible. Labels are compared lowercased
// because the stylesheet applies `text-transform: uppercase`, which innerText
// reflects.
const visibleMetrics = () => page.$$eval('[data-testid="stMetric"]', els =>
  Object.fromEntries(els
    .filter(e => e.offsetParent !== null)
    .map(e => [
      e.querySelector('[data-testid="stMetricLabel"]')?.innerText.trim().toLowerCase(),
      e.querySelector('[data-testid="stMetricValue"]')?.innerText.trim(),
    ])));

const byLabel = await visibleMetrics();
check("8 KPI tiles render on page 1", Object.keys(byLabel).length === 8,
  `${Object.keys(byLabel).length} visible tiles`);
check("Restaurants tile = 8,652", byLabel["restaurants"] === "8,652", byLabel["restaurants"]);
check("Avg cost tile = ₹624", byLabel["avg cost for two"] === "₹624", byLabel["avg cost for two"]);
check("Avg rating tile = 3.35", byLabel["avg rating"] === "3.35", byLabel["avg rating"]);
check("Not rated tile = 24.7%", byLabel["not rated"] === "24.7%", byLabel["not rated"]);

// ---- every tab renders plotly charts / tables ----------------------------
const tabs = await page.$$('[data-testid="stTab"]');
check("five tabs present", tabs.length === 5, `${tabs.length} tabs`);

const tabNames = ["overview", "cost", "cuisine", "opportunity", "method"];
for (let i = 0; i < tabs.length; i++) {
  await tabs[i].click();
  await page.waitForTimeout(4500);
  const { charts, tables, text } = await page.evaluate(() => {
    const panel = [...document.querySelectorAll('[data-testid="stTabPanel"]')]
      .find(e => e.offsetParent !== null);
    if (!panel) return { charts: 0, tables: 0, text: 0 };
    return {
      charts: panel.querySelectorAll('[data-testid="stPlotlyChart"]').length,
      tables: panel.querySelectorAll('[data-testid="stDataFrame"]').length,
      text: panel.innerText.length,
    };
  });
  const ok = tabNames[i] === "method" ? (tables >= 1 && text > 1500) : charts >= 1;
  check(`tab "${tabNames[i]}" renders content`, ok,
    `${charts} charts, ${tables} tables, ${text} chars`);
  await page.screenshot({ path: path.join(SHOTS, `streamlit-${tabNames[i]}.png`), fullPage: true });
}

// ---- the sidebar filters actually filter ---------------------------------
await tabs[0].click();
await page.waitForTimeout(2500);

// City multiselect -> Bangalore. Type into the combobox input, wait for the
// option list, then commit with Enter.
const cityInput = page.locator('[data-testid="stSidebar"] [data-testid="stMultiSelect"] input').first();
await cityInput.click();
await cityInput.type("Bangalore", { delay: 60 });
await page.waitForTimeout(1800);
// Click the option itself rather than pressing Enter — the combobox does not
// pre-highlight the first match, so Enter alone is a no-op.
await page.getByText(/^Bangalore \(\d+\)$/).first().click();
await page.waitForTimeout(6000);

const filteredBody = await page.textContent("body");
check("city filter changes the scope line", filteredBody.includes("20 of 8,652"),
  (filteredBody.match(/[\d,]+ of [\d,]+ restaurants in scope/) || ["not found"])[0]);
check("active-filter chip names the city", filteredBody.includes("City: Bangalore"),
  "City: Bangalore");

const filteredMetrics = await visibleMetrics();
check("KPI tile recomputes under the filter",
  filteredMetrics["restaurants"] === "20",
  `Restaurants = ${filteredMetrics["restaurants"]}, `
  + `avg rating ${filteredMetrics["avg rating"]}`);

await page.screenshot({ path: path.join(SHOTS, "streamlit-filtered.png"), fullPage: true });

// ---- shrink screenshots ---------------------------------------------------
try {
  const sharp = (await import("sharp")).default;
  let before = 0, after = 0;
  for (const f of fs.readdirSync(SHOTS).filter(f => f.startsWith("streamlit-"))) {
    const p = path.join(SHOTS, f);
    before += fs.statSync(p).size;
    const meta = await sharp(p).metadata();
    const buf = await sharp(p).resize(Math.round(meta.width / 2))
      .png({ palette: true, colours: 192, compressionLevel: 9 }).toBuffer();
    fs.writeFileSync(p, buf);
    after += buf.length;
  }
  check("screenshots optimised", after < before,
    `${Math.round(before / 1024)} KB -> ${Math.round(after / 1024)} KB`);
} catch (e) {
  console.log(`SKIP  screenshot optimisation: ${e.message}`);
}

await browser.close();

const failed = results.filter(r => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} Streamlit UI checks passed`);
fs.writeFileSync(path.join(ROOT, "docs", "streamlit_ui_report.json"),
  JSON.stringify(results, null, 2));
if (failed.length) process.exit(1);
