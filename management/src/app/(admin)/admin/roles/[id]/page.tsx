"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  Loader2,
  Mail,
  Shield,
  Users,
} from "lucide-react";
import { settingsApi, type ApiRoleDefinition } from "@/lib/api";

export default function RoleDetailPage() {
  const params = useParams();
  const id = String(params.id || "").toLowerCase();

  const [role, setRole] = useState<ApiRoleDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRole() {
      setLoading(true);
      setError(null);
      try {
        const res = await settingsApi.getRoles();
        if (res.success && res.data) {
          const found = res.data.find((r) => r.id.toLowerCase() === id) || null;
          if (!found) {
            setError(`Role '${id}' not found.`);
          } else {
            setRole(found);
          }
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to load role details.");
      } finally {
        setLoading(false);
      }
    }
    void fetchRole();
  }, [id]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-20 flex flex-col items-center justify-center text-[#7699F0]">
        <Loader2 size={28} className="animate-spin mb-2" />
        <p className="text-xs text-gray-500">Loading role definition…</p>
      </div>
    );
  }

  if (error || !role) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <AlertCircle size={32} className="text-rose-500 mx-auto" />
        <p className="text-sm text-gray-700">{error || "Role unavailable."}</p>
        <Link href="/admin/roles" className="text-sm font-semibold text-[#7699F0] hover:underline">
          ← Back to Roles
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-10">
      <div className="flex items-center gap-4">
        <Link
          href="/admin/roles"
          className="p-2.5 rounded-xl bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 transition"
          aria-label="Back to roles"
        >
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{role.name} Role</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {role.users_count} user(s) assigned · {role.permissions_count} backend permission(s)
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-2">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-blue-50 text-[#7699F0] flex items-center justify-center">
            <Shield size={24} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">{role.name}</h2>
            <p className="text-xs text-gray-500">{role.description}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Users size={18} className="text-[#7699F0]" />
            Assigned Users ({role.users.length})
          </h2>
          <Link
            href="/admin/customers"
            className="text-xs font-semibold text-[#7699F0] hover:underline"
          >
            Manage User Roles →
          </Link>
        </div>

        {role.users.length === 0 ? (
          <p className="text-sm text-gray-400 py-6 text-center">
            No users currently assigned to &quot;{role.name}&quot;.
          </p>
        ) : (
          <div className="divide-y divide-gray-100">
            {role.users.map((u) => (
              <div key={u.id} className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-blue-50 text-[#7699F0] flex items-center justify-center font-bold text-xs">
                    {u.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{u.name}</p>
                    <p className="text-xs text-gray-400 flex items-center gap-1">
                      <Mail size={11} /> {u.email}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      u.is_active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {u.is_active ? "Active" : "Disabled"}
                  </span>
                  <Link
                    href={`/admin/customers/${u.id}`}
                    className="text-xs font-semibold text-[#7699F0] hover:underline"
                  >
                    View →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Enforced Permissions</h2>
        <div className="space-y-4">
          {role.permission_groups.map((group) => (
            <div key={group.module} className="border border-gray-100 rounded-xl p-4">
              <h3 className="text-xs font-bold text-gray-700 uppercase mb-3">
                {group.module}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {group.permissions.map((perm) => (
                  <div
                    key={perm}
                    className="flex items-center gap-2 p-2 rounded-lg bg-gray-50 text-xs font-mono text-gray-700"
                  >
                    <Check size={14} className="text-emerald-600 shrink-0" />
                    <span>{perm}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
