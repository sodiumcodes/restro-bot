"use client";

import { useState, useCallback } from "react";
import { getCart, addToCart, updateCartItem, removeCartItem } from "../lib/api";

// Manages cart state with backend price calculations and optimistic concurrency checks
export function useCart(sessionId) {
  const [cart, setCart] = useState({ lines: [], total: "0.00", version: 1 });
  const [loading, setLoading] = useState(false);
  const [staleNotice, setStaleNotice] = useState(null);

  // Load current cart from backend
  const refreshCart = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data = await getCart(sessionId);
      setCart(data);
    } catch (err) {
      console.error("Cart fetch error:", err);
    }
  }, [sessionId]);

  // Synchronize cart directly with server snapshot (e.g. from chat response)
  const syncCart = useCallback((serverCart) => {
    if (serverCart && typeof serverCart.version === "number") {
      setCart(serverCart);
    }
  }, []);

  // Handle optimistic concurrency conflict (409) by replacing local state with server state
  const handleMutation = async (actionFn) => {
    setLoading(true);
    setStaleNotice(null);
    try {
      const updated = await actionFn();
      setCart(updated);
    } catch (err) {
      if (err.status === 409 && err.detail && typeof err.detail === "object") {
        setCart(err.detail);
        setStaleNotice("Cart was updated in another tab. We refreshed your cart.");
      } else {
        throw err;
      }
    } finally {
      setLoading(false);
    }
  };

  const addItem = (itemId, quantity = 1, specialRequest = null) =>
    handleMutation(() =>
      addToCart(sessionId, { itemId, quantity, specialRequest, expectedVersion: cart.version })
    );

  const updateItem = (itemId, quantity, specialRequest) =>
    handleMutation(() =>
      updateCartItem(sessionId, { itemId, quantity, specialRequest, expectedVersion: cart.version })
    );

  const removeItem = (itemId) =>
    handleMutation(() => removeCartItem(sessionId, itemId, cart.version));

  return { cart, loading, staleNotice, refreshCart, syncCart, addItem, updateItem, removeItem };
}
