"use client";

import { useState, useEffect, useCallback } from "react";
import { createSession, getSessionStatus } from "../lib/api";

const STORAGE_KEY = "cafe_session_id";

// Custom hook managing anonymous customer session lifecycle and local persistence
export function useSession() {
  const [sessionId, setSessionId] = useState(null);
  const [isClosed, setIsClosed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize or restore session on first mount
  const initSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    let storedId = null;

    // Wrap localStorage access in try/catch to handle private browsing restrictions
    try {
      storedId = window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      console.warn("Storage access failed, using memory state", e);
    }

    if (storedId) {
      try {
        const status = await getSessionStatus(storedId);
        setSessionId(storedId);
        setIsClosed(status.status === "closed");
        setLoading(false);
        return;
      } catch (err) {
        // If session was purged on backend (404), fall through to generate a new one
        if (err.status !== 404) {
          setError(err.message || "Failed to verify session");
          setLoading(false);
          return;
        }
      }
    }

    // Create a new session when none is stored or previous session returned 404
    try {
      const res = await createSession();
      setSessionId(res.session_id);
      setIsClosed(false);
      try {
        window.localStorage.setItem(STORAGE_KEY, res.session_id);
      } catch (e) {
        console.warn("Failed to persist session_id", e);
      }
    } catch (err) {
      setError(err.message || "Could not establish ordering session");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  return { sessionId, isClosed, setIsClosed, loading, error, refreshSession: initSession };
}
