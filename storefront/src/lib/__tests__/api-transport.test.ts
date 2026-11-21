import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { authApi, productsApi } from "../api";
import { TOKEN_KEY } from "../auth";

const originalFetch = globalThis.fetch;
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
const originalStorage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
  else Reflect.deleteProperty(globalThis, "window");
  if (originalStorage) Object.defineProperty(globalThis, "localStorage", originalStorage);
  else Reflect.deleteProperty(globalThis, "localStorage");
});

test("guest catalog GET is CORS-simple and keeps no-store semantics", async () => {
  globalThis.fetch = async (_input, options) => {
    const headers = new Headers(options?.headers);
    assert.equal(headers.has("Content-Type"), false);
    assert.equal(headers.has("Authorization"), false);
    assert.equal(options?.cache, "no-store");
    return Response.json({ success: true, data: { items: [] } });
  };
  await productsApi.list({ limit: 20 });
});

test("JSON writes still send the correct content type and payload", async () => {
  const credentials = { email: "fixture@example.com", password: "test-only" };
  globalThis.fetch = async (_input, options) => {
    assert.equal(new Headers(options?.headers).get("Content-Type"), "application/json");
    assert.equal(options?.method, "POST");
    assert.deepEqual(JSON.parse(String(options?.body)), credentials);
    return Response.json({ success: true });
  };
  await authApi.login(credentials);
});

test("authenticated GET keeps bearer authorization", async () => {
  const token = `e30.${Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url")}.fixture`;
  Object.defineProperty(globalThis, "window", { configurable: true, value: {} });
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: (key: string) => key === TOKEN_KEY ? token : null },
  });
  globalThis.fetch = async (_input, options) => {
    const headers = new Headers(options?.headers);
    assert.equal(headers.get("Authorization"), `Bearer ${token}`);
    assert.equal(headers.has("Content-Type"), false);
    return Response.json({ success: true });
  };
  await authApi.getMe();
});

test("failed requests preserve their status and message", async () => {
  globalThis.fetch = async () => Response.json({ detail: "Unavailable" }, { status: 503 });
  await assert.rejects(productsApi.list(), { message: "Unavailable", status: 503 });
});
