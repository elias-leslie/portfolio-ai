import { test, expect } from "@playwright/test";
import { registerNewsMocks } from "./utils/mockData";

test.describe("News Intelligence hub", () => {
  test.beforeEach(async ({ page }) => {
    await registerNewsMocks(page);
  });

  test("loads market headlines and sentiment summary", async ({ page }) => {
    await page.goto("/news");

    await expect(page.getByRole("heading", { name: "News Intelligence" })).toBeVisible();

    const summaryCard = page
      .getByRole("heading", { name: "Market Overview" })
      .locator("..")
      .locator("..");

    await expect(page.getByText("FinBERT 18/22")).toBeVisible();
    await expect(page.getByText("+0.34")).toBeVisible();
    await expect(page.getByText("+0.08", { exact: false })).toBeVisible();

    await expect(page.getByRole("link", { name: /beats expectations/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /regulatory scrutiny/i })).toBeVisible();

    await page.getByRole("button", { name: "Refresh" }).click();
    await expect(page.getByRole("button", { name: "Refresh" })).not.toBeDisabled();

    const screenshotPath = test.info().outputPath("news-market.png");
    await page.screenshot({ path: screenshotPath, fullPage: true });
    test.info().attach("state-market", { path: screenshotPath, contentType: "image/png" });
  });

  test("switches to watchlist view and renders per-symbol bundles", async ({ page }) => {
    await page.goto("/news");

    await page.getByRole("button", { name: "My Watchlist" }).click();

    await expect(page.getByText("Symbol: AAPL")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Symbol: MSFT")).toBeVisible();

    await expect(page.getByText("FinBERT 6/7")).toBeVisible();
    await expect(page.getByText("+0.56")).toBeVisible();

    await expect(
      page.locator('[data-testid="article-card"]').first(),
    ).toBeVisible();

    const screenshotPath = test.info().outputPath("news-watchlist.png");
    await page.screenshot({ path: screenshotPath, fullPage: true });
    test.info().attach("state-watchlist", { path: screenshotPath, contentType: "image/png" });

    await page.goto("/watchlist");
    const watchlistRow = page.getByRole("row", { name: /AAPL/ }).first();
    await expect(watchlistRow).toBeVisible();
    await watchlistRow.click();
    await expect(page.getByTestId("watchlist-news-card")).toBeVisible();
  });

  test("hides watchlist headlines when user disables preference", async ({ page }) => {
    await page.goto("/news");
    await page.getByRole("button", { name: "My Watchlist" }).click();
    await expect(page.getByText("Symbol: AAPL")).toBeVisible();

    await page.goto("/settings");

    const toggle = page.getByRole("checkbox", {
      name: "Show news sentiment and headlines in watchlist",
    });
    await expect(toggle).toBeChecked();

    const settingsBeforePath = test.info().outputPath("settings-watchlist-news-enabled.png");
    await page.screenshot({ path: settingsBeforePath, fullPage: true });
    test.info().attach("settings-before", {
      path: settingsBeforePath,
      contentType: "image/png",
    });

    await toggle.uncheck();

    await page.getByRole("button", { name: "Save Changes" }).first().click();
    await expect(page.getByText("Watchlist preferences updated")).toBeVisible();

    const settingsAfterPath = test.info().outputPath("settings-watchlist-news-disabled.png");
    await page.screenshot({ path: settingsAfterPath, fullPage: true });
    test.info().attach("settings-after", {
      path: settingsAfterPath,
      contentType: "image/png",
    });

    await page.goto("/news");
    await page.getByRole("button", { name: "My Watchlist" }).click();

    await expect(page.getByTestId("news-hidden")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('[data-testid="article-card"]')).toHaveCount(0);

    const screenshotPath = test.info().outputPath("news-watchlist-hidden.png");
    await page.screenshot({ path: screenshotPath, fullPage: true });
    test.info().attach("state-watchlist-hidden", {
      path: screenshotPath,
      contentType: "image/png",
    });

    await page.goto("/watchlist");
    const hiddenRow = page.getByRole("row", { name: /AAPL/ }).first();
    await expect(hiddenRow).toBeVisible();
    await hiddenRow.click();
    await expect(page.getByTestId("watchlist-news-hidden-card")).toBeVisible();
    await expect(page.getByTestId("watchlist-news-hidden")).toBeVisible();
  });
});
