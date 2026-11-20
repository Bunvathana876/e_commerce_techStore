export default function StoreLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-12 animate-pulse">
      {/* Hero / Banner Skeleton */}
      <div className="h-72 sm:h-96 w-full rounded-[2rem] bg-slate-200/80" />

      {/* Trust Pillars Skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 rounded-3xl bg-slate-100" />
        ))}
      </div>

      {/* Catalog Grid Skeleton */}
      <div className="space-y-4">
        <div className="h-8 w-48 rounded-xl bg-slate-200" />
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div
              key={i}
              className="rounded-3xl border border-slate-200/80 bg-white p-4 space-y-4"
            >
              <div className="aspect-square w-full rounded-2xl bg-slate-100" />
              <div className="h-4 w-3/4 rounded bg-slate-200" />
              <div className="h-4 w-1/2 rounded bg-slate-100" />
              <div className="h-8 w-full rounded-xl bg-slate-100" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
