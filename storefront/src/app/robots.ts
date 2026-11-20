import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://blue-panda-techstore.vercel.app";

  return {
    rules: [
      {
        userAgent: "*",
        allow: [
          "/",
          "/shop",
          "/categories",
          "/deals",
          "/new-arrivals",
          "/stores",
          "/product/",
        ],
        disallow: [
          "/account",
          "/account/*",
          "/checkout",
          "/checkout/*",
          "/orders",
          "/orders/*",
          "/cart",
          "/cart/*",
          "/login",
          "/register",
          "/api/",
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
