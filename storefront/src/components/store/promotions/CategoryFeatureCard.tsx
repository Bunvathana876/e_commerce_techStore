import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { ApiCategory } from "@/lib/api";

interface CategoryFeatureCardProps {
  category: ApiCategory;
  productCount?: number;
  highlight?: boolean;
}

export default function CategoryFeatureCard({ category, productCount = 0, highlight = false }: CategoryFeatureCardProps) {
  return (
    <Link href={`/shop?category=${encodeURIComponent(category.name)}`} className={`group flex min-h-72 flex-col justify-between border border-line bg-surface-subtle p-6 transition-colors hover:bg-line sm:p-8 ${highlight ? "md:min-h-80" : ""}`}>
      <div className="flex items-start justify-between gap-4 text-xs uppercase tracking-[0.14em] text-muted">
        <span>Department</span>
        <ArrowUpRight size={20} aria-hidden="true" className="text-ink transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
      </div>
      <div>
        <h3 className="text-2xl font-medium text-ink sm:text-3xl">{category.name}</h3>
        {category.description && <p className="mt-3 line-clamp-2 max-w-sm text-sm leading-6 text-muted">{category.description}</p>}
        <p className="mt-6 text-xs text-muted">{productCount} {productCount === 1 ? "product" : "products"}</p>
      </div>
    </Link>
  );
}
