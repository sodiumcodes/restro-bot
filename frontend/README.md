# Cafe Ordering Chatbot - Frontend

Customer-facing ordering frontend built with Next.js (App Router, JavaScript) and Tailwind CSS.

## Getting Started

### 1. Environment Setup
Copy `.env.example` to `.env.local` and set your FastAPI backend address:

```bash
cp .env.example .env.local
```

Default configuration:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Run Development Server
```bash
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Manual Test Checklist

Use this checklist to verify customer ordering flows across desktop and mobile (tested at 360px viewport width):

1. **Browse via Chat**
   - Type `"What vegetarian dishes do you have?"` or `"show me spicy food"`.
   - Verify typing indicator displays during in-flight LLM calls and input is disabled.
   - Verify bot reply appears with formatted text and structured suggestion cards.

2. **Add via Suggestion Card**
   - Click **"+ Add to cart"** on any suggestion card.
   - Verify the item is added to the cart immediately without an extra LLM round trip.
   - Verify the cart quantity badge and total update with values returned by the backend.

3. **Add via Chat**
   - Ask the bot: `"Can you recommend a drink?"`.
   - Verify suggestion cards for beverages appear and can be added directly to the cart.

4. **Edit Quantity (+ / -)**
   - In the cart panel, tap **"+"** on an item to increment quantity.
   - Tap **"-"** to decrement quantity.
   - Verify line totals and order totals update strictly from backend calculations (no client-side math).

5. **Special Cooking Request**
   - Type a note (e.g., `"extra spicy, no onions"`) in an item's special request field.
   - Press Enter or click outside the input (blur).
   - Verify the request note persists and is displayed on that item line.

6. **Stale Cart Concurrency (Two Tabs)**
   - Open [http://localhost:3000](http://localhost:3000) in two browser tabs sharing the same session ID.
   - In Tab A, add an item or change quantity.
   - In Tab B, attempt to change quantity without reloading.
   - Verify backend returns HTTP 409 and Tab B displays: *"Cart was updated in another tab. We refreshed your cart."* with reconciled state.

7. **Takeaway and Dine-in Validation**
   - Click **"Review & Order"**.
   - Select **Dine-In** and leave Table Number blank; click Confirm. Verify inline error: *"Table number is required for dine-in."*
   - Select **Takeaway** and leave Contact blank; click Confirm. Verify inline error: *"Name or phone number is required for takeaway."*

8. **Double-Tap Confirm Prevention**
   - Fill in a valid table number (e.g. `4`) and click **"Confirm Order"**.
   - Verify the Confirm button is disabled during submission (`"Placing..."`) and the request includes an `Idempotency-Key` header so duplicate clicks cannot create duplicate orders.

9. **Refresh Mid-Order**
   - Add items to the cart, send a few messages, then refresh the page (F5).
   - Verify session ID is retained from `localStorage`, conversation history is fetched from `/api/v1/sessions/{session_id}/messages`, and the cart is reloaded intact.

10. **Refresh After Order (Session Completed)**
    - After placing an order, refresh the page.
    - Verify the screen restores the **Order Confirmed** view with the bill payment QR note and keeps the chat and cart locked.
