'use client'

import { ProfileSelector } from '@/components/settings/ProfileSelector'
import { SaveBar } from '@/components/settings/SaveBar'
import { SettingsSection } from '@/components/settings/SettingsSection'
import { DisplaySettings } from '@/components/settings/sections/DisplaySettings'
import { TradingRiskSettings } from '@/components/settings/sections/TradingRiskSettings'
import { WatchlistSettingsSection } from '@/components/settings/sections/WatchlistSettingsSection'
import { PageContainer } from '@/components/shared/PageContainer'
import { PageHeader } from '@/components/shared/PageHeader'
import { useSettingsState } from './useSettingsState'

export default function SettingsPage() {
  const {
    riskTolerance,
    allowLong,
    allowShort,
    allowOptions,
    allowCrypto,
    allowFutures,
    maxPositionSizePct,
    displayTimezone,
    defaultRefreshMinutes,
    watchlistOverride,
    newsOverride,
    newsLookbackHours,
    newsMaxArticles,
    showNews,
    autoExpand,
    scoreWeights,
    technicalSubWeights,
    fundamentalSubWeights,
    setRiskTolerance,
    setAllowLong,
    setAllowShort,
    setAllowOptions,
    setAllowCrypto,
    setAllowFutures,
    setMaxPositionSizePct,
    setDisplayTimezone,
    setDefaultRefreshMinutes,
    setWatchlistOverride,
    setNewsOverride,
    setNewsLookbackHours,
    setNewsMaxArticles,
    setShowNews,
    setAutoExpand,
    setScoreWeights,
    setTechnicalSubWeights,
    setFundamentalSubWeights,
    hasChanges,
    changeCount,
    tradingSummary,
    displaySummary,
    watchlistSummary,
    handleSaveAll,
    handleResetAll,
    handleProfileLoad,
    getCurrentPreferences,
    preferences,
    isLoading,
    isPending,
  } = useSettingsState()

  if (isLoading) {
    return (
      <PageContainer className="max-w-6xl space-y-12 py-10" fullWidth>
        <div className="animate-pulse space-y-6">
          <div className="h-9 w-48 rounded-md bg-surface-muted/60" />
          <div className="h-4 w-80 rounded-md bg-surface-muted/60" />
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-64 rounded-lg bg-surface-muted/60" />
            ))}
          </div>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer className="max-w-6xl space-y-12 py-10 pb-24" fullWidth>
      <PageHeader
        title="Settings"
        description="Configure your preferences, risk tolerance, and system behavior."
        size="md"
      />

      <div className="space-y-8">
        {preferences && (
          <SettingsSection
            title="Profiles"
            description="Save and reuse preference sets for different strategies."
            summary="Import, export, and activate saved profiles"
            defaultCollapsed={false}
          >
            <ProfileSelector
              variant="plain"
              currentPreferences={getCurrentPreferences()}
              onProfileLoad={handleProfileLoad}
            />
          </SettingsSection>
        )}

        <SettingsSection
          title="Trading & Risk"
          description="Control the instruments, position sizing, and risk tolerance available to AI agents."
          summary={tradingSummary}
        >
          <TradingRiskSettings
            riskTolerance={riskTolerance}
            maxPositionSizePct={maxPositionSizePct}
            allowLong={allowLong}
            allowShort={allowShort}
            allowOptions={allowOptions}
            allowCrypto={allowCrypto}
            allowFutures={allowFutures}
            onRiskToleranceChange={setRiskTolerance}
            onMaxPositionSizePctChange={setMaxPositionSizePct}
            onAllowLongChange={setAllowLong}
            onAllowShortChange={setAllowShort}
            onAllowOptionsChange={setAllowOptions}
            onAllowCryptoChange={setAllowCrypto}
            onAllowFuturesChange={setAllowFutures}
          />
        </SettingsSection>

        <SettingsSection
          title="Display & Interface"
          description="Choose your preferred timezone."
          summary={displaySummary}
        >
          <DisplaySettings
            displayTimezone={displayTimezone}
            onDisplayTimezoneChange={setDisplayTimezone}
          />
        </SettingsSection>

        <SettingsSection
          title="Watchlist & Scoring"
          description="Tune refresh cadence, news visibility, and scoring weights for watchlist insights."
          summary={watchlistSummary}
        >
          <WatchlistSettingsSection
            defaultRefreshMinutes={defaultRefreshMinutes}
            watchlistOverride={watchlistOverride}
            newsOverride={newsOverride}
            newsLookbackHours={newsLookbackHours}
            newsMaxArticles={newsMaxArticles}
            showNews={showNews}
            autoExpand={autoExpand}
            scoreWeights={scoreWeights}
            technicalSubWeights={technicalSubWeights}
            fundamentalSubWeights={fundamentalSubWeights}
            onDefaultRefreshMinutesChange={setDefaultRefreshMinutes}
            onWatchlistOverrideChange={setWatchlistOverride}
            onNewsOverrideChange={setNewsOverride}
            onNewsLookbackHoursChange={setNewsLookbackHours}
            onNewsMaxArticlesChange={setNewsMaxArticles}
            onShowNewsChange={setShowNews}
            onAutoExpandChange={setAutoExpand}
            onScoreWeightsChange={setScoreWeights}
            onTechnicalSubWeightsChange={setTechnicalSubWeights}
            onFundamentalSubWeightsChange={setFundamentalSubWeights}
          />
        </SettingsSection>
      </div>

      {/* Unified Save Bar */}
      <SaveBar
        hasChanges={hasChanges}
        onSave={handleSaveAll}
        onReset={handleResetAll}
        isPending={isPending}
        changeCount={changeCount}
      />
    </PageContainer>
  )
}
