interface ProductSkeletonProps {
  className?: string;
  layout?: "grid" | "list";
}

// Mirrors ProductCard's proportions so content lands without layout shift.
export default function ProductSkeleton({
  className = "",
  layout = "grid",
}: ProductSkeletonProps) {
  if (layout === "list") {
    return (
      <div
        aria-hidden="true"
        className={`flex animate-pulse flex-col gap-5 border-b border-line pb-6 sm:flex-row ${className}`}
      >
        <div className="aspect-square w-full shrink-0 bg-surface-subtle sm:h-48 sm:w-48" />
        <div className="flex flex-1 flex-col justify-between gap-3">
          <div className="space-y-2.5">
            <div className="h-3 w-24 rounded bg-surface-subtle" />
            <div className="h-5 w-3/4 rounded bg-surface-subtle" />
            <div className="h-3 w-1/2 rounded bg-surface-subtle" />
          </div>
          <div className="flex items-center justify-between border-t border-line pt-4">
            <div className="h-6 w-24 rounded bg-surface-subtle" />
            <div className="h-11 w-32 rounded-xl bg-surface-subtle" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div aria-hidden="true" className={`flex animate-pulse flex-col ${className}`}>
      <div className="aspect-square w-full bg-surface-subtle" />
      <div className="space-y-2 px-1 pt-4">
        <div className="h-3 w-16 rounded bg-surface-subtle" />
        <div className="h-4 w-full rounded bg-surface-subtle" />
        <div className="h-4 w-2/3 rounded bg-surface-subtle" />
        <div className="h-5 w-20 rounded bg-surface-subtle pt-2" />
      </div>
    </div>
  );
}
