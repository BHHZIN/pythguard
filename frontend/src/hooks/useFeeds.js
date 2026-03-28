/**
 * useFeeds hook.
 *
 * ALWAYS fetches real Pyth prices from the backend — even in demo mode.
 * Falls back to simulated prices only if the backend is unreachable.
 *
 * This means the feed bar always shows real SOL/BTC/ETH prices
 * regardless of whether a wallet is connected.
 */
import { useState, useEffect, useRef } from "react";
import { fetchAllFeedStatuses, fetchDemoFeedStatuses } from "../api";

const FEED_POLLING_INTERVAL_MS = 10_000;

/**
 * @param {boolean} isDemoMode  — passed in but we still try real prices first
 */
export function useFeeds(isDemoMode = false) {
  const [feedStatuses, setFeedStatuses]       = useState([]);
  const [isLoadingFeeds, setIsLoadingFeeds]   = useState(true);
  const [isUsingRealPrices, setIsUsingRealPrices] = useState(false);
  const pollingIntervalRef                    = useRef(null);

  async function fetchAndUpdateFeeds() {
    // Always try real Pyth prices first
    try {
      const realStatuses = await fetchAllFeedStatuses();
      if (realStatuses && realStatuses.length > 0) {
        setFeedStatuses(realStatuses);
        setIsUsingRealPrices(true);
        setIsLoadingFeeds(false);
        return;
      }
    } catch {
      // Real prices unavailable — fall through to demo
    }

    // Fallback: demo prices (simulated)
    try {
      const demoStatuses = await fetchDemoFeedStatuses();
      setFeedStatuses(demoStatuses);
      setIsUsingRealPrices(false);
    } catch {
      // Both failed — keep existing data
    } finally {
      setIsLoadingFeeds(false);
    }
  }

  useEffect(() => {
    fetchAndUpdateFeeds();
    pollingIntervalRef.current = setInterval(
      fetchAndUpdateFeeds,
      FEED_POLLING_INTERVAL_MS
    );
    return () => clearInterval(pollingIntervalRef.current);
  }, []);

  return { feedStatuses, isLoadingFeeds, isUsingRealPrices };
}
