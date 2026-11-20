import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-plus-jakarta-sans",
});

export const viewport: Viewport = {
  themeColor: "#2563eb",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "Blue Panda — Official Online Store & Marketplace",
  description:
    "Shop curated tech, sneakers, streetwear, accessories, and beauty on Blue Panda — fast delivery, verified official stores, and exclusive rewards.",
  icons: {
    icon: "/images/logo_panda_blue.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preconnect"
          href="https://images.unsplash.com"
          crossOrigin="anonymous"
        />
        <link rel="dns-prefetch" href="https://images.unsplash.com" />
      </head>
      <body
        className={`${plusJakartaSans.className} antialiased text-slate-900 selection:bg-blue-600 selection:text-white`}
      >
        {children}
      </body>
    </html>
  );
}
