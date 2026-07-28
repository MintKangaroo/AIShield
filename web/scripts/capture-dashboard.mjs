import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";

import { chromium } from "playwright";

const baseUrl = process.env.AISHIELD_SCREENSHOT_URL ?? "http://127.0.0.1:5173";
const browserCdpUrl = process.env.AISHIELD_BROWSER_CDP;
const output = resolve(
  process.env.AISHIELD_SCREENSHOT_OUTPUT ?? "../docs/assets/dashboard-overview.png",
);

await mkdir(dirname(output), { recursive: true });
const browser = browserCdpUrl
  ? await chromium.connectOverCDP(browserCdpUrl)
  : await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    colorScheme: "dark",
    deviceScaleFactor: 1,
    viewport: { width: 1440, height: 1050 },
  });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  if (process.env.AISHIELD_SCREENSHOT_RUN_DEMO === "true") {
    const demoButton = page.getByRole("button", { name: "Launch zero-download demo" });
    if (await demoButton.isVisible()) {
      await demoButton.click();
      await page.getByText("Local demo completed", { exact: false }).waitFor({
        state: "visible",
        timeout: 120_000,
      });
      await page.locator(".toast").waitFor({ state: "hidden", timeout: 10_000 });
    }
  }
  const targetPage = process.env.AISHIELD_SCREENSHOT_PAGE;
  if (targetPage) {
    const navigationLabels = {
      artifacts: "Artifacts",
      attacks: "Attack lab",
      registry: "Registry",
      runs: "Baseline runs",
    };
    const label = navigationLabels[targetPage];
    if (!label) {
      throw new Error(`Unknown dashboard screenshot page: ${targetPage}`);
    }
    await page.getByRole("button", { name: label }).click();
  }
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: output,
  });
  console.log(`Dashboard screenshot saved to ${output}`);
} finally {
  await browser.close();
}
