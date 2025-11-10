"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";
import {
  formatSentimentScore,
  getSentimentBadgeVariant,
  formatNewsDate,
} from "@/lib/utils/news-formatting";

interface KeyEvent {
    icon: string;
    text: string;
    time_ago: string;
    is_material: boolean;
    event_category?: string | null;
    published_at?: string | null;
}

interface NewsArticle {
    ticker: string;
    headline: string;
    url?: string | null;
    source?: string | null;
    published_at?: string | null;
    sentiment_score: number;
    sentiment_label: string;
    plain_language_headline?: string | null;
    impact_summary?: string | null;
    actionable_insight?: string | null;
}

interface NewsIntelligence {
    headline: string;
    sentiment_score: number;
    sentiment_label: string;
    article_count_24h: number;
    key_events: KeyEvent[];
    recent_articles: NewsArticle[];
}

interface NewsIntelligenceCardProps {
    newsIntelligence: NewsIntelligence | null | undefined;
    newsHidden: boolean;
}

export function NewsIntelligenceCard({
    newsIntelligence,
    newsHidden,
}: NewsIntelligenceCardProps) {
    if (newsHidden) return null;
    if (!newsIntelligence) return null;

    return (
        <Card className="border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-base">📰 News Intelligence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Headline Summary */}
                <div>
                    <h4 className="text-sm font-semibold text-text mb-2">
                        {newsIntelligence.headline}
                    </h4>
                    <div className="flex flex-wrap items-center gap-3 text-xs">
                        <div>
                            <span className="text-text-muted">Sentiment: </span>
                            <Badge
                                variant={getSentimentBadgeVariant(
                                    newsIntelligence.sentiment_label,
                                )}
                            >
                                {newsIntelligence.sentiment_label}{" "}
                                ({formatSentimentScore(newsIntelligence.sentiment_score)})
                            </Badge>
                        </div>
                        <div className="text-text-muted">
                            {newsIntelligence.article_count_24h} articles in 24h
                        </div>
                    </div>
                </div>

                {/* Key Events */}
                {newsIntelligence.key_events.length > 0 && (
                    <div>
                        <h5 className="text-xs font-semibold text-text mb-2">
                            Key Events:
                        </h5>
                        <div className="space-y-2">
                            {newsIntelligence.key_events.map((event, idx) => (
                                <div
                                    key={`event-${idx}-${event.text.substring(0, 20)}`}
                                    className="flex items-start gap-2 text-xs"
                                >
                                    <span className="text-base flex-shrink-0">
                                        {event.icon}
                                    </span>
                                    <div className="flex-1">
                                        <span className="text-text">
                                            {event.text}
                                        </span>
                                        <span className="text-text-muted ml-2">
                                            ({event.time_ago})
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Recent Articles */}
                {newsIntelligence.recent_articles.length > 0 && (
                    <div>
                        <h5 className="text-xs font-semibold text-text mb-2">
                            Recent Articles (showing{" "}
                            {newsIntelligence.recent_articles.length}):
                        </h5>
                        <div className="space-y-2">
                            {newsIntelligence.recent_articles.map(
                                (article, idx) => {
                                    const displayHeadline =
                                        article.plain_language_headline ||
                                        article.headline;
                                    const articleKey =
                                        article.url ||
                                        `news-${idx}-${article.headline.substring(0, 30)}`;
                                    return (
                                        <div
                                            key={articleKey}
                                            className="rounded-md border border-border bg-surface-muted/20 p-2 space-y-1"
                                        >
                                            {article.url ? (
                                                <a
                                                    href={article.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                                                >
                                                    {displayHeadline}
                                                    <ExternalLink className="h-3 w-3 flex-shrink-0" />
                                                </a>
                                            ) : (
                                                <p className="text-xs font-medium text-text">
                                                    {displayHeadline}
                                                </p>
                                            )}
                                            <div className="flex flex-wrap items-center gap-2 text-[10px] text-text-muted">
                                                {article.source && (
                                                    <span>{article.source}</span>
                                                )}
                                                {article.published_at && (
                                                    <span>·</span>
                                                )}
                                                {article.published_at && (
                                                    <span>
                                                        {formatNewsDate(article.published_at)}
                                                    </span>
                                                )}
                                                {article.sentiment_label && (
                                                    <>
                                                        <span>·</span>
                                                        <Badge
                                                            variant={getSentimentBadgeVariant(
                                                                article.sentiment_label,
                                                            )}
                                                            className="text-[9px] px-1.5 py-0"
                                                        >
                                                            {
                                                                article.sentiment_label
                                                            }
                                                        </Badge>
                                                    </>
                                                )}
                                            </div>
                                            {article.impact_summary && (
                                                <p className="text-xs text-text-muted italic">
                                                    💡 {article.impact_summary}
                                                </p>
                                            )}
                                            {article.actionable_insight && (
                                                <p className="text-xs text-primary font-medium mt-1">
                                                    💡 {article.actionable_insight}
                                                </p>
                                            )}
                                        </div>
                                    );
                                },
                            )}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
