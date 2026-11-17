"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Cpu,
  Gamepad2,
  Headphones,
  Heart,
  Laptop,
  PackageCheck,
  ShoppingBag,
  Trash2,
} from "lucide-react";
import { useShopStore } from "@/lib/store";
import ProductCard from "@/components/store/ProductCard";

const TECH_SHORTCUTS = [
  {
    name: "Computers & Laptops",
    icon: Laptop,
    href: "/shop?category=Computers%20%26%20Laptops",
  },
  {
    name: "PC Components",
    icon: Cpu,
    href: "/shop?category=PC%20Components",
  },
  {
    name: "Gaming Gear",
    icon: Gamepad2,
    href: "/shop?category=Gaming%20Gear",
  },
  {
    name: "Headphones & Audio",
    icon: Headphones,
    href: "/shop?category=Headphones%20%26%20Audio",
  },
];

export default function WishlistPage() {
  const wishlist = useShopStore((s) => s.wishlist);
  const addToCart = useShopStore((s) => s.addToCart);
  const toggleWishlist = useShopStore((s) => s.toggleWishlist);
  const pushToast = useShopStore((s) => s.pushToast);

  const [confirmClear, setConfirmClear] = useState(false);
  const [movingToBag, setMovingToBag] = useState(false);

  const inStockItems = wishlist.filter((item) => (item.stock ?? 0) > 0);
  const outOfStockCount = wishlist.length - inStockItems.length;

  const handleMoveAllToBag = async () => {
    if (inStockItems.length === 0) {
      pushToast({
        title: "All Items Out of Stock",
        description: "None of your saved products are currently available in inventory.",
        tone: "error",
      });
      return;
    }

    setMovingToBag(true);
    try {
      for (const item of inStockItems) {
        await addToCart(item, 1, undefined, false);
      }

      pushToast({
        title: "Items Added to Bag",
        description:
          outOfStockCount > 0
            ? `Added ${inStockItems.length} available items to your bag (${outOfStockCount} out of stock).`
            : `Added all ${inStockItems.length} items to your shopping bag.`,
        tone: "success",
      });

      useShopStore.getState().openCart();
    } finally {
      setMovingToBag(false);
    }
  };

  const handleClearAll = () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }

    [...wishlist].forEach((p) => toggleWishlist(p));
    setConfirmClear(false);
    pushToast({
      title: "Wishlist Cleared",
      description: "All saved products have been removed from your wishlist.",
      tone: "info",
    });
  };

  return (
    <div className="min-h-[70vh] bg-[#F5F8FD]/60 pb-16">
      <div className="bp-container space-y-8 pt-10 sm:pt-14">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-slate-200/80">
          <div>
            <p className="bp-eyebrow">Wishlist</p>
            <h1 className="mt-3 text-4xl font-bold text-ink sm:text-5xl">
              Saved for later{" "}
              <span className="bp-price font-sans text-xl font-medium text-muted">
                {wishlist.length} {wishlist.length === 1 ? "item" : "items"}
              </span>
            </h1>
            <p className="text-sm text-slate-500 mt-1.5 max-w-2xl">
              Monitor inventory availability, track pricing changes, and seamlessly move products directly to your shopping bag.
            </p>
          </div>

          {wishlist.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              {/* In-Stock summary pills */}
              <div className="hidden sm:flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white border border-slate-200/80 text-xs shadow-xs">
                <span className="inline-flex items-center gap-1.5 font-bold text-emerald-700">
                  <PackageCheck size={14} className="text-emerald-600" />
                  {inStockItems.length} In Stock
                </span>
                {outOfStockCount > 0 && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span className="font-semibold text-rose-600">
                      {outOfStockCount} Sold Out
                    </span>
                  </>
                )}
              </div>

              {/* Move to bag button */}
              <button
                type="button"
                onClick={handleMoveAllToBag}
                disabled={movingToBag || inStockItems.length === 0}
                className="px-5 py-2.5 rounded-2xl bg-[#245BE7] hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none text-white text-xs font-extrabold inline-flex items-center gap-2 shadow-md shadow-blue-600/20 transition cursor-pointer active:scale-98"
              >
                <ShoppingBag size={15} />
                {movingToBag ? "Adding Items..." : "Move Available to Bag"}
              </button>

              {/* Clear button */}
              <button
                type="button"
                onClick={handleClearAll}
                className={`px-4 py-2.5 rounded-2xl text-xs font-bold inline-flex items-center gap-1.5 transition cursor-pointer border ${
                  confirmClear
                    ? "bg-rose-50 border-rose-300 text-rose-700 hover:bg-rose-100"
                    : "bg-white border-slate-200 hover:border-rose-200 hover:text-rose-600 text-slate-600 shadow-xs"
                }`}
              >
                {confirmClear ? (
                  <>
                    <Check size={14} />
                    Confirm Clear?
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    Clear List
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Content Section */}
        {wishlist.length === 0 ? (
          <div className="max-w-2xl mx-auto py-12 text-center">
            <div className="bg-white rounded-[2.5rem] border border-slate-200/80 p-8 sm:p-14 shadow-sm text-center">
              <div className="w-20 h-20 rounded-3xl bg-blue-50/80 border border-blue-100/60 text-[#245BE7] flex items-center justify-center mx-auto mb-6 shadow-inner">
                <Heart size={36} className="text-[#245BE7] fill-blue-100/50" />
              </div>

              <h2 className="text-2xl sm:text-3xl font-semibold text-[#181818] tracking-tight">
                Your Saved Gear is Empty
              </h2>
              <p className="text-sm text-slate-500 mt-2.5 max-w-md mx-auto leading-relaxed">
                Curate your workstation setup, compare technical specs, or track price drops. Tap the heart icon on any product to save it here for later.
              </p>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <Link
                  href="/shop"
                  className="inline-flex items-center gap-2 px-7 py-3.5 rounded-2xl bg-[#245BE7] hover:bg-blue-700 text-white text-sm font-extrabold shadow-lg shadow-blue-600/20 transition active:scale-98"
                >
                  Discover Hardware Catalog <ArrowRight size={16} />
                </Link>
              </div>

              {/* Tech Category Discovery Shortcuts */}
              <div className="mt-12 pt-8 border-t border-slate-100">
                <p className="text-xs font-extrabold uppercase tracking-wider text-slate-400 mb-4">
                  Or Explore by Category
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-left">
                  {TECH_SHORTCUTS.map((cat) => {
                    const Icon = cat.icon;
                    return (
                      <Link
                        key={cat.name}
                        href={cat.href}
                        className="group flex flex-col p-3.5 rounded-2xl bg-slate-50 hover:bg-blue-50/60 border border-slate-100 hover:border-blue-200 transition"
                      >
                        <Icon
                          size={18}
                          className="text-slate-400 group-hover:text-[#245BE7] transition mb-2"
                        />
                        <span className="text-xs font-bold text-slate-800 group-hover:text-[#245BE7] leading-snug">
                          {cat.name}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {wishlist.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
