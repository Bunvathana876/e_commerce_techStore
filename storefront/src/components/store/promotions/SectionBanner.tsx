import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface SectionBannerProps {
  badge?: string;
  title: string;
  description?: string;
  ctaText?: string;
  ctaHref?: string;
  stats?: Array<{ label: string; value: string | number }>;
  theme?: "navy" | "blue" | "subtle";
}

export default function SectionBanner({
  badge,
  title,
  description,
  ctaText,
  ctaHref,
  stats,
  theme = "navy",
}: SectionBannerProps) {
  if (theme === "subtle") {
    return (
      <div className="rounded-3xl bg-slate-50 border border-slate-200/80 p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-5">
        <div>
          {badge && (
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#245BE7] block mb-1">
              {badge}
            </span>
          )}
          <h3 className="text-lg sm:text-xl font-semibold text-[#181818] tracking-tight">
            {title}
          </h3>
          {description && (
            <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-xl leading-relaxed">
              {description}
            </p>
          )}
        </div>

        {ctaText && ctaHref && (
          <Link
            href={ctaHref}
            className="px-6 py-3 rounded-2xl bg-[#181818] hover:bg-[#245BE7] text-white text-xs font-semibold transition shrink-0 inline-flex items-center gap-2 shadow-xs"
          >
            <span>{ctaText}</span>
            <ArrowRight size={14} />
          </Link>
        )}
      </div>
    );
  }

  const bgClasses = theme === "blue" ? "bg-brand" : "bg-ink";

  return (
    <section
      className={`relative overflow-hidden rounded-4xl ${bgClasses} p-7 text-white sm:p-10`}
    >

      <div className="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="max-w-2xl">
          {badge && (
            <p className="bp-eyebrow mb-2 text-sky">{badge}</p>
          )}
          <h2 className="text-2xl sm:text-4xl font-semibold tracking-tight text-white leading-tight">
            {title}
          </h2>
          {description && (
            <p className="text-sm sm:text-base text-blue-100/90 mt-2 max-w-xl leading-relaxed">
              {description}
            </p>
          )}

          {stats && stats.length > 0 && (
            <div className="flex flex-wrap items-center gap-2.5 mt-5">
              {stats.map((s) => (
                <span
                  key={s.label}
                  className="px-3 py-1 rounded-full bg-white/15 text-blue-100 border border-white/20 backdrop-blur-xs text-xs font-bold"
                >
                  {s.value} {s.label}
                </span>
              ))}
            </div>
          )}
        </div>

        {ctaText && ctaHref && (
          <Link
            href={ctaHref}
            className="px-6 py-3.5 rounded-2xl bg-white hover:bg-blue-50 text-[#181818] text-xs font-semibold transition shrink-0 inline-flex items-center gap-2 shadow-lg shadow-black/10 hover:scale-[1.02] active:scale-[0.98]"
          >
            <span>{ctaText}</span>
            <ArrowRight size={14} className="text-[#245BE7]" />
          </Link>
        )}
      </div>
    </section>
  );
}
