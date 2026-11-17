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

export default function CategoryCard({ category, image, count }: CategoryCardProps) {
  return (
    <Link
      href={`/shop?category=${encodeURIComponent(category.name)}`}
      className="group flex flex-col focus-visible:outline-offset-4"
    >
      <span className="relative flex aspect-square w-full items-center justify-center overflow-hidden bg-surface-subtle transition-colors duration-300 group-hover:bg-line">
        {image ? (
          <img
            src={image}
            alt=""
            onError={applyProductImageFallback}
            loading="lazy"
            width={320}
            height={320}
            className="h-full w-full object-contain p-6 transition-transform duration-500 ease-out group-hover:scale-[1.03]"
          />
        ) : (
          <span aria-hidden="true" className="text-brand">
            {renderCategoryIcon(category.name, 36)}
          </span>
        )}
      </span>

      <span className="mt-3 flex items-center justify-between gap-2 px-1">
        <span className="min-w-0">
          <span className="block truncate text-[15px] font-semibold text-ink">
            {category.name}
          </span>
          {typeof count === "number" && (
            <span className="block text-xs text-muted">
              {count} {count === 1 ? "product" : "products"}
            </span>
          )}
        </span>
        <ArrowRight
          size={16}
          aria-hidden="true"
          className="shrink-0 text-muted transition-[transform,color] duration-200 group-hover:translate-x-0.5 group-hover:text-brand"
        />
      </span>
    </Link>
  );
}
