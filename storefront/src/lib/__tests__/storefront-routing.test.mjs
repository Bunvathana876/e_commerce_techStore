import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  AUTH_KEY,
  TOKEN_KEY,
  USER_KEY,
  getSafeRoleDestination,
  logout,
  saveAuthSession,
  isLoggedIn,
  getCurrentUser,
  clearPrivateSessionData,
  isAllowlistedOrigin,
} from "../auth.ts";

class MockStorage {
  privateStore = new Map();
  getItem(key) {
    return this.privateStore.get(key) ?? null;
  }
  setItem(key, val) {
    this.privateStore.set(key, String(val));
  }
  removeItem(key) {
    this.privateStore.delete(key);
  }
  clear() {
    this.privateStore.clear();
  }
}

const mockStorage = new MockStorage();

globalThis.localStorage = mockStorage;
if (typeof globalThis.window === "undefined") {
  globalThis.window = {
    dispatchEvent: () => true,
    addEventListener: () => {},
    removeEventListener: () => {},
  };
}
if (typeof globalThis.CustomEvent === "undefined") {
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, init) {
      this.type = type;
      this.detail = init?.detail;
    }
  };
}

describe("Storefront Customer Routing & Redirection Guard", () => {
  it("1. Uses dedicated storefront persistence keys", () => {
    assert.equal(AUTH_KEY, "storefront_isLoggedIn");
    assert.equal(TOKEN_KEY, "storefront_accessToken");
    assert.equal(USER_KEY, "storefront_currentUser");
  });

  it("2. Customer defaults to storefront root /", () => {
    assert.equal(getSafeRoleDestination("customer"), "/");
    assert.equal(getSafeRoleDestination(null), "/");
    assert.equal(getSafeRoleDestination(undefined), "/");
  });

  it("3. Customer with valid storefront path preserves path", () => {
    assert.equal(getSafeRoleDestination("customer", "/checkout"), "/checkout");
    assert.equal(getSafeRoleDestination("customer", "/account"), "/account");
    assert.equal(getSafeRoleDestination("customer", "/orders"), "/orders");
    assert.equal(getSafeRoleDestination("customer", "/cart"), "/cart");
    assert.equal(getSafeRoleDestination("customer", "/wishlist"), "/wishlist");
    assert.equal(getSafeRoleDestination("customer", "/shop?category=1"), "/shop?category=1");
  });

  it("4. Admin or seller routes are rejected in storefront and fall back to /", () => {
    assert.equal(getSafeRoleDestination("customer", "/admin"), "/");
    assert.equal(getSafeRoleDestination("customer", "/admin/dashboard"), "/");
    assert.equal(getSafeRoleDestination("customer", "/seller"), "/");
    assert.equal(getSafeRoleDestination("customer", "/seller/products"), "/");
    assert.equal(getSafeRoleDestination("admin", "/admin/dashboard"), "/");
    assert.equal(getSafeRoleDestination("seller", "/seller"), "/");
  });

  it("5. Open redirect attempts using // or /\\ are blocked", () => {
    assert.equal(getSafeRoleDestination("customer", "//malicious.com"), "/");
    assert.equal(getSafeRoleDestination("customer", "/\\malicious.com"), "/");
    assert.equal(getSafeRoleDestination("customer", "\\\\malicious.com"), "/");
    assert.equal(getSafeRoleDestination("customer", "javascript:alert(1)"), "/");
  });

  it("6. Open redirect attempts to non-allowlisted domains are blocked", () => {
    assert.equal(getSafeRoleDestination("customer", "https://malicious.com"), "/");
    assert.equal(getSafeRoleDestination("customer", "http://evil.com/admin"), "/");
    assert.equal(isAllowlistedOrigin("https://malicious.com"), false);
    assert.equal(isAllowlistedOrigin("http://localhost:3000"), true);
    assert.equal(isAllowlistedOrigin("http://localhost:3001"), true);
  });

  it("7. Customer login session lifecycle and data clearance", () => {
    clearPrivateSessionData();
    assert.equal(isLoggedIn(), false);

    const testUser = {
      id: 99,
      name: "Customer Jane",
      email: "jane@example.com",
      role: "customer",
      is_active: true,
      created_at: new Date().toISOString(),
    };
    const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
    const payload = Buffer.from(
      JSON.stringify({
        sub: "jane@example.com",
        exp: Math.floor(Date.now() / 1000) + 3600,
      })
    ).toString("base64url");
    const fakeToken = `${header}.${payload}.signature`;

    saveAuthSession(fakeToken, testUser);
    assert.equal(isLoggedIn(), true);
    assert.deepEqual(getCurrentUser(), testUser);

    logout();
    assert.equal(isLoggedIn(), false);
    assert.equal(getCurrentUser(), null);
  });

  it("8. Storefront logout does not delete Management session keys", () => {
    // Set management session keys
    mockStorage.setItem("mgmt_isLoggedIn", "true");
    mockStorage.setItem("mgmt_accessToken", "mgmt-secret-token");
    mockStorage.setItem("mgmt_currentUser", JSON.stringify({ id: 1, role: "admin" }));
    mockStorage.setItem("pos_parked_carts", JSON.stringify([{ id: 10 }]));

    // Customer logs out of storefront
    logout();

    // Verify management session is untouched
    assert.equal(mockStorage.getItem("mgmt_isLoggedIn"), "true");
    assert.equal(mockStorage.getItem("mgmt_accessToken"), "mgmt-secret-token");
    assert.notEqual(mockStorage.getItem("mgmt_currentUser"), null);
    assert.notEqual(mockStorage.getItem("pos_parked_carts"), null);
  });

  it("9. saveAuthSession tears down prior user session when switching user IDs", () => {
    const userA = { id: 1, name: "User A", email: "a@test.com", role: "customer" };
    const userB = { id: 2, name: "User B", email: "b@test.com", role: "customer" };

    const tokenHeader = Buffer.from(JSON.stringify({ alg: "HS256" })).toString("base64url");
    const tokenPayload = Buffer.from(
      JSON.stringify({ sub: "test", exp: Math.floor(Date.now() / 1000) + 3600 })
    ).toString("base64url");
    const validToken = `${tokenHeader}.${tokenPayload}.sig`;

    saveAuthSession(validToken, userA);
    mockStorage.setItem("notif_read", "true");
    assert.equal(getCurrentUser().id, 1);

    // Save session for different user ID
    saveAuthSession(validToken, userB);
    assert.equal(getCurrentUser().id, 2);
    // Prior user's private notification caches were cleared
    assert.equal(mockStorage.getItem("notif_read"), null);

    logout();
  });

  it("10. Staff redirect preserving valid management URLs", () => {
    // If admin arrives with a valid cross-app management portal redirect, allow it
    const staffRedirect = "http://localhost:3001/admin/dashboard";
    assert.equal(getSafeRoleDestination("admin", staffRedirect), staffRedirect);

    const sellerRedirect = "http://localhost:3001/seller";
    assert.equal(getSafeRoleDestination("seller", sellerRedirect), sellerRedirect);

    // Non-allowlisted external portal is rejected
    assert.equal(getSafeRoleDestination("admin", "http://untrusted-portal.com/admin"), "/");
  });
});
