import type { ApiProduct } from "@/lib/api";
import ProductCard from "@/components/store/ProductCard";
import ProductSkeleton from "@/components/store/ProductSkeleton";

interface ProductGridProps {
  products?: ApiProduct[];
  isLoading?: boolean;
  skeletonCount?: number;
  layout?: "grid" | "list";
  /** Desktop column count. 4 for full-width rows, 3 beside a filter sidebar. */
  columns?: 3 | 4;
  editorial?: boolean;
}

// Two columns from the smallest phone up: the standard for product browsing.
const GRID_COLUMNS: Record<3 | 4, string> = {
  3: "grid grid-cols-2 gap-x-4 gap-y-10 sm:gap-x-6 xl:grid-cols-3",
  4: "grid grid-cols-2 gap-x-4 gap-y-10 sm:gap-x-6 md:grid-cols-3 lg:grid-cols-4",
};

export default function ProductGrid({
  products = [],
  isLoading = false,
  skeletonCount = 8,
  layout = "grid",
  columns = 4,
  editorial = false,
}: ProductGridProps) {
  if (isLoading) {
    if (layout === "list") {
      return (
        <div className="space-y-4" aria-busy="true" aria-label="Loading products">
          {Array.from({ length: skeletonCount }).map((_, index) => (
            <ProductSkeleton key={index} layout="list" />
          ))}
        </div>
      );
    }

    return (
      <div className={GRID_COLUMNS[columns]} aria-busy="true" aria-label="Loading products">
        {Array.from({ length: skeletonCount }).map((_, index) => (
          <ProductSkeleton key={index} layout="grid" />
        ))}
      </div>
    );
  }

  if (layout === "list") {
    return (
      <div className="space-y-4">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} layout="list" />
        ))}
      </div>
    );
  }

  return (
    <div className={`${GRID_COLUMNS[columns]} ${editorial && products.length >= 3 ? "[&>article:first-child]:md:col-span-2 [&>article:first-child>div:first-child]:md:aspect-[2/1]" : ""}`}>
      {products.map((product) => (
        <ProductCard key={product.id} product={product} layout="grid" />
      ))}
    </div>
  );
}
