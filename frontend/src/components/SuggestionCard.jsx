"use client";

import { useState } from "react";

// Card rendering structured dish suggestion with direct cart mutation action
export default function SuggestionCard({ item, onAdd, disabled }) {
  const [adding, setAdding] = useState(false);

  // Directly mutates cart without routing back through the LLM
  const handleAdd = async () => {
    setAdding(true);
    try {
      await onAdd(item.item_id);
    } catch (e) {
      console.error("Failed to add suggestion to cart:", e);
    } finally {
      setAdding(false);
    }
  };

  const isVeg = item.veg_type === "veg" || item.veg_type === "vegan";

  return (
    <div className="flex flex-col justify-between p-3 bg-white border border-gray-200 rounded-lg shadow-sm hover:border-gray-300 transition-colors">
      <div>
        <div className="flex items-start justify-between gap-2">
          <h4 className="text-sm font-semibold text-gray-900 leading-snug">{item.name}</h4>
          <span className="text-sm font-bold text-gray-800 whitespace-nowrap">₹{Number(item.price).toFixed(2)}</span>
        </div>
        {item.veg_type && (
          <span
            className={`inline-block mt-1 px-1.5 py-0.5 text-[10px] font-medium rounded ${
              isVeg ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"
            }`}
          >
            {item.veg_type.toUpperCase()}
          </span>
        )}
        {item.description && <p className="mt-1 text-xs text-gray-600 line-clamp-2">{item.description}</p>}
      </div>

      <button
        type="button"
        onClick={handleAdd}
        disabled={disabled || adding}
        className="mt-2.5 w-full py-1 px-3 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-50 border border-emerald-200 rounded transition-colors"
      >
        {adding ? "Adding..." : "+ Add to cart"}
      </button>
    </div>
  );
}
