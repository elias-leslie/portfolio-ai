/**
 * Trading Rules API Client
 */

import { get } from "./client";

export interface CatalystImpact {
  impact: number;
  durationDays: number;
}

export interface TradingRules {
  version: string;
  updated: string;
  updatedBy: string;
  positionSizing: {
    defaultRiskPercent: number;
    minRiskPercent: number;
    maxRiskPercent: number;
    minPositionValue: number;
    maxPositionPercent: number;
    maxSectorExposurePct: number;
    defaultKellyFraction: number;
    minTradesForKelly: number;
    minPositionPercent: number;
    maxPositionPercentAdv: number;
    minVolumeDays: number;
  };
  riskManagement: {
    portfolioDrawdownHaltPct: number;
    drawdownWarningLevel1: number;
    drawdownWarningLevel2: number;
    maxSingleTradeLossPct: number;
    defaultPositionLimit: number;
    defaultSectorLimit: number;
    warningThresholdPct: number;
  };
  technicalThresholds: {
    rsiPeriod: number;
    rsiOversold: number;
    rsiOverbought: number;
    rsiReversalZoneLow: [number, number];
    rsiReversalZoneHigh: [number, number];
    smaPeriods: number[];
    emaPeriods: number[];
    macdFast: number;
    macdSlow: number;
    macdSignal: number;
    bollingerPeriod: number;
    bollingerStdDev: number;
    bollingerLowerThreshold: number;
    bollingerUpperThreshold: number;
    atrPeriod: number;
    stopLossAtrMultiplier: number;
    stochasticKPeriod: number;
    stochasticDPeriod: number;
    stochasticSmoothK: number;
    stochasticOversold: number;
    stochasticOverbought: number;
    volumeSmaPeriod: number;
    volumeThresholdRatio: number;
    volumeHighThreshold: number;
    trendThresholdPct: number;
    lookbackDays: number;
    minDaysForSma200: number;
  };
  scoring: {
    priceWeight: number;
    technicalWeight: number;
    fundamentalWeight: number;
    valuationWeight: number;
    growthWeight: number;
    healthWeight: number;
    sentimentWeight: number;
    priceStaleTtlMinutes: number;
    technicalStaleTtlMinutes: number;
    buyConfirmationsThreshold: number;
    avoidFlagsThreshold: number;
    signalStrengthDivisor: number;
  };
  fundamentals: {
    profitMarginExcellent: number;
    profitMarginGood: number;
    profitMarginModerate: number;
    revenueGrowthExceptional: number;
    revenueGrowthStrong: number;
    revenueGrowthGood: number;
    revenueGrowthModerate: number;
    debtEquityExcellent: number;
    debtEquityGood: number;
    debtEquityModerate: number;
    debtEquityHigh: number;
    debtEquityWeak: number;
    analystStrongBuy: number;
    analystBuy: number;
    analystHold: number;
    analystNeutral: number;
    analystSell: number;
    analystBuyPctStrong: number;
    analystBuyPctModerate: number;
  };
  signals: {
    newsSentimentPositive: number;
    newsSentimentNegative: number;
    optionsStrongBullish: number;
    optionsModerateBullish: number;
    optionsSlightBullish: number;
    optionsBearish: number;
    earningsAvoidDays: number;
    earningsEventDays: number;
    strongBuyThreshold: number;
    buyThreshold: number;
  };
  fees: {
    slippageBps: number;
    slippageDynamicFactor: number;
    slippageInstitutionalBps: number;
    commissionPerShare: number;
    commissionPerTrade: number;
    commissionPct: number;
    commissionMinimum: number;
    commissionPerShareInstitutional: number;
    commissionMinimumInstitutional: number;
    defaultStopLossPct: number;
    defaultTargetGainPct: number;
    momentumTargetProfitPct: number;
    momentumStopLossPct: number;
  };
  compliance: {
    pdtDayTradeLimit: number;
    pdtRollingDays: number;
    pdtEquityThreshold: number;
    washSaleWindowDays: number;
  };
  market: {
    vixLow: number;
    vixNormal: number;
    vixElevated: number;
    vixHigh: number;
    treasury10YDovish: number;
    treasury10YHawkish: number;
    treasury10YVeryDovish: number;
    putCallBullish: number;
    defaultRiskFreeRate: number;
  };
  paperTrading: {
    maxHoldingDays: number;
    defaultPositionPct: number;
  };
  catalystImpacts: Record<string, CatalystImpact>;
  watchlistManagement: {
    maxWatchlistSize: number;
    maxDailyAdditions: number;
    maxDailyRemovals: number;
    discoveryScoreThreshold: number;
    gainersThresholdPct: number;
    volumeSpikeRatio: number;
    newsMentionThreshold: number;
    autoTrimEnabled: boolean;
    minDaysWatched: number;
    minScoreThreshold: number;
    excludePortfolioHoldings: boolean;
  };
}

export async function fetchRules(): Promise<TradingRules> {
  return get<TradingRules>("/api/rules");
}
