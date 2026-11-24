"use client";

import { useState, useRef } from "react";
import { placeOrder } from "../lib/api";

// Modal handling order placement, table/contact validation, and idempotency
export default function OrderModal({ sessionId, cart, isOpen, onClose, onSuccess, onStaleCart }) {
  const [orderType, setOrderType] = useState("dine_in");
  const [tableNumber, setTableNumber] = useState("");
  const [contact, setContact] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Maintain one idempotency key per checkout attempt, reusing it across retry clicks
  const idempotencyKeyRef = useRef(null);
  if (!idempotencyKeyRef.current) {
    idempotencyKeyRef.current = "order_" + Math.random().toString(36).substring(2) + Date.now();
  }

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    // Enforce backend validation rules locally before submitting
    if (orderType === "dine_in" && !tableNumber.trim()) {
      setErrorMsg("Table number is required for dine-in.");
      return;
    }
    if (orderType === "takeaway" && !contact.trim()) {
      setErrorMsg("Name or phone number is required for takeaway.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        session_id: sessionId,
        order_type: orderType,
        cart_version: cart.version,
        table_number: orderType === "dine_in" ? tableNumber.trim() : null,
        contact: orderType === "takeaway" ? contact.trim() : null,
      };

      const orderResult = await placeOrder(payload, idempotencyKeyRef.current);
      onSuccess(orderResult);
    } catch (err) {
      if (err.status === 409) {
        if (typeof err.detail === "object" && err.detail?.version) {
          onStaleCart(err.detail);
          setErrorMsg("Cart was modified. Please review updated items and retry.");
        } else {
          setErrorMsg(err.message || "An item is no longer available. Please update your cart.");
        }
      } else if (err.status === 429) {
        setErrorMsg("Too many requests. Please wait a moment before retrying.");
      } else if (err.status === 503) {
        setErrorMsg("Checkout is temporarily unavailable. Please tap Confirm to retry.");
      } else {
        setErrorMsg(err.message || "Failed to place order.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
      <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5">
        <h3 className="text-base font-bold text-gray-900 mb-1">Confirm Order</h3>
        <p className="text-xs text-gray-500 mb-4">{cart.lines?.length || 0} item(s) • Total: ₹{Number(cart.total || 0).toFixed(2)}</p>

        {errorMsg && <div className="mb-3 p-2 text-xs bg-red-50 text-red-700 border border-red-200 rounded">{errorMsg}</div>}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex rounded-md border border-gray-200 overflow-hidden text-xs font-medium">
            <button
              type="button"
              onClick={() => setOrderType("dine_in")}
              className={`flex-1 py-1.5 text-center ${orderType === "dine_in" ? "bg-indigo-600 text-white" : "bg-gray-50 text-gray-700"}`}
            >
              Dine-In
            </button>
            <button
              type="button"
              onClick={() => setOrderType("takeaway")}
              className={`flex-1 py-1.5 text-center ${orderType === "takeaway" ? "bg-indigo-600 text-white" : "bg-gray-50 text-gray-700"}`}
            >
              Takeaway
            </button>
          </div>

          {orderType === "dine_in" ? (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Table Number *</label>
              <input
                type="text"
                value={tableNumber}
                onChange={(e) => setTableNumber(e.target.value)}
                placeholder="e.g. 7"
                disabled={submitting}
                className="w-full text-xs px-2.5 py-1.5 border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Name or Phone *</label>
              <input
                type="text"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                placeholder="e.g. Priya or 9876543210"
                disabled={submitting}
                className="w-full text-xs px-2.5 py-1.5 border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          )}

          <div className="pt-2 flex gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="flex-1 py-2 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded"
            >
              Back
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded"
            >
              {submitting ? "Placing..." : "Confirm Order"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
