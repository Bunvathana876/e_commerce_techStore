import type { ApiNotification, ApiResponse } from "./api";

export type AdminFeedState =
  | { status: "loading"; notifications: ApiNotification[]; error: null }
  | { status: "ready"; notifications: ApiNotification[]; error: null }
  | { status: "error"; notifications: ApiNotification[]; error: string };

export const initialAdminFeedState: AdminFeedState = {
  status: "loading",
  notifications: [],
  error: null,
};

export interface AdminNotificationSession {
  epoch: number;
  token: string | null;
  userId: number | null;
}

export function isSameAdminNotificationSession(
  captured: AdminNotificationSession,
  current: AdminNotificationSession
): boolean {
  return captured.epoch === current.epoch && captured.token === current.token &&
    captured.userId === current.userId;
}

export function isPersonalAdminNotification(
  notification: Pick<ApiNotification, "user_id">,
  adminUserId: number
): boolean {
  return Number.isSafeInteger(adminUserId) && adminUserId > 0 &&
    notification.user_id === adminUserId;
}

export function isUnreadPersonalAdminNotification(
  notification: Pick<ApiNotification, "user_id" | "read">,
  adminUserId: number
): boolean {
  return isPersonalAdminNotification(notification, adminUserId) && !notification.read;
}

export async function loadAdminFeed(
  fetchFeed: () => Promise<ApiResponse<ApiNotification[]>>,
  adminUserId: number
): Promise<AdminFeedState> {
  try {
    if (!Number.isSafeInteger(adminUserId) || adminUserId <= 0) {
      throw new Error("Administrator session is unavailable.");
    }
    const response = await fetchFeed();
    if (!response.success || !Array.isArray(response.data)) {
      throw new Error("Could not load notifications.");
    }
    if (response.data.some((notification) =>
      notification.user_id !== null && notification.user_id !== adminUserId
    )) {
      throw new Error("Notification recipient mismatch.");
    }
    return { status: "ready", notifications: response.data, error: null };
  } catch (error) {
    return {
      status: "error",
      notifications: [],
      error: error instanceof Error ? error.message : "Could not load notifications.",
    };
  }
}

export async function mutatePersonalAdminNotification(
  notification: Pick<ApiNotification, "user_id">,
  adminUserId: number,
  mutate: () => Promise<{ success: boolean }>,
  refresh: () => Promise<unknown>
): Promise<void> {
  if (!isPersonalAdminNotification(notification, adminUserId)) {
    throw new Error("Shared notices have no per-admin read or delete state.");
  }
  const response = await mutate();
  if (!response.success) throw new Error("Notification action failed.");
  await refresh();
}

export async function mutatePersonalAdminFeed(
  mutate: () => Promise<{ success: boolean }>,
  refresh: () => Promise<unknown>
): Promise<void> {
  const response = await mutate();
  if (!response.success) throw new Error("Notification action failed.");
  await refresh();
}
