"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  MapPin,
  Phone,
  RefreshCw,
  ShieldCheck,
  Star,
  Store,
} from "lucide-react";
import type { ApiSeller } from "@/lib/api";
import { fetchStoreSellers } from "@/lib/store-catalog";

export default function OfficialStoresPage() {
  const [sellers, setSellers] = useState<ApiSeller[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadStores = useCallback(() => {
    setLoading(true);
    setLoadError(null);
    fetchStoreSellers().then((data) => {
      setSellers(data);
      if (!data.isLiveBackend && data.length === 0) {
        setLoadError("We couldn't load official partner stores. Please try again.");
      }
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    loadStores();
  }, [loadStores]);

  return (
    <div className="bp-container space-y-10 py-10 sm:py-14">
      <div className="max-w-2xl">
        <span className="inline-flex items-center gap-1.5 text-xs font-extrabold uppercase tracking-wider text-blue-600">
          <ShieldCheck size={15} /> 100% Verified Merchants
        </span>
        <h1 className="mt-3 text-4xl font-bold text-ink sm:text-5xl">
          Official Partner Stores
        </h1>
        <p className="text-sm text-slate-500 mt-2 leading-relaxed">
          Every Official Store on Blue Panda undergoes verified merchant onboarding
          for authentic product listings, active customer support, and reliable dispatch.
        </p>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-64 rounded-[2rem] bg-slate-100 animate-pulse border border-slate-200/80"
            />
          ))}
        </div>
      ) : loadError && sellers.length === 0 ? (
        <div className="bg-white rounded-3xl border border-rose-200 p-12 text-center max-w-2xl mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-4">
            <AlertCircle size={28} />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900">
            Unable to Load Partner Stores
          </h2>
          <p className="text-sm text-slate-500 mt-2 leading-relaxed">
            {loadError}
          </p>
          <button
            type="button"
            onClick={loadStores}
            className="mt-6 inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-extrabold transition cursor-pointer"
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      ) : sellers.length === 0 ? (
        <div className="bg-white rounded-3xl border border-slate-200/80 p-12 text-center max-w-2xl mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
            <Store size={28} />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900">
            No Official Partner Stores Listed
          </h2>
          <p className="text-sm text-slate-500 mt-2 leading-relaxed">
            All current tech products are fulfilled directly through Blue Panda verified inventory. Check back as independent verified partner storefronts launch.
          </p>
          <Link
            href="/shop"
            className="mt-6 inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-extrabold transition"
          >
            Explore Blue Panda Catalog <ArrowRight size={14} />
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sellers.map((seller) => (
            <div
              key={seller.id}
              className="bg-white rounded-[2rem] border border-slate-200/80 p-7 shadow-xs hover:shadow-xl transition flex flex-col justify-between gap-6"
            >
              <div>
                <div className="flex items-start justify-between gap-4">
                  <div aria-hidden="true"
                    className="flex h-14 w-14 items-center justify-center rounded-full bg-ink text-xl font-semibold text-white">
                    {seller.name.charAt(0)}
                  </div>
                  {Number(seller.rating) > 0 ? (
                    <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-extrabold">
                      <Star size={13} className="fill-amber-400 text-amber-400" />
                      {Number(seller.rating).toFixed(2)} Rating
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-extrabold">
                      Verified Seller
                    </span>
                  )}
                </div>

                <h2 className="text-xl font-extrabold text-slate-900 mt-5 flex items-center gap-2">
                  {seller.name}
                  <ShieldCheck size={18} className="text-blue-600 shrink-0" />
                </h2>
                {seller.owner_name && (
                  <p className="text-xs font-semibold text-slate-400 mt-0.5">
                    Managed by {seller.owner_name}
                  </p>
                )}

                <p className="text-sm text-slate-600 mt-3 leading-relaxed">
                  {seller.description ||
                    "Authorized official Blue Panda retailer delivering genuine products and responsive customer service."}
                </p>

                <div className="mt-4 space-y-1.5 text-xs text-slate-500">
                  {seller.address && (
                    <p className="flex items-center gap-2">
                      <MapPin size={13} className="text-blue-600 shrink-0" />
                      {seller.address}
                    </p>
                  )}
                  {seller.phone && (
                    <p className="flex items-center gap-2">
                      <Phone size={13} className="text-blue-600 shrink-0" />
                      {seller.phone}
                    </p>
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-500 inline-flex items-center gap-1.5">
                  <Store size={14} className="text-blue-600" />
                  {seller.products_count ?? 0}{" "}
                  {(seller.products_count ?? 0) === 1
                    ? "Active Listing"
                    : "Active Listings"}
                </span>
                <Link
                  href={`/shop?seller=${seller.id}`}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-extrabold inline-flex items-center gap-1.5 transition"
                >
                  Shop Store <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
