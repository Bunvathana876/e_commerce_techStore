import assert from "node:assert/strict";
import { afterEach, beforeEach, it } from "node:test";
import { getAccessToken, getSessionEpoch, logout, logoutFromServer, onLogout, saveAuthSession, TOKEN_KEY } from "../auth.ts";
import { authApi, uploadApi } from "../api.ts";

const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: (key) => storage.delete(key),
};
globalThis.window = { dispatchEvent() {}, location: { pathname: "/login" } };
const originalFetch = globalThis.fetch;
const user = { id: 21, name: "Fixture", email: "fixture@example.invalid", role: "customer", is_active: true };
const tokenFor = (id) => `e30.${Buffer.from(JSON.stringify({ sub: String(id), exp: Date.now() / 1000 + 3600 })).toString("base64url")}.fixture`;
const reply = (status = 200) => new Response(JSON.stringify({ success: status === 200, data: null }), { status });

beforeEach(() => { logout(); storage.clear(); });
afterEach(() => { globalThis.fetch = originalFetch; });

for (const outcome of [200, 401, 500, "offline", "synchronous"]) {
  it(`logout sends the original bearer and clears private state for ${outcome}`, async () => {
    const token = tokenFor(21);
    saveAuthSession(token, user);
    const epoch = getSessionEpoch();
    let calls = 0;
    let cleanups = 0;
    const unregister = onLogout(() => { cleanups++; });
    globalThis.fetch = (url, options) => {
      calls++;
      assert.match(url, /\/api\/auth\/logout$/);
      assert.equal(options.method, "POST");
      assert.equal(options.headers.Authorization, `Bearer ${token}`);
      assert.equal(storage.get(TOKEN_KEY), token);
      assert.equal(options.credentials, "omit");
      assert.equal(options.redirect, "error");
      assert.equal(options.cache, "no-store");
      assert.equal(options.keepalive, true);
      assert.equal(options.body, undefined);
      if (outcome === "synchronous") throw new Error(token);
      if (outcome === "offline") return Promise.reject(new Error(token));
      return Promise.resolve(reply(outcome));
    };
    try {
      const pending = logoutFromServer();
      assert.equal(getAccessToken(), null, "local cleanup happens before network completion");
      assert.equal(getSessionEpoch(), epoch + 1);
      assert.equal(await pending, outcome === 200);
      assert.equal(calls, 1);
      assert.equal(cleanups, 1);
    } finally { unregister(); }
  });
}

for (const status of [200, 401, 500]) {
  it(`a delayed logout ${status} cannot clear a later login`, async () => {
    saveAuthSession(tokenFor(21), user);
    let finish;
    globalThis.fetch = () => new Promise((resolve) => { finish = resolve; });
    const pending = logoutFromServer();
    const nextToken = tokenFor(22);
    saveAuthSession(nextToken, { ...user, id: 22 });
    finish(reply(status));
    await pending;
    assert.equal(getAccessToken(), nextToken);
  });
}

it("does not send an anonymous logout or refresh request", async () => {
  globalThis.fetch = () => { throw new Error("Must not send"); };
  assert.equal(await logoutFromServer(), false);
});

for (const operation of ["profile", "upload"]) {
  it(`a late ${operation} 401 cannot log out the next account`, async () => {
    saveAuthSession(tokenFor(21), user);
    let finish;
    globalThis.fetch = () => new Promise((resolve) => { finish = resolve; });
    const pending = operation === "profile" ? authApi.getMe() : uploadApi.uploadImage(new File(["fixture"], "test.png"));
    const nextToken = tokenFor(22);
    saveAuthSession(nextToken, { ...user, id: 22 });
    finish(reply(401));
    await assert.rejects(pending);
    assert.equal(getAccessToken(), nextToken);
  });
}

it("clears the requesting session after password-change revocation", async () => {
  saveAuthSession(tokenFor(21), user);
  globalThis.fetch = async () => reply();
  await authApi.changePassword({ current_password: "test-only", new_password: "test-only" });
  assert.equal(getAccessToken(), null);
});

it("password-change completion cannot clear a later login", async () => {
  saveAuthSession(tokenFor(21), user);
  let finish;
  globalThis.fetch = () => new Promise((resolve) => { finish = resolve; });
  const pending = authApi.changePassword({ current_password: "test-only", new_password: "test-only" });
  const nextToken = tokenFor(22);
  saveAuthSession(nextToken, { ...user, id: 22 });
  finish(reply());
  await pending;
  assert.equal(getAccessToken(), nextToken);
});

it("expired sessions clear locally without attempting refresh or remote logout", async () => {
  const expired = `e30.${Buffer.from(JSON.stringify({ exp: 1 })).toString("base64url")}.fixture`;
  saveAuthSession(expired, user);
  let calls = 0;
  globalThis.fetch = async () => { calls++; return reply(); };
  assert.equal(await logoutFromServer(), false);
  assert.equal(getAccessToken(), null);
  assert.equal(calls, 0);
});

it("logout never logs credentials carried by network or cleanup exceptions", async () => {
  const token = tokenFor(21);
  saveAuthSession(token, user);
  const messages = [];
  const originalError = console.error;
  const originalWarn = console.warn;
  console.error = (...args) => messages.push(args.join(" "));
  console.warn = (...args) => messages.push(args.join(" "));
  const unregister = onLogout(() => { throw new Error(token); });
  globalThis.fetch = async () => { throw new Error(token); };
  try {
    await logoutFromServer();
    assert.ok(messages.length > 0);
    assert.ok(messages.every((message) => !message.includes(token)));
  } finally {
    unregister();
    console.error = originalError;
    console.warn = originalWarn;
  }
});
