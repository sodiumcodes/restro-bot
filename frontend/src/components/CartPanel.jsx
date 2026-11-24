"use client";

import CartItem from "./CartItem";

// Responsive cart display rendering as bottom sheet on mobile and sidebar on desktop
export default function CartPanel({
  cart,
  staleNotice,
  isOpen,
  onClose,
  onUpdateItem,
  onRemoveItem,
  onCheckout,
  disabled,
}) {
  const lines = cart.lines || [];
  const hasItems = lines.length > 0;

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/40 sm:hidden transition-opacity"
        />
      )}

      <aside
        className={`fixed inset-x-0 bottom-0 z-40 max-h-[85vh] sm:static sm:z-auto sm:max-h-none sm:h-full bg-white border-t sm:border-t-0 sm:border-l border-gray-200 shadow-xl sm:shadow-none flex flex-col transition-transform duration-300 ${
          isOpen ? "translate-y-0" : "translate-y-full sm:translate-y-0"
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h3 className="text-base font-semibold text-gray-900">Your Cart</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 sm:hidden text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {/* Stale cart warning banner */}
        {staleNotice && (
          <div className="p-2.5 mx-4 mt-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
            {staleNotice}
          </div>
        )}

        {/* Items list */}
        <div className="flex-1 overflow-y-auto px-4 py-2">
          {!hasItems ? (
            <div className="py-8 text-center text-xs text-gray-400">Your cart is currently empty.</div>
          ) : (
            lines.map((item) => (
              <CartItem
                key={item.item_id}
                item={item}
                onUpdate={onUpdateItem}
                onRemove={onRemoveItem}
                disabled={disabled}
              />
            ))
          )}
        </div>

        {/* Footer with backend total and checkout trigger */}
        <div className="p-4 border-t border-gray-100 bg-gray-50">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs text-gray-500">Order Total</span>
            <span className="text-base font-bold text-gray-900">₹{Number(cart.total || 0).toFixed(2)}</span>
          </div>
          <button
            type="button"
            onClick={onCheckout}
            disabled={disabled || !hasItems}
            className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
          >
            Review & Order
          </button>
        </div>
      </aside>
    </>
  );
}
