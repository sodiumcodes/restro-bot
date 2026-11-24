// Base API URL pointing to the FastAPI backend v1 routes
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

// Helper handling JSON fetch requests and parsing server error responses
async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const error = new Error(typeof data?.detail === "string" ? data.detail : res.statusText);
    error.status = res.status;
    error.detail = data?.detail;
    throw error;
  }
  return data;
}

// Session endpoints
export const createSession = () => request("/sessions", { method: "POST" });
export const getSessionStatus = (sessionId) => request(`/sessions/${sessionId}`);
export const getSessionMessages = (sessionId) => request(`/sessions/${sessionId}/messages`);

// Chat endpoint returning assistant message, suggestions, and cart snapshot
export const sendChatMessage = (sessionId, message) =>
  request("/chat", { method: "POST", body: JSON.stringify({ session_id: sessionId, message }) });

// Cart endpoints for optimistic concurrency
export const getCart = (sessionId) => request(`/cart/${sessionId}`);

export const addToCart = (sessionId, { itemId, quantity = 1, specialRequest = null, expectedVersion }) =>
  request(`/cart/${sessionId}/items`, {
    method: "POST",
    body: JSON.stringify({
      item_id: itemId,
      quantity,
      special_request: specialRequest,
      expected_version: expectedVersion,
    }),
  });

export const updateCartItem = (sessionId, { itemId, quantity, specialRequest, expectedVersion }) =>
  request(`/cart/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({
      item_id: itemId,
      quantity,
      special_request: specialRequest,
      expected_version: expectedVersion,
    }),
  });

export const removeCartItem = (sessionId, itemId, expectedVersion) =>
  request(`/cart/${sessionId}/items/${itemId}?expected_version=${expectedVersion}`, {
    method: "DELETE",
  });

// Order placement endpoint using client-generated idempotency key
export const placeOrder = (payload, idempotencyKey) =>
  request("/orders", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
