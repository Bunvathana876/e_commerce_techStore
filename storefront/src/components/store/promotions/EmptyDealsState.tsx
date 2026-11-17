import Link from "next/link";
import { Compass, Zap } from "lucide-react";

interface EmptyDealsStateProps {
  title?: string;
  description?: string;
  ctaText?: string;
  ctaHref?: string;
}

export default function EmptyDealsState({
  title = "No Promotions Currently Active",
  description = "All products in the store are currently offered at standard verified pricing. Check back soon for upcoming promotional events.",
  ctaText = "Explore Full Catalog",
  ctaHref = "/shop",
}: EmptyDealsStateProps) {
  return (
    <div className="rounded-3xl border border-slate-200/80 bg-white p-10 sm:p-14 text-center shadow-xs">
      <div className="w-14 h-14 rounded-2xl bg-blue-50 text-[#245BE7] flex items-center justify-center mx-auto mb-3 shadow-2xs">
        <Zap size={24} />
      </div>
      <h3 className="text-xl font-semibold text-[#181818] tracking-tight">
        {title}
      </h3>
      <p className="text-xs sm:text-sm text-slate-500 mt-1.5 max-w-md mx-auto leading-relaxed">
        {description}
      </p>
      <Link
        href={ctaHref}
        className="mt-6 inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-[#181818] hover:bg-[#245BE7] text-white text-xs font-semibold transition shadow-sm hover:scale-[1.02] active:scale-[0.98]"
      >
        <Compass size={16} /> {ctaText}
      </Link>
    </div>
  );
}
