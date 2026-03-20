/**
 * useRiskScore hook.
 *
 * Polls the backend for risk scores every N seconds.
 * When no wallet is connected, automatically uses demo mode
 * so the dashboard is always populated with live-feeling data.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { fetchWalletRiskSummary, fetchDemoRiskSummary } from "../api";

const LIVE_POLLING_INTERVAL_MS = 15_000;
const DEMO_POLLING_INTERVAL_MS = 10_000;

/**
 * @param {string | null} connectedWalletAddress  null triggers demo mode
 */
export function useRiskScore(connectedWalletAddress) {
  const [riskSummary, setRiskSummary]            = useState(null);
  const [isLoadingRiskData, setIsLoadingRiskData] = useState(true);
  const [riskDataError, setRiskDataError]         = useState(null);
  const pollingIntervalRef                        = useRef(null);

  const isDemoMode = !connectedWalletAddress;

  const fetchAndUpdateRiskData = useCallback(async () => {
    setIsLoadingRiskData(true);
    setRiskDataError(null);
    try {
      const freshRiskSummary = isDemoMode
        ? await fetchDemoRiskSummary()
        : await fetchWalletRiskSummary(connectedWalletAddress);
      setRiskSummary(freshRiskSummary);
    } catch (fetchError) {
      setRiskDataError(
        fetchError?.response?.data?.detail ||
          "Failed to fetch risk data. Is the backend running?"
      );
    } finally {
      setIsLoadingRiskData(false);
    }
  }, [connectedWalletAddress, isDemoMode]);

  useEffect(() => {
    fetchAndUpdateRiskData();
    const intervalMs = isDemoMode
      ? DEMO_POLLING_INTERVAL_MS
      : LIVE_POLLING_INTERVAL_MS;
    pollingIntervalRef.current = setInterval(fetchAndUpdateRiskData, intervalMs);
    return () => clearInterval(pollingIntervalRef.current);
  }, [fetchAndUpdateRiskData, isDemoMode]);

  return {
    riskSummary,
    isLoadingRiskData,
    riskDataError,
    isDemoMode,
    refreshRiskData: fetchAndUpdateRiskData,
  };
}
