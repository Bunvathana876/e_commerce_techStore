import type { MetadataRoute } from "next";
import { fetchStoreProducts } from "@/lib/store-catalog";

export async function generateStorefrontSitemap(deps?: {
  fetchProducts?: typeof fetchStoreProducts;
}): Promise<MetadataRoute.Sitemap> {
  const siteUrl =
    process.env.NEXT_PUBLIC_SITE_URL ||
    "https://blue-panda-techstore.vercel.app";
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: `${siteUrl}`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 1.0,
    },
    {
      url: `${siteUrl}/shop`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${siteUrl}/categories`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/deals`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/new-arrivals`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/stores`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.5,
    },
  ];

  let productRoutes: MetadataRoute.Sitemap = [];
  const fetchFn = deps?.fetchProducts ?? fetchStoreProducts;
  try {
    const { products, isLiveBackend } = await fetchFn();
    if (isLiveBackend && products.length > 0) {
      productRoutes = products
        .filter(
          (p) =>
            p.is_active !== false &&
            Number.isInteger(Number(p.id)) &&
            Number(p.id) > 0
        )
        .map((p) => ({
          url: `${siteUrl}/product/${p.id}`,
          lastModified: p.updated_at ? new Date(p.updated_at) : now,
          changeFrequency: "weekly",
          priority: 0.7,
        }));
    }
  } catch {
    // Do not include fictional product URLs if backend is unavailable
    productRoutes = [];
  }

  return [...staticRoutes, ...productRoutes];
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  return generateStorefrontSitemap();
}
