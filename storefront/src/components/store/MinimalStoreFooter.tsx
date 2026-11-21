"use client";

import Link from "next/link";
import Image from "next/image";
import { FREE_SHIPPING_THRESHOLD, STANDARD_SHIPPING_FEE } from "@/lib/store";

const SHOP_LINKS = [
  { href: "/shop", label: "All products" },
  { href: "/categories", label: "Categories" },
  { href: "/new-arrivals", label: "New arrivals" },
  { href: "/deals", label: "Deals and promo codes" },
];

const ACCOUNT_LINKS = [
  { href: "/account", label: "Your account" },
  { href: "/orders", label: "Orders and receipts" },
  { href: "/wishlist", label: "Wishlist" },
  { href: "/cart", label: "Shopping bag" },
];

function FooterColumn({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string }[];
}) {
  return (
    <nav aria-label={title}>
      <h2 className="font-sans text-sm font-semibold tracking-normal text-ink">{title}</h2>
      <ul className="mt-4 space-y-1">
        {links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              className="inline-flex min-h-9 items-center text-sm text-muted transition-colors hover:text-ink"
            >
              <span className="bp-link">{link.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default function MinimalStoreFooter() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="mt-(--section-gap) border-t border-line bg-white text-ink">
      <div className="bp-container grid gap-12 py-16 sm:py-20 md:grid-cols-2 lg:grid-cols-12">
        {/* Brand */}
        <div className="lg:col-span-5">
          <Link
            href="/"
            className="inline-flex items-center gap-3"
            aria-label="Blue Panda home"
          >
            <Image
              src="/images/logo_panda_blue.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 object-contain"
            />
            <span className="font-display text-2xl font-semibold tracking-tight">Blue Panda</span>
          </Link>
          <p className="mt-5 max-w-sm text-[15px] leading-7 text-muted">
            Considered technology for everyday life. Explore the live Blue Panda collection.
          </p>
        </div>

        <div className="lg:col-span-2">
          <FooterColumn title="Shop" links={SHOP_LINKS} />
        </div>
        <div className="lg:col-span-2">
          <FooterColumn title="Account" links={ACCOUNT_LINKS} />
        </div>

        {/* Delivery & payment facts */}
        <div className="md:col-span-2 lg:col-span-3">
          <h2 className="font-sans text-sm font-semibold tracking-normal text-ink">
            Delivery
          </h2>
          <dl className="mt-4 space-y-4 text-sm leading-6">
            <div>
              <dt className="text-ink">Shipping rates</dt>
              <dd className="text-muted">
                Free over ${FREE_SHIPPING_THRESHOLD}, otherwise ${STANDARD_SHIPPING_FEE} flat.
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="bp-container flex flex-col gap-2 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>© {currentYear} Blue Panda Technology Store</p>
          <p>Prices in USD. Stock levels update live from the catalog.</p>
        </div>
      </div>
    </footer>
  );
}
