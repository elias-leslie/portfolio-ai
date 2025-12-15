-- Seed data for market_events table
-- Date: 2025-12-15
-- Description: Initial seed of FOMC, CPI, NFP events for 2024-2026

-- 2024 FOMC Rate Decisions (8 meetings)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('fomc_decision', '2024-01-31', '14:00:00', 'FOMC January 2024 - Rates Held', 'seed'),
('fomc_decision', '2024-03-20', '14:00:00', 'FOMC March 2024 - Rates Held', 'seed'),
('fomc_decision', '2024-05-01', '14:00:00', 'FOMC May 2024 - Rates Held', 'seed'),
('fomc_decision', '2024-06-12', '14:00:00', 'FOMC June 2024 - Rates Held', 'seed'),
('fomc_decision', '2024-07-31', '14:00:00', 'FOMC July 2024 - Rates Held', 'seed'),
('fomc_decision', '2024-09-18', '14:00:00', 'FOMC September 2024 - Rate Cut 50bp', 'seed'),
('fomc_decision', '2024-11-07', '14:00:00', 'FOMC November 2024 - Rate Cut 25bp', 'seed'),
('fomc_decision', '2024-12-18', '14:00:00', 'FOMC December 2024 - Rate Cut 25bp', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2025 FOMC Rate Decisions (8 meetings)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('fomc_decision', '2025-01-29', '14:00:00', 'FOMC January 2025', 'seed'),
('fomc_decision', '2025-03-19', '14:00:00', 'FOMC March 2025', 'seed'),
('fomc_decision', '2025-05-07', '14:00:00', 'FOMC May 2025', 'seed'),
('fomc_decision', '2025-06-18', '14:00:00', 'FOMC June 2025', 'seed'),
('fomc_decision', '2025-07-30', '14:00:00', 'FOMC July 2025', 'seed'),
('fomc_decision', '2025-09-17', '14:00:00', 'FOMC September 2025', 'seed'),
('fomc_decision', '2025-11-05', '14:00:00', 'FOMC November 2025', 'seed'),
('fomc_decision', '2025-12-17', '14:00:00', 'FOMC December 2025', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2024 CPI Releases (12 monthly)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('cpi_release', '2024-01-11', '08:30:00', 'CPI December 2023', 'seed'),
('cpi_release', '2024-02-13', '08:30:00', 'CPI January 2024', 'seed'),
('cpi_release', '2024-03-12', '08:30:00', 'CPI February 2024', 'seed'),
('cpi_release', '2024-04-10', '08:30:00', 'CPI March 2024', 'seed'),
('cpi_release', '2024-05-15', '08:30:00', 'CPI April 2024', 'seed'),
('cpi_release', '2024-06-12', '08:30:00', 'CPI May 2024', 'seed'),
('cpi_release', '2024-07-11', '08:30:00', 'CPI June 2024', 'seed'),
('cpi_release', '2024-08-14', '08:30:00', 'CPI July 2024', 'seed'),
('cpi_release', '2024-09-11', '08:30:00', 'CPI August 2024', 'seed'),
('cpi_release', '2024-10-10', '08:30:00', 'CPI September 2024', 'seed'),
('cpi_release', '2024-11-13', '08:30:00', 'CPI October 2024', 'seed'),
('cpi_release', '2024-12-11', '08:30:00', 'CPI November 2024', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2025 CPI Releases (12 monthly)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('cpi_release', '2025-01-15', '08:30:00', 'CPI December 2024', 'seed'),
('cpi_release', '2025-02-12', '08:30:00', 'CPI January 2025', 'seed'),
('cpi_release', '2025-03-12', '08:30:00', 'CPI February 2025', 'seed'),
('cpi_release', '2025-04-10', '08:30:00', 'CPI March 2025', 'seed'),
('cpi_release', '2025-05-13', '08:30:00', 'CPI April 2025', 'seed'),
('cpi_release', '2025-06-11', '08:30:00', 'CPI May 2025', 'seed'),
('cpi_release', '2025-07-10', '08:30:00', 'CPI June 2025', 'seed'),
('cpi_release', '2025-08-12', '08:30:00', 'CPI July 2025', 'seed'),
('cpi_release', '2025-09-10', '08:30:00', 'CPI August 2025', 'seed'),
('cpi_release', '2025-10-09', '08:30:00', 'CPI September 2025', 'seed'),
('cpi_release', '2025-11-13', '08:30:00', 'CPI October 2025', 'seed'),
('cpi_release', '2025-12-10', '08:30:00', 'CPI November 2025', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2024 Non-Farm Payrolls (12 monthly, first Friday)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('nfp_release', '2024-01-05', '08:30:00', 'NFP December 2023', 'seed'),
('nfp_release', '2024-02-02', '08:30:00', 'NFP January 2024', 'seed'),
('nfp_release', '2024-03-08', '08:30:00', 'NFP February 2024', 'seed'),
('nfp_release', '2024-04-05', '08:30:00', 'NFP March 2024', 'seed'),
('nfp_release', '2024-05-03', '08:30:00', 'NFP April 2024', 'seed'),
('nfp_release', '2024-06-07', '08:30:00', 'NFP May 2024', 'seed'),
('nfp_release', '2024-07-05', '08:30:00', 'NFP June 2024', 'seed'),
('nfp_release', '2024-08-02', '08:30:00', 'NFP July 2024', 'seed'),
('nfp_release', '2024-09-06', '08:30:00', 'NFP August 2024', 'seed'),
('nfp_release', '2024-10-04', '08:30:00', 'NFP September 2024', 'seed'),
('nfp_release', '2024-11-01', '08:30:00', 'NFP October 2024', 'seed'),
('nfp_release', '2024-12-06', '08:30:00', 'NFP November 2024', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2025 Non-Farm Payrolls (12 monthly, first Friday)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('nfp_release', '2025-01-10', '08:30:00', 'NFP December 2024', 'seed'),
('nfp_release', '2025-02-07', '08:30:00', 'NFP January 2025', 'seed'),
('nfp_release', '2025-03-07', '08:30:00', 'NFP February 2025', 'seed'),
('nfp_release', '2025-04-04', '08:30:00', 'NFP March 2025', 'seed'),
('nfp_release', '2025-05-02', '08:30:00', 'NFP April 2025', 'seed'),
('nfp_release', '2025-06-06', '08:30:00', 'NFP May 2025', 'seed'),
('nfp_release', '2025-07-03', '08:30:00', 'NFP June 2025', 'seed'),
('nfp_release', '2025-08-01', '08:30:00', 'NFP July 2025', 'seed'),
('nfp_release', '2025-09-05', '08:30:00', 'NFP August 2025', 'seed'),
('nfp_release', '2025-10-03', '08:30:00', 'NFP September 2025', 'seed'),
('nfp_release', '2025-11-07', '08:30:00', 'NFP October 2025', 'seed'),
('nfp_release', '2025-12-05', '08:30:00', 'NFP November 2025', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2024 GDP Releases (4 quarterly)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('gdp_release', '2024-01-25', '08:30:00', 'GDP Q4 2023 Advance', 'seed'),
('gdp_release', '2024-04-25', '08:30:00', 'GDP Q1 2024 Advance', 'seed'),
('gdp_release', '2024-07-25', '08:30:00', 'GDP Q2 2024 Advance', 'seed'),
('gdp_release', '2024-10-30', '08:30:00', 'GDP Q3 2024 Advance', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- 2025 GDP Releases (4 quarterly)
INSERT INTO market_events (event_type, event_date, event_time, title, source) VALUES
('gdp_release', '2025-01-30', '08:30:00', 'GDP Q4 2024 Advance', 'seed'),
('gdp_release', '2025-04-30', '08:30:00', 'GDP Q1 2025 Advance', 'seed'),
('gdp_release', '2025-07-30', '08:30:00', 'GDP Q2 2025 Advance', 'seed'),
('gdp_release', '2025-10-30', '08:30:00', 'GDP Q3 2025 Advance', 'seed')
ON CONFLICT (event_type, event_date) DO NOTHING;

-- Verify seed data
SELECT event_type::text, COUNT(*) as count FROM market_events GROUP BY event_type ORDER BY event_type;
