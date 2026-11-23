"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ChevronRight,
  Loader2,
  Search,
  Shield,
  Users,
} from "lucide-react";
import { settingsApi, type ApiRoleDefinition } from "@/lib/api";

const ROLE_COLORS: Record<string, string> = {
  admin: "from-[#7699F0] to-blue-600",
  seller: "from-emerald-500 to-teal-600",
  customer: "from-indigo-500 to-violet-600",
  staff: "from-amber-500 to-orange-600",
  employee: "from-slate-600 to-slate-800",
};

export default function RolesPage() {
  const [roles, setRoles] = useState<ApiRoleDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const fetchRoles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await settingsApi.getRoles();
      if (res.success && res.data) {
        setRoles(res.data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load roles & permissions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRoles();
  }, [fetchRoles]);

  const filtered = roles.filter(
    (role) =>
      role.name.toLowerCase().includes(search.toLowerCase()) ||
      role.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Roles & Permissions</h1>
          <p className="text-sm text-gray-500 mt-1">
            Backend-enforced RBAC permission groups and live assigned user counts
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
        <div className="relative">
          <Search
            size={18}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="search"
            aria-label="Search roles"
            placeholder="Search roles by title or capability..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#7699F0]"
          />
        </div>
      </div>

      {error && (
        <div role="alert" className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-center gap-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center text-[#7699F0]">
          <Loader2 size={32} className="animate-spin mb-2" />
          <p className="text-sm font-medium text-gray-500">
            Loading roles & permissions from backend…
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((role) => (
            <div
              key={role.id}
              className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4 hover:shadow-md transition group"
            >
              <div className="flex items-start justify-between">
                <div
                  className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${
                    ROLE_COLORS[role.id] || "from-slate-600 to-slate-800"
                  } flex items-center justify-center text-white shadow-sm`}
                >
                  <Shield size={24} />
                </div>
                {role.is_system && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-50 text-violet-700">
                    System Role
                  </span>
                )}
              </div>

              <div>
                <h2 className="text-lg font-bold text-gray-900 group-hover:text-[#7699F0] transition">
                  {role.name}
                </h2>
                <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                  {role.description}
                </p>
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-gray-100 text-xs text-gray-500">
                <span className="flex items-center gap-1.5 font-medium text-gray-900">
                  <Users size={14} className="text-[#7699F0]" />
                  {role.users_count} user(s)
                </span>
                <span>{role.permissions_count} permissions</span>
              </div>

              <Link
                href={`/admin/roles/${role.id}`}
                className="flex items-center justify-between w-full pt-2 text-sm font-semibold text-[#7699F0] hover:underline"
              >
                <span>Inspect Role & Users</span>
                <ChevronRight size={16} />
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
