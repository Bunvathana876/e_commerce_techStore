import type { ApiUser } from "./api";

export const AUTH_KEY = "isLoggedIn";
export const TOKEN_KEY = "accessToken";
export const USER_KEY = "currentUser";

/**
 * Tracks the current session generation.
 * Incremented whenever authentication state changes (login, logout, account switch).
 * In-flight async responses compare their captured epoch against getSessionEpoch()
 * and discard their results if the epoch has advanced.
 */
let currentSessionEpoch = 0;

export function getSessionEpoch(): number {
  return currentSessionEpoch;
}

export function incrementSessionEpoch(): number {
  currentSessionEpoch += 1;
  return currentSessionEpoch;
}

/**
 * Registry of logout callbacks (e.g. stores, memory caches) to execute synchronously
 * when a user logs out.
 */
const logoutHandlers: Array<() => void> = [];

export function onLogout(handler: () => void): () => void {
  logoutHandlers.push(handler);
  return () => {
    const idx = logoutHandlers.indexOf(handler);
    if (idx !== -1) {
      logoutHandlers.splice(idx, 1);
    }
  };
}

/**
 * Checks whether a given JWT token string is structurally valid and not expired.
 */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const decoded = JSON.parse(jsonPayload);
    if (!decoded.exp) return false;
    // Buffer by 10 seconds to avoid race condition near expiration
    return Date.now() >= (decoded.exp * 1000 - 10000);
  } catch {
    return true;
  }
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token || localStorage.getItem(AUTH_KEY) !== "true") return false;
  if (isTokenExpired(token)) {
    logout("token_expired");
    return false;
  }
  return true;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  if (isTokenExpired(token)) {
    logout("token_expired");
    return null;
  }
  return token;
}

export function getCurrentUser(): ApiUser | null {
  if (typeof window === "undefined") return null;
  const userStr = localStorage.getItem(USER_KEY);
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
}

export function getCurrentUserId(): number | null {
  const user = getCurrentUser();
  return user?.id ?? null;
}

/**
 * Removes user credentials and private feature caches from localStorage,
 * preserving public/neutral preferences (e.g. theme, public catalog settings).
 */
export function clearPrivateSessionData(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);

  // Private notification caches
  localStorage.removeItem("notif_read");
  localStorage.removeItem("notif_cleared_at");
  localStorage.removeItem("notif_deleted_ids");

  // Private merchant / cashier caches
  localStorage.removeItem("pos_parked_carts");

  // Zustand persistent shop storage
  localStorage.removeItem("blue-panda-shop-storage");
}

export function saveAuthSession(token: string, user: ApiUser): void {
  if (typeof window === "undefined") return;
  const previousUser = getCurrentUser();
  // If switching between different authenticated accounts, ensure prior session is torn down first
  if (previousUser && previousUser.id !== user.id) {
    clearPrivateSessionData();
  }
  incrementSessionEpoch();

  localStorage.setItem(AUTH_KEY, "true");
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));

  window.dispatchEvent(
    new CustomEvent("auth-changed", { detail: { action: "login", user } })
  );
}

export function logout(reason?: string): void {
  if (typeof window === "undefined") return;
  // 1. Advance session generation to invalidate any in-flight requests from this session
  incrementSessionEpoch();

  // 2. Clear private session keys and caches
  clearPrivateSessionData();

  // 3. Execute registered store/cache cleanup handlers synchronously
  for (const handler of logoutHandlers) {
    try {
      handler();
    } catch (err) {
      console.error("Error in logout handler:", err);
    }
  }

  // 4. Dispatch auth-changed event to inform UI components
  window.dispatchEvent(
    new CustomEvent("auth-changed", { detail: { action: "logout", reason } })
  );
}

/**
 * Safely resolves post-auth destination based on user role and optional redirect parameter.
 * Prevents open redirect attacks (//, /\, protocol schemes) and cross-role privilege escalation
 * (e.g. customers or sellers attempting to navigate into /admin, or admins into /seller).
 */
export function getSafeRoleDestination(
  role: string | undefined | null,
  redirectParam?: string | null
): string {
  const normalizedRole = (role || "customer").toLowerCase().trim();

  // Determine standard role home
  let roleHome = "/";
  if (normalizedRole === "admin") {
    roleHome = "/admin/dashboard";
  } else if (normalizedRole === "seller") {
    roleHome = "/seller";
  }

  if (!redirectParam) {
    return roleHome;
  }

  // Prevent open redirects & protocol exploits
  const trimmed = redirectParam.trim();
  if (
    !trimmed.startsWith("/") ||
    trimmed.startsWith("//") ||
    trimmed.startsWith("/\\") ||
    trimmed.includes("://")
  ) {
    return roleHome;
  }

  // Validate path access against role
  if (trimmed.startsWith("/admin")) {
    return normalizedRole === "admin" ? trimmed : roleHome;
  }

  if (trimmed.startsWith("/seller")) {
    return normalizedRole === "seller" ? trimmed : roleHome;
  }

  // Storefront and public customer routes (/shop, /checkout, /orders, /account, etc.)
  // If an admin or seller logs in with a public storefront redirect, allow it unless it conflicts
  return trimmed;
}
