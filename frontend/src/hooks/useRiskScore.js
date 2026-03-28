/**
 * useRiskScore hook.
 *
 * Supports three modes:
 *   DEMO    — no wallet, uses /demo/risk (simulated data)
 *   WATCH   — any wallet address, uses /risk/{address} (read-only, real data)
 *   LIVE    — connected wallet, uses /risk/{address} (real data)
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { fetchWalletRiskSummary, fetchDemoRiskSummary } from "../api";

const LIVE_POLLING_INTERVAL_MS  = 15_000;
const DEMO_POLLING_INTERVAL_MS  = 10_000;
const WATCH_POLLING_INTERVAL_MS = 30_000; // slower for watched wallets

/**
 * @param {string | null} connectedWalletAddress  — own wallet (LIVE mode)
 * @param {string | null} watchedWalletAddress    — any wallet (WATCH mode)
 */
export function useRiskScore(connectedWalletAddress, watchedWalletAddress = null) {
  const [riskSummary, setRiskSummary]             = useState(null);
  const [isLoadingRiskData, setIsLoadingRiskData]  = useState(true);
  const [riskDataError, setRiskDataError]          = useState(null);
  const pollingIntervalRef                         = useRef(null);

  // Determine current mode
  const isDemoMode    = !connectedWalletAddress && !watchedWalletAddress;
  const isWatchMode   = !connectedWalletAddress && !!watchedWalletAddress;
  const isLiveMode    = !!connectedWalletAddress;

  // The active wallet address to query (live takes priority over watch)
  const activeWalletAddress = connectedWalletAddress || watchedWalletAddress;

  const fetchAndUpdateRiskData = useCallback(async () => {
    setIsLoadingRiskData(true);
    setRiskDataError(null);
    try {
      const freshRiskSummary = isDemoMode
        ? await fetchDemoRiskSummary()
        : await fetchWalletRiskSummary(activeWalletAddress);
      setRiskSummary(freshRiskSummary);
    } catch (fetchError) {
      setRiskDataError(
        fetchError?.response?.data?.detail ||
          "Failed to fetch risk data. Is the backend running?"
      );
    } finally {
      setIsLoadingRiskData(false);
    }
  }, [activeWalletAddress, isDemoMode]);

  useEffect(() => {
    // Reset data when switching modes
    setRiskSummary(null);
    fetchAndUpdateRiskData();

    const intervalMs = isDemoMode
      ? DEMO_POLLING_INTERVAL_MS
      : isWatchMode
      ? WATCH_POLLING_INTERVAL_MS
      : LIVE_POLLING_INTERVAL_MS;

    pollingIntervalRef.current = setInterval(fetchAndUpdateRiskData, intervalMs);
    return () => clearInterval(pollingIntervalRef.current);
  }, [fetchAndUpdateRiskData, isDemoMode, isWatchMode]);

  return {
    riskSummary,
    isLoadingRiskData,
    riskDataError,
    isDemoMode,
    isWatchMode,
    isLiveMode,
    refreshRiskData: fetchAndUpdateRiskData,
  };
}
