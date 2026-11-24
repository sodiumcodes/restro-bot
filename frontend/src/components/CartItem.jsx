"use client";

import { useState } from "react";

// Line item row with quantity stepper and inline special request input
export default function CartItem({ item, onUpdate, onRemove, disabled }) {
  const [note, setNote] = useState(item.special_request || "");

  // Commit special request text changes to the backend
  const handleSaveNote = () => {
    if (note !== (item.special_request || "")) {
      onUpdate(item.item_id, item.quantity, note);
    }
  };

  return (
    <div className="py-3 border-b border-gray-100 last:border-0">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h5 className="text-sm font-medium text-gray-900 truncate">{item.name}</h5>
          <span className="text-xs text-gray-500">₹{Number(item.unit_price).toFixed(2)} each</span>
        </div>
        <span className="text-sm font-semibold text-gray-900 whitespace-nowrap">₹{Number(item.line_total).toFixed(2)}</span>
      </div>

      {/* Special cooking request field */}
      <div className="mt-1.5 flex items-center gap-1.5">
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={handleSaveNote}
          onKeyDown={(e) => e.key === "Enter" && handleSaveNote()}
          placeholder="Special request (e.g. less spicy)..."
          disabled={disabled}
          className="flex-1 text-xs px-2 py-1 bg-gray-50 border border-gray-200 rounded focus:bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      {/* Stepper and remove control */}
      <div className="mt-2 flex items-center justify-between text-xs">
        <button
          type="button"
          onClick={() => onRemove(item.item_id)}
          disabled={disabled}
          className="text-red-600 hover:text-red-700 disabled:opacity-50"
        >
          Remove
        </button>
        <div className="flex items-center space-x-2 border border-gray-200 rounded bg-white">
          <button
            type="button"
            onClick={() => onUpdate(item.item_id, item.quantity - 1, item.special_request)}
            disabled={disabled || item.quantity <= 1}
            className="px-2 py-0.5 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
          >
            -
          </button>
          <span className="px-1 text-xs font-semibold text-gray-800">{item.quantity}</span>
          <button
            type="button"
            onClick={() => onUpdate(item.item_id, item.quantity + 1, item.special_request)}
            disabled={disabled}
            className="px-2 py-0.5 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
          >
            +
          </button>
        </div>
      </div>
    </div>
  );
}
