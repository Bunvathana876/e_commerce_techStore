import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  /** Small factual line under the description, e.g. live counts. */
  meta?: ReactNode;
  /** Right-hand slot on desktop: a search field or an action. */
  aside?: ReactNode;
  className?: string;
}

/**
 * Editorial page header shared by catalog pages (shop, deals, new arrivals,
 * categories). Flat page background, display headline, one supporting line —
 * replaces the gradient + glow banners each page used to carry.
 */
export default function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  aside,
  className = "",
}: PageHeaderProps) {
  return (
    <header
      className={`flex flex-col gap-6 border-b border-line pb-8 sm:pb-10 lg:flex-row lg:items-end lg:justify-between ${className}`}
    >
      <div className="max-w-2xl">
        {eyebrow && <p className="bp-eyebrow">{eyebrow}</p>}
        <h1 className="mt-3 text-4xl font-medium leading-[1.08] text-ink sm:text-5xl lg:text-[3.5rem]">
          {title}
        </h1>
        {description && (
          <p className="mt-4 max-w-xl text-base leading-7 text-muted">{description}</p>
        )}
        {meta && <div className="mt-4 text-sm font-medium text-ink-soft">{meta}</div>}
      </div>
      {aside && <div className="w-full shrink-0 lg:w-96">{aside}</div>}
    </header>
  );
}
