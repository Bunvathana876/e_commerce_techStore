import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

const values = new Map();
globalThis.localStorage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, String(value)),
  removeItem: (key) => values.delete(key),
};
globalThis.window = {
  dispatchEvent: () => true,
  addEventListener: () => {},
  removeEventListener: () => {},
  location: { pathname: "/admin/notifications", href: "" },
};
globalThis.CustomEvent = class CustomEvent {
  constructor(type, init) {
    this.type = type;
    this.detail = init?.detail;
  }
};

const {
  initialAdminFeedState,
  isSameAdminNotificationSession,
  isPersonalAdminNotification,
  isUnreadPersonalAdminNotification,
  loadAdminFeed,
  mutatePersonalAdminFeed,
  mutatePersonalAdminNotification,
} = await import("../admin-notification-feed.ts");
const { notificationsApi } = await import("../api.ts");
const { saveAuthSession, getAccessToken } = await import("../auth.ts");

function token() {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({ sub: "1", exp: Math.floor(Date.now() / 1000) + 3600 })).toString("base64url");
  return `${header}.${payload}.test-signature`;
}

function notice(id, userId, read = false) {
  return {
    id, user_id: userId, type: "system", title: `Notice ${id}`,
    message: "Test notice", link: null, read,
    created_at: "2026-11-16T00:00:00", updated_at: "2026-11-16T00:00:00",
  };
}

function feed(data) {
  return { success: true, message: "Notifications retrieved successfully.", data };
}

beforeEach(() => {
  values.clear();
  saveAuthSession(token(), { id: 1, role: "admin", name: "Admin", email: "admin@example.test" });
});

describe("admin notification feed lifecycle", () => {
  it("discards late responses after same-tab and cross-tab account changes", () => {
    const captured = { epoch: 5, token: "old-token", userId: 1 };
    assert.equal(isSameAdminNotificationSession(captured, { ...captured }), true);
    assert.equal(isSameAdminNotificationSession(captured, { ...captured, epoch: 6 }), false);
    assert.equal(isSameAdminNotificationSession(captured, { ...captured, token: "new-token" }), false);
    assert.equal(isSameAdminNotificationSession(captured, { ...captured, userId: 2 }), false);
  });

  it("starts loading and handles an empty successful feed", async () => {
    assert.equal(initialAdminFeedState.status, "loading");
    assert.deepEqual(initialAdminFeedState.notifications, []);
    assert.deepEqual(await loadAdminFeed(async () => feed([]), 1), {
      status: "ready", notifications: [], error: null,
    });
  });

  it("keeps only the admin's private notice and shared notices in the feed", async () => {
    const personal = notice(11, 1);
    const shared = notice(12, null);
    const result = await loadAdminFeed(async () => feed([personal, shared]), 1);
    assert.equal(result.status, "ready");
    assert.deepEqual(result.notifications.map((item) => item.id), [11, 12]);
    assert.equal(isUnreadPersonalAdminNotification(personal, 1), true);
    assert.equal(isUnreadPersonalAdminNotification(shared, 1), false);
    assert.equal(isPersonalAdminNotification(shared, 1), false);
  });

  it("fails closed for a foreign private notice or missing admin identity", async () => {
    const leaked = await loadAdminFeed(async () => feed([notice(13, 2)]), 1);
    assert.equal(leaked.status, "error");
    assert.deepEqual(leaked.notifications, []);
    assert.match(leaked.error, /recipient mismatch/i);
    const missing = await loadAdminFeed(async () => feed([notice(11, 1)]), -1);
    assert.equal(missing.status, "error");
    assert.deepEqual(missing.notifications, []);
  });

  it("reports fetch and authorization failures without returning cached notices", async () => {
    for (const message of ["Offline", "Permission denied."]) {
      const result = await loadAdminFeed(async () => { throw new Error(message); }, 1);
      assert.equal(result.status, "error");
      assert.deepEqual(result.notifications, []);
      assert.equal(result.error, message);
    }
  });

  it("refreshes after successful read and delete, and preserves state on failure", async () => {
    let mutations = 0;
    let refreshes = 0;
    const mutate = async () => { mutations += 1; return { success: true }; };
    const refresh = async () => { refreshes += 1; };
    await mutatePersonalAdminNotification(notice(11, 1), 1, mutate, refresh);
    await mutatePersonalAdminNotification(notice(11, 1), 1, mutate, refresh);
    assert.equal(mutations, 2);
    assert.equal(refreshes, 2);

    await assert.rejects(
      mutatePersonalAdminNotification(notice(12, null), 1, mutate, refresh),
      /shared notices/i
    );
    await assert.rejects(
      mutatePersonalAdminNotification(notice(13, 2), 1, mutate, refresh),
      /shared notices/i
    );
    assert.equal(mutations, 2);
    assert.equal(refreshes, 2);

    await assert.rejects(
      mutatePersonalAdminNotification(notice(11, 1), 1, async () => { throw new Error("Forbidden"); }, refresh),
      /Forbidden/
    );
    await assert.rejects(
      mutatePersonalAdminFeed(async () => ({ success: false }), refresh),
      /action failed/i
    );
    assert.equal(refreshes, 2);
    await mutatePersonalAdminFeed(mutate, refresh);
    assert.equal(refreshes, 3);
  });
});

describe("management API contract", () => {
  it("uses admin paths, methods, and the management bearer token", async () => {
    const calls = [];
    globalThis.fetch = async (url, options) => {
      const parsed = new URL(url);
      calls.push({ pathname: parsed.pathname + parsed.search, method: options.method ?? "GET", authorization: options.headers.Authorization });
      const response = options.method === "DELETE" && parsed.pathname.endsWith("/11")
        ? { success: true, message: "Notification deleted." }
        : parsed.pathname.endsWith("/unread-count")
          ? { success: true, unread_count: 0 }
          : { ...feed([]), unread_count: 0 };
      return new Response(JSON.stringify(response), { status: 200, headers: { "Content-Type": "application/json" } });
    };
    const listed = await notificationsApi.getAll({ limit: 4 });
    await notificationsApi.getUnreadCount();
    await notificationsApi.markAsRead(11);
    await notificationsApi.markAllAsRead();
    const deleted = await notificationsApi.delete(11);
    await notificationsApi.clearAll();
    assert.deepEqual(calls.map(({ pathname, method }) => [method, pathname]), [
      ["GET", "/api/notifications/admin?limit=4"],
      ["GET", "/api/notifications/admin/unread-count"],
      ["PATCH", "/api/notifications/admin/11/read"],
      ["POST", "/api/notifications/admin/read-all"],
      ["DELETE", "/api/notifications/admin/11"],
      ["DELETE", "/api/notifications/admin"],
    ]);
    assert.ok(calls.every((call) => call.authorization === `Bearer ${getAccessToken()}`));
    assert.ok(calls.every((call) => !call.pathname.startsWith("/api/notifications/11")));
    assert.equal(listed.unread_count, 0);
    assert.deepEqual(deleted, { success: true, message: "Notification deleted." });
  });

  it("surfaces read and delete HTTP failures, including authorization errors", async () => {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Permission denied." }), {
      status: 403, headers: { "Content-Type": "application/json" },
    });
    await assert.rejects(notificationsApi.markAsRead(11), /Permission denied/);
    await assert.rejects(notificationsApi.delete(11), /Permission denied/);
    assert.ok(getAccessToken());
  });

  it("invalidates the management session on an unauthorized response", async () => {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Authentication required" }), {
      status: 401, headers: { "Content-Type": "application/json" },
    });
    await assert.rejects(notificationsApi.getAll(), /Authentication required/);
    assert.equal(getAccessToken(), null);
  });
});
