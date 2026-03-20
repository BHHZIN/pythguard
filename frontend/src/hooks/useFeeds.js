/**
 * useFeeds hook.
 *
 * Polls the backend for live Pyth price feed statuses.
 * Supports demo mode — falls back to /demo/feeds when isDemoMode is true.
 */
import { useState, useEffect, useRef } from "react";
import { fetchAllFeedStatuses, fetchDemoFeedStatuses } from "../api";

const FEED_POLLING_INTERVAL_MS = 10_000;

/**
 * @param {boolean} isDemoMode
 */
export function useFeeds(isDemoMode = false) {
  const [feedStatuses, setFeedStatuses]     = useState([]);
  const [isLoadingFeeds, setIsLoadingFeeds] = useState(true);
  const pollingIntervalRef                  = useRef(null);

  async function fetchAndUpdateFeeds() {
    try {
      const latestStatuses = isDemoMode
        ? await fetchDemoFeedStatuses()
        : await fetchAllFeedStatuses();
      setFeedStatuses(latestStatuses);
    } catch {
      // Silently keep stale data — UI stays functional
    } finally {
      setIsLoadingFeeds(false);
    }
  }

  useEffect(() => {
    fetchAndUpdateFeeds();
    pollingIntervalRef.current = setInterval(fetchAndUpdateFeeds, FEED_POLLING_INTERVAL_MS);
    return () => clearInterval(pollingIntervalRef.current);
  }, [isDemoMode]);

  return { feedStatuses, isLoadingFeeds };
}
