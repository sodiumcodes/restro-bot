"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "../hooks/useSession";
import { useCart } from "../hooks/useCart";
import { getSessionMessages, sendChatMessage } from "../lib/api";
import ChatMessage, { TypingIndicator } from "../components/ChatMessage";
import CartPanel from "../components/CartPanel";
import OrderModal from "../components/OrderModal";
import OrderConfirmation from "../components/OrderConfirmation";

// Primary ordering page managing chat history, cart synchronization, and checkout flow
export default function OrderingPage() {
  const { sessionId, isClosed, setIsClosed, loading: sessionLoading, error: sessionError, refreshSession } = useSession();
  const { cart, staleNotice, refreshCart, syncCart, addItem, updateItem, removeItem } = useCart(sessionId);

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [completedOrder, setCompletedOrder] = useState(null);

  const messagesEndRef = useRef(null);

  // Auto-scroll chat view to bottom when new messages or typing indicators appear
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Load existing conversation history and cart on session initialization/refresh
  useEffect(() => {
    if (!sessionId) return;
    refreshCart();
    getSessionMessages(sessionId)
      .then((data) => {
        if (data?.messages) {
          setMessages(data.messages);
        }
      })
      .catch((err) => console.error("Could not load message history", err));
  }, [sessionId, refreshCart]);

  // Send user message, stream response, and update suggestions and cart
  const handleSendMessage = async (e) => {
    e?.preventDefault();
    const text = inputValue.trim();
    if (!text || sending || isClosed) return;

    setInputValue("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);

    try {
      const res = await sendChatMessage(sessionId, text);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.response, suggestions: res.suggestions || [] },
      ]);
      if (res.cart) syncCart(res.cart);
    } catch (err) {
      if (err.status === 409) setIsClosed(true);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: err.message || "Unable to process message right now." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const cartCount = cart.lines?.reduce((sum, item) => sum + item.quantity, 0) || 0;

  if (sessionLoading) return <div className="p-8 text-center text-sm text-gray-500">Starting ordering session...</div>;
  if (sessionError) return <div className="p-8 text-center text-sm text-red-600">{sessionError}</div>;

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto bg-white border-x border-gray-200">
      {/* Header with title and mobile cart toggle */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div>
          <h1 className="text-base font-bold text-gray-900 leading-tight">Cafe Assistant</h1>
          <p className="text-[11px] text-gray-500">{isClosed ? "Ordering completed" : "Ask for recommendations or dishes"}</p>
        </div>
        {!isClosed && !completedOrder && (
          <button
            type="button"
            onClick={() => setCartOpen((prev) => !prev)}
            className="relative px-3 py-1.5 text-xs font-semibold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg sm:hidden"
          >
            Cart {cartCount > 0 && <span className="ml-1 px-1.5 py-0.2 bg-indigo-600 text-white rounded-full text-[10px]">{cartCount}</span>}
          </button>
        )}
      </header>

      {/* Main chat & cart layout */}
      <div className="flex flex-1 overflow-hidden">
        {completedOrder || isClosed ? (
          <OrderConfirmation
            order={completedOrder || { order_id: "Completed", order_type: "dine_in", items: cart.lines, total: cart.total }}
            onReset={() => {
              setCompletedOrder(null);
              refreshSession();
            }}
          />
        ) : (
          <>
            <main className="flex-1 flex flex-col min-w-0">
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 && (
                  <div className="text-center py-10 text-xs text-gray-400">
                    Welcome! Ask what you would like to eat or drink today.
                  </div>
                )}
                {messages.map((m, idx) => (
                  <ChatMessage
                    key={idx}
                    message={m}
                    onAddSuggestion={(itemId) => addItem(itemId, 1)}
                    disabled={sending || isClosed}
                  />
                ))}
                {sending && <TypingIndicator />}
                <div ref={messagesEndRef} />
              </div>

              <form onSubmit={handleSendMessage} className="p-3 border-t border-gray-200 bg-gray-50 flex gap-2">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder={isClosed ? "Session completed." : "Message cafe bot..."}
                  disabled={sending || isClosed}
                  maxLength={500}
                  className="flex-1 text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
                <button
                  type="submit"
                  disabled={sending || isClosed || !inputValue.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
                >
                  Send
                </button>
              </form>
            </main>

            <CartPanel
              cart={cart}
              staleNotice={staleNotice}
              isOpen={cartOpen}
              onClose={() => setCartOpen(false)}
              onUpdateItem={updateItem}
              onRemoveItem={removeItem}
              onCheckout={() => setCheckoutOpen(true)}
              disabled={sending || isClosed}
            />
          </>
        )}
      </div>

      <OrderModal
        sessionId={sessionId}
        cart={cart}
        isOpen={checkoutOpen}
        onClose={() => setCheckoutOpen(false)}
        onSuccess={(order) => {
          setCheckoutOpen(false);
          setCompletedOrder(order);
          setIsClosed(true);
        }}
        onStaleCart={(freshCart) => syncCart(freshCart)}
      />
    </div>
  );
}
