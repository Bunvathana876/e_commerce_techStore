// Invoked by backend pytest, which supplies an ephemeral database and test-only tokens.
import assert from "node:assert/strict";
import { test } from "node:test";

const base = new URL(process.env.NEXT_PUBLIC_API_URL);
assert.equal(base.hostname, "127.0.0.1", "Only an isolated loopback API is allowed");
assert.ok(process.env.BLUE_PANDA_TEST_TOKEN, "Run through backend pytest");

const values = new Map();
const storage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, String(value)),
  removeItem: (key) => values.delete(key),
};
Object.defineProperty(globalThis, "localStorage", { configurable: true, value: storage });
const events = new EventTarget();
globalThis.window = {
  localStorage: storage,
  location: { pathname: "/" },
  addEventListener: events.addEventListener.bind(events),
  removeEventListener: events.removeEventListener.bind(events),
  dispatchEvent: events.dispatchEvent.bind(events),
  setTimeout: (callback, delay) => setTimeout(callback, delay).unref(),
};

const { productsApi, cartApi, authApi } = await import("../src/lib/api.ts");
const { saveAuthSession, logout } = await import("../src/lib/auth.ts");
const { useShopStore, getCartTotals } = await import("../src/lib/store.ts");
const state = () => useShopStore.getState();
const totals = () => getCartTotals(state().items, state().appliedCoupon);

test("guest and authenticated cart lifecycle uses the real isolated API", async () => {
  const product = (await productsApi.get(1)).data;
  assert.equal(product.price, 20);

  // Guest operations drive the same store and totals used by the lazy drawer.
  state().openQuickView(product);
  assert.equal(state().quickViewProduct.id, product.id);
  await state().addToCart(product, 2);
  state().closeQuickView();
  assert.equal(state().quickViewProduct, null);
  assert.equal(state().isCartOpen, true);
  assert.equal(totals().subtotal, 40);
  assert.equal(totals().shipping, 2);
  assert.equal(totals().total, 42);
  state().closeCart();
  assert.equal(state().isCartOpen, false);
  state().openCart();
  assert.equal(state().items[0].quantity, 2);
  await state().updateQuantity("1:default", 5);
  assert.equal(totals().subtotal, 100);
  assert.equal(totals().shipping, 0);
  await state().removeFromCart("1:default");
  assert.equal(totals().total, 0);
  assert.equal(totals().totalItems, 0);

  saveAuthSession(process.env.BLUE_PANDA_TEST_TOKEN, {
    id: 2, name: "Fixture 2", email: "user2@example.com", role: "customer", is_active: true,
  });
  assert.equal((await authApi.getMe()).data.id, 2);
  await state().addToCart(product, 2);
  let serverCart = (await cartApi.get()).data;
  assert.equal(serverCart.subtotal, 40);
  assert.equal(serverCart.items[0].quantity, 2);
  assert.equal(state().items[0].backendItemId, serverCart.items[0].id);

  await state().updateQuantity("1:default", 5);
  serverCart = (await cartApi.get()).data;
  assert.equal(serverCart.items[0].quantity, 5);
  assert.equal(serverCart.subtotal, totals().subtotal);

  // An unrelated customer must not be able to modify this cart row.
  const denied = await fetch(`${base.href}/cart/items/${serverCart.items[0].id}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${process.env.BLUE_PANDA_OTHER_TEST_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ quantity: 1 }),
  });
  assert.equal(denied.status, 404);
  assert.equal((await cartApi.get()).data.items[0].quantity, 5);

  await state().removeFromCart("1:default");
  assert.equal((await cartApi.get()).data.items.length, 0);
  assert.equal(totals().total, 0);
  logout();
  assert.equal(state().isCartOpen, false);
  assert.equal(state().items.length, 0);
});
