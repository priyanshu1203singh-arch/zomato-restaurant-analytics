/**
 * 04_verify_dashboard.mjs
 * =======================
 * Headless verification of the built dashboard. This is the test suite:
 *   1. the page loads from file:// with ZERO console errors
 *   2. the self-check table (browser JS vs pandas) reports no mismatches
 *   3. every tab renders SVG marks, not an empty div
 *   4. slicers actually change the KPI numbers (cross-filtering works)
 *   5. screenshots of every page are written to assets/ for the README
 *
 * Run:  node scripts/04_verify_dashboard.mjs
 */
import { chromium } from "playwright";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(import.meta.dirname, "..");
const FILE = "file://" + path.join(ROOT, "dashboard", "zomato_dashboard.html");
const SHOTS = path.join(ROOT, "assets");
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const check = (name, pass, detail = "") => {
  results.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });

const errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

await page.goto(FILE, { waitUntil: "load" });
await page.waitForTimeout(1200);

check("page loads with no JS errors", errors.length === 0, errors.slice(0, 4).join(" | "));

// ---- 1. header facts populated -------------------------------------------
const hdr = await page.textContent("#hdr-count");
check("header restaurant count populated", hdr === "8,652", `got "${hdr}"`);

// ---- 2. KPI tiles --------------------------------------------------------
const tiles = await page.$$eval("#kpiStrip .tile", els =>
  els.map(e => [e.querySelector(".k").textContent, e.querySelector(".v").textContent]));
check("8 KPI tiles render", tiles.length === 8, JSON.stringify(tiles.slice(0, 3)));
const kv = Object.fromEntries(tiles);
check("Avg cost tile = ₹624", kv["Avg cost for two"] === "₹624", kv["Avg cost for two"]);
check("Avg rating tile = 3.35", kv["Avg rating"] === "3.35", kv["Avg rating"]);
check("Restaurants tile = 8,652", kv["Restaurants"] === "8,652", kv["Restaurants"]);

// ---- 3. each page renders marks ------------------------------------------
const pages = ["overview", "cost", "cuisine", "opportunity", "method"];
for (const p of pages) {
  await page.click(`nav.tabs button[data-page="${p}"]`);
  await page.waitForTimeout(700);
  const marks = await page.$$eval(`#page-${p} svg`, els =>
    els.reduce((s, e) => s + e.querySelectorAll("path,circle,rect,line").length, 0));
  const min = p === "method" ? 0 : 30;
  check(`page "${p}" renders svg marks`, marks >= min, `${marks} marks`);
  await page.screenshot({ path: path.join(SHOTS, `page-${p}.png`), fullPage: true });
}

// ---- 4. self-check table (JS vs pandas) ----------------------------------
await page.click('nav.tabs button[data-page="method"]');
await page.waitForTimeout(500);
const selfCheck = await page.$$eval("#selfCheck tbody tr, #selfCheck tr", rows =>
  rows.slice(1).map(r => [...r.querySelectorAll("td")].map(td => td.textContent.trim())));
const mismatches = selfCheck.filter(r => r[3] && r[3].includes("differs"));
check("pandas <-> JS self-check: all KPIs agree",
  selfCheck.length > 0 && mismatches.length === 0,
  `${selfCheck.length} checked, ${mismatches.length} mismatched ${JSON.stringify(mismatches)}`);

// ---- 5. cross-filtering actually filters ---------------------------------
await page.click('nav.tabs button[data-page="overview"]');
await page.waitForTimeout(400);
const before = await page.textContent("#kpiStrip .tile .v");
await page.selectOption("#fCity", "Bangalore");
await page.waitForTimeout(500);
const after = await page.textContent("#kpiStrip .tile .v");
const note = await page.textContent("#activeNote");
check("city slicer changes the KPI", before !== after, `${before} -> ${after}`);
check("active-filter note reflects the slicer", note.includes("Bangalore"), note.slice(0, 90));

await page.click("#resetBtn");
await page.waitForTimeout(500);
const reset = await page.textContent("#kpiStrip .tile .v");
check("reset restores the unfiltered KPI", reset === before, `${reset} vs ${before}`);

// ---- 6. price chip slicer -------------------------------------------------
await page.click('#fPrice .chip[data-p="4"]');
await page.waitForTimeout(500);
const lux = await page.textContent("#kpiStrip .tile .v");
check("luxury chip narrows to 388 restaurants", lux === "388", lux);
await page.click("#resetBtn");
await page.waitForTimeout(300);

// ---- 7. chart click cross-filters ---------------------------------------
await page.waitForTimeout(400);
await page.click('#chCities [data-click]');
await page.waitForTimeout(500);
const clicked = await page.textContent("#activeNote");
check("clicking a city bar cross-filters", clicked.includes("City:"), clicked.slice(0, 80));
await page.click("#resetBtn");

// ---- 8. table-view toggle (accessibility relief) -------------------------
await page.waitForTimeout(400);
await page.click('.tbtn[data-table="chRatingDist"]');
await page.waitForTimeout(300);
const tblRows = await page.$$eval(".chart-table table tr", r => r.length);
check("chart table-view toggle produces a data table", tblRows > 2, `${tblRows} rows`);

// ---- 9. dark mode --------------------------------------------------------
await page.click("#themeBtn");
await page.waitForTimeout(700);
await page.click('nav.tabs button[data-page="overview"]');
await page.waitForTimeout(600);
const theme = await page.getAttribute("html", "data-theme");
check("dark mode applies", theme === "dark", theme);
await page.screenshot({ path: path.join(SHOTS, "page-overview-dark.png"), fullPage: true });

await browser.close();

// ---- 10. shrink the screenshots so the repo stays small -------------------
// Captured at deviceScaleFactor 2 for sharpness, then halved and palette-reduced.
// 4.6 MB of PNGs becomes ~1.4 MB with no visible loss on flat UI screenshots.
try {
  const sharp = (await import("sharp")).default;
  let before = 0, after = 0;
  for (const f of fs.readdirSync(SHOTS).filter(f => f.endsWith(".png"))) {
    const p = path.join(SHOTS, f);
    before += fs.statSync(p).size;
    const meta = await sharp(p).metadata();
    const buf = await sharp(p)
      .resize(Math.round(meta.width / 2))
      .png({ palette: true, colours: 192, compressionLevel: 9 })
      .toBuffer();
    fs.writeFileSync(p, buf);
    after += buf.length;
  }
  check("screenshots optimised for the repo", after < before,
    `${Math.round(before / 1024)} KB -> ${Math.round(after / 1024)} KB`);
} catch (e) {
  console.log(`SKIP  screenshot optimisation (sharp not installed): ${e.message}`);
}

const failed = results.filter(r => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
fs.writeFileSync(path.join(ROOT, "docs", "verification_report.json"),
  JSON.stringify({ checks: results, screenshots: fs.readdirSync(SHOTS) }, null, 2));
if (failed.length) process.exit(1);
