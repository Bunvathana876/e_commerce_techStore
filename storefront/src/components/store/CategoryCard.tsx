import Link from "next/link";
import {
  ArrowRight,
  Cpu,
  Gamepad2,
  Headphones,
  Laptop,
  Monitor,
  Package,
  Shirt,
  ShoppingBag,
  Smartphone,
  Watch,
} from "lucide-react";
import type { ApiCategory } from "@/lib/api";
import { applyProductImageFallback } from "@/lib/store-catalog";

interface CategoryCardProps {
  category: ApiCategory;
  image?: string | null;
  count?: number;
}

function renderCategoryIcon(name: string, size = 24) {
  const lower = name.toLowerCase();
  if (lower.includes("laptop") || lower.includes("computer") || lower.includes("pc")) {
    return <Laptop size={size} />;
  }
  if (lower.includes("audio") || lower.includes("headphone") || lower.includes("sound") || lower.includes("electr")) {
    return <Headphones size={size} />;
  }
  if (lower.includes("game") || lower.includes("gaming") || lower.includes("console")) {
    return <Gamepad2 size={size} />;
  }
  if (lower.includes("phone") || lower.includes("mobile") || lower.includes("smartphone")) {
    return <Smartphone size={size} />;
  }
  if (
    lower.includes("component") ||
    lower.includes("gpu") ||
    lower.includes("cpu") ||
    lower.includes("chip")
  ) {
    return <Cpu size={size} />;
  }
  if (lower.includes("monitor") || lower.includes("screen") || lower.includes("display")) {
    return <Monitor size={size} />;
  }
  if (lower.includes("accessory") || lower.includes("watch") || lower.includes("wallet")) {
    return <Watch size={size} />;
  }
  if (lower.includes("shoe") || lower.includes("footwear") || lower.includes("sneaker")) {
    return <ShoppingBag size={size} />;
  }
  if (lower.includes("fashion") || lower.includes("cloth") || lower.includes("hoodie")) {
    return <Shirt size={size} />;
  }
  return <Package size={size} />;
}

function getCategoryColorTheme(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes("laptop") || lower.includes("computer") || lower.includes("pc")) {
    return {
      bg: "bg-gradient-to-br from-blue-500/15 via-cyan-500/10 to-indigo-500/10",
      border: "border-blue-100 group-hover:border-blue-400 group-hover:shadow-blue-500/20",
      icon: "text-blue-600",
    };
  }
  if (lower.includes("audio") || lower.includes("headphone") || lower.includes("sound") || lower.includes("electr")) {
    return {
      bg: "bg-gradient-to-br from-purple-500/15 via-pink-500/10 to-indigo-500/10",
      border: "border-purple-100 group-hover:border-purple-400 group-hover:shadow-purple-500/20",
      icon: "text-purple-600",
    };
  }
  if (lower.includes("game") || lower.includes("gaming") || lower.includes("console")) {
    return {
      bg: "bg-gradient-to-br from-emerald-500/15 via-teal-500/10 to-cyan-500/10",
      border: "border-emerald-100 group-hover:border-emerald-400 group-hover:shadow-emerald-500/20",
      icon: "text-emerald-600",
    };
  }
  if (lower.includes("phone") || lower.includes("mobile") || lower.includes("smartphone")) {
    return {
      bg: "bg-gradient-to-br from-rose-500/15 via-orange-500/10 to-amber-500/10",
      border: "border-rose-100 group-hover:border-rose-400 group-hover:shadow-rose-500/20",
      icon: "text-rose-600",
    };
  }
  if (
    lower.includes("component") ||
    lower.includes("gpu") ||
    lower.includes("cpu") ||
    lower.includes("chip")
  ) {
    return {
      bg: "bg-gradient-to-br from-cyan-500/15 via-blue-500/10 to-teal-500/10",
      border: "border-cyan-100 group-hover:border-cyan-400 group-hover:shadow-cyan-500/20",
      icon: "text-cyan-600",
    };
  }
  if (lower.includes("monitor") || lower.includes("screen") || lower.includes("display")) {
    return {
      bg: "bg-gradient-to-br from-indigo-500/15 via-blue-500/10 to-sky-500/10",
      border: "border-indigo-100 group-hover:border-indigo-400 group-hover:shadow-indigo-500/20",
      icon: "text-indigo-600",
    };
  }
  if (lower.includes("accessory") || lower.includes("watch") || lower.includes("wallet")) {
    return {
      bg: "bg-gradient-to-br from-amber-500/15 via-orange-500/10 to-yellow-500/10",
      border: "border-amber-100 group-hover:border-amber-400 group-hover:shadow-amber-500/20",
      icon: "text-amber-600",
    };
  }
  return {
    bg: "bg-gradient-to-br from-blue-500/10 via-indigo-500/10 to-cyan-500/10",
    border: "border-slate-100 group-hover:border-blue-400 group-hover:shadow-blue-500/20",
    icon: "text-blue-600",
  };
}

export default function CategoryCard({ category, image, count }: CategoryCardProps) {
  const theme = getCategoryColorTheme(category.name);

  return (
    <Link
      href={`/shop?category=${encodeURIComponent(category.name)}`}
      className="group flex flex-col focus-visible:outline-offset-4"
    >
      <span className={`relative flex aspect-square w-full items-center justify-center overflow-hidden rounded-2xl border ${theme.border} ${theme.bg} shadow-xs transition-all duration-300 group-hover:scale-[1.03] group-hover:shadow-lg`}>
        {image ? (
          <img
            src={image}
            alt=""
            onError={applyProductImageFallback}
            loading="lazy"
            width={320}
            height={320}
            className="h-full w-full object-contain p-6 transition-transform duration-500 ease-out group-hover:scale-[1.06]"
          />
        ) : (
          <span aria-hidden="true" className={theme.icon}>
            {renderCategoryIcon(category.name, 40)}
          </span>
        )}
      </span>

      <span className="mt-3 flex items-center justify-between gap-2 px-1">
        <span className="min-w-0">
          <span className="block truncate text-[15px] font-bold text-slate-900 transition-colors group-hover:text-blue-600">
            {category.name}
          </span>
          {typeof count === "number" && (
            <span className="block text-xs font-medium text-slate-500">
              {count} {count === 1 ? "product" : "products"}
            </span>
          )}
        </span>
        <ArrowRight
          size={16}
          aria-hidden="true"
          className="shrink-0 text-slate-400 transition-[transform,color] duration-200 group-hover:translate-x-1 group-hover:text-blue-600"
        />
      </span>
    </Link>
  );
}
