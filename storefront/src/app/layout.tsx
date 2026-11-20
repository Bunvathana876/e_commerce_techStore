import type { Metadata } from "next";
import { Bricolage_Grotesque, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

// Body and UI text: the existing Blue Panda face.
const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-body",
});

// Display face for page and section headings: a grotesque with optical
// sizing, so large headlines tighten up and small ones stay open.
const bricolageGrotesque = Bricolage_Grotesque({
  subsets: ["latin"],
  axes: ["opsz"],
  display: "swap",
  variable: "--font-heading",
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://blue-panda-techstore.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Blue Panda — Premium Technology & PC Store",
    template: "%s | Blue Panda",
  },
  description:
    "Discover modern laptops, PC components, gaming gear, studio audio, and everyday tech essentials on Blue Panda — fast delivery, genuine warranty, and reliable support.",
  keywords: [
    "technology store",
    "PC components",
    "gaming laptops",
    "mechanical keyboards",
    "high-performance hardware",
    "Blue Panda",
    "electronics",
  ],
  authors: [{ name: "Blue Panda Retail" }],
  creator: "Blue Panda",
  publisher: "Blue Panda",
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: siteUrl,
    siteName: "Blue Panda",
    title: "Blue Panda — Premium Technology & PC Store",
    description:
      "Modern laptops, PC components, gaming gear, studio audio, and tech essentials with verified quality and express delivery.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Blue Panda — Premium Technology & PC Store",
    description:
      "Modern laptops, PC components, gaming gear, studio audio, and tech essentials with verified quality and express delivery.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${plusJakartaSans.variable} ${bricolageGrotesque.variable}`}>
      <body className="font-sans antialiased text-ink">
        {children}
      </body>
    </html>
  );
}
