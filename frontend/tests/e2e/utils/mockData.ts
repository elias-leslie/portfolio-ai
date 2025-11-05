import type { Page, Route } from "@playwright/test";

interface MockState {
  showNews: boolean;
  refreshTimestamp: string;
}

const DEFAULT_TIMESTAMP = new Date("2025-11-05T14:30:00Z").toISOString();

const basePreferences = {
  risk_tolerance: 5,
  allow_long: true,
  allow_short: false,
  allow_options: true,
  allow_crypto: false,
  allow_futures: false,
  max_position_size_pct: 20,
  default_refresh_minutes: 5,
  watchlist_refresh_override: null,
  portfolio_refresh_override: null,
  news_refresh_override: null,
  frontend_poll_interval: 30,
  watchlist_refresh_minutes: 5,
  watchlist_auto_expand: false,
  watchlist_price_weight: 50,
  watchlist_technical_weight: 50,
  display_timezone: "America/New_York",
};

const baseWatchlistItems = [
  {
    id: "item-aapl",
    account_id: "default",
    symbol: "AAPL",
    note: "Hold through earnings",
    created_at: DEFAULT_TIMESTAMP,
    updated_at: DEFAULT_TIMESTAMP,
    current_score: null,
    news_sentiment_score: 0.42,
    recent_news: null,
  },
  {
    id: "item-msft",
    account_id: "default",
    symbol: "MSFT",
    note: null,
    created_at: DEFAULT_TIMESTAMP,
    updated_at: DEFAULT_TIMESTAMP,
    current_score: null,
    news_sentiment_score: -0.12,
    recent_news: null,
  },
];

const finbertArticle = (ticker: string, overrides: Partial<Record<string, unknown>> = {}) => ({
  ticker,
  headline: `${ticker} beats expectations amid strong demand`,
  url: `https://example.com/${ticker.toLowerCase()}-headline`,
  summary: `${ticker} reports robust quarter with accelerating revenue.`,
  source: "Example Times",
  author: "Finance Desk",
  image_url: null,
  published_at: DEFAULT_TIMESTAMP,
  fetched_at: DEFAULT_TIMESTAMP,
  sentiment: {
    score: 0.68,
    label: "positive",
    confidence: 0.87,
    model: "finbert",
    probabilities: {
      positive: 0.87,
      neutral: 0.10,
      negative: 0.03,
    },
  },
  content_hash: `${ticker}-finbert-1`,
  raw: {},
  ...overrides,
});

const fallbackArticle = (ticker: string) => ({
  ...finbertArticle(ticker, {
    headline: `${ticker} faces regulatory scrutiny`,
    sentiment: {
      score: -0.32,
      label: "negative",
      confidence: 0.61,
      model: "vader",
    },
    content_hash: `${ticker}-fallback-1`,
  }),
});

function buildMarketBundle(state: MockState) {
  return {
    ticker: "MARKET",
    summary: {
      score: 0.34,
      score_change: 0.08,
      positive_count: 12,
      neutral_count: 6,
      negative_count: 4,
      article_count: 22,
      latest_published_at: state.refreshTimestamp,
      top_positive: finbertArticle("MARKET"),
      top_negative: fallbackArticle("MARKET"),
      model_breakdown: {
        finbert: 18,
        vader: 4,
      },
    },
    articles: [
      finbertArticle("SPY", { content_hash: "spy-1" }),
      fallbackArticle("QQQ"),
      finbertArticle("DIA", { headline: "Dow components rally on macro optimism" }),
    ],
  };
}

function buildWatchlistBundles(state: MockState) {
  if (!state.showNews) {
    return [];
  }
  return [
    {
      ticker: "AAPL",
      summary: {
        score: 0.56,
        score_change: 0.14,
        positive_count: 4,
        neutral_count: 2,
        negative_count: 1,
        article_count: 7,
        latest_published_at: state.refreshTimestamp,
        top_positive: finbertArticle("AAPL"),
        top_negative: fallbackArticle("AAPL"),
        model_breakdown: {
          finbert: 6,
          vader: 1,
        },
      },
      articles: [
        finbertArticle("AAPL"),
        fallbackArticle("AAPL"),
        finbertArticle("AAPL", {
          headline: "Supply chain stabilizes heading into holiday season",
          content_hash: "aapl-unique-3",
        }),
      ],
    },
    {
      ticker: "MSFT",
      summary: {
        score: -0.22,
        score_change: -0.05,
        positive_count: 1,
        neutral_count: 3,
        negative_count: 2,
        article_count: 6,
        latest_published_at: state.refreshTimestamp,
        top_positive: finbertArticle("MSFT"),
        top_negative: fallbackArticle("MSFT"),
        model_breakdown: {
          finbert: 4,
          vader: 2,
        },
      },
      articles: [
        finbertArticle("MSFT"),
        fallbackArticle("MSFT"),
        finbertArticle("MSFT", {
          headline: "Azure consumption steady despite macro jitters",
          content_hash: "msft-unique-3",
        }),
      ],
    },
  ];
}

function buildWatchlistItems(state: MockState) {
  const bundles = buildWatchlistBundles({ ...state, showNews: true });
  const bundleMap = new Map(bundles.map((bundle) => [bundle.ticker, bundle]));

  return baseWatchlistItems.map((item) => {
    const bundle = bundleMap.get(item.symbol);
    return {
      ...item,
      news_sentiment_score: bundle?.summary.score ?? item.news_sentiment_score,
      recent_news: bundle
        ? {
            summary: bundle.summary,
            articles: bundle.articles,
          }
        : {
            summary: null,
            articles: [],
          },
    };
  });
}

export async function registerNewsMocks(page: Page) {
  const state: MockState = {
    showNews: true,
    refreshTimestamp: DEFAULT_TIMESTAMP,
  };

  const fulfillJson = async (route: Route, data: unknown, status = 200) => {
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  };

  await page.route("**/api/preferences/", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      const body = request.postDataJSON() as { watchlist_show_news?: boolean } | null;
      if (body && Object.prototype.hasOwnProperty.call(body, "watchlist_show_news")) {
        state.showNews = Boolean(body.watchlist_show_news);
      }
      return fulfillJson(route, {
        ...basePreferences,
        watchlist_show_news: state.showNews,
      });
    }

    return fulfillJson(route, {
      ...basePreferences,
      watchlist_show_news: state.showNews,
    });
  });

  await page.route("**/api/watchlist?**", async (route) => {
    return fulfillJson(route, {
      items: buildWatchlistItems(state),
      total_count: baseWatchlistItems.length,
    });
  });

  await page.route("**/api/news/market**", async (route) => {
    return fulfillJson(route, buildMarketBundle(state));
  });

  await page.route("**/api/news/watchlist**", async (route) => {
    const items = buildWatchlistBundles(state);
    if (!state.showNews) {
      return fulfillJson(
        route,
        {
          account_id: "default",
          items,
          status: "hidden",
        },
        200,
      );
    }

    return fulfillJson(route, {
      account_id: "default",
      items,
    });
  });

  await page.route("**/api/news/symbol/**", async (route) => {
    // Fallback for symbol lookups in other panels
    const url = new URL(route.request().url());
    const symbol = url.pathname.split("/").pop() ?? "UNKNOWN";
    return fulfillJson(route, {
      ticker: symbol.toUpperCase(),
      ...buildMarketBundle(state),
    });
  });

  return state;
}
