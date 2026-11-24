"use client";

// Confirmation screen presented upon order placement, locking the session
export default function OrderConfirmation({ order, onReset }) {
  const items = order.items || [];

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 bg-white max-w-md mx-auto text-center">
      {/* Success badge */}
      <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center text-xl mb-3">
        ✓
      </div>
      <h2 className="text-xl font-bold text-gray-900">Order Confirmed!</h2>
      <p className="text-xs text-gray-500 mt-0.5">Order #{order.order_id} • {order.order_type === "dine_in" ? `Table ${order.table_number}` : `Takeaway (${order.contact})`}</p>

      {/* Bill & payment QR notice */}
      <div className="my-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 text-left">
        <strong>Payment Note:</strong> Our staff will share the final bill and payment QR with you at your table or counter.
      </div>

      {/* Receipt itemization */}
      <div className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-left mb-4">
        <h4 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">Order Summary</h4>
        <div className="space-y-1.5 divide-y divide-gray-200 text-xs">
          {items.map((i, idx) => (
            <div key={idx} className="pt-1.5 flex justify-between">
              <div>
                <span className="font-medium text-gray-800">{i.quantity}x {i.item_name}</span>
                {i.special_request && <p className="text-[10px] text-gray-500 italic">"{i.special_request}"</p>}
              </div>
              <span className="font-semibold text-gray-700">₹{Number(i.line_total).toFixed(2)}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 pt-2 border-t border-gray-300 flex justify-between text-sm font-bold text-gray-900">
          <span>Total</span>
          <span>₹{Number(order.total).toFixed(2)}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={onReset}
        className="w-full py-2.5 px-4 bg-gray-900 hover:bg-black text-white text-xs font-semibold rounded-lg transition-colors"
      >
        Start New Order
      </button>
    </div>
  );
}
