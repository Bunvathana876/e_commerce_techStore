import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";
const isVercel = process.env.VERCEL === "1";
const isStrictProduction = process.env.STRICT_PRODUCTION_URLS === "true";

// Defaults for production deployments when not explicitly overridden
const DEFAULT_PROD_API_URL = "https://e-commerce-techstore-bhu7.onrender.com/api";
const DEFAULT_PROD_STOREFRONT_URL = "https://blue-panda-techstore.vercel.app";

if (isVercel || isStrictProduction) {
  const currentApi = process.env.NEXT_PUBLIC_API_URL;
  if (!currentApi || /localhost|127\.|0\.|\[::1\]/.test(currentApi) || !currentApi.startsWith("https://")) {
    process.env.NEXT_PUBLIC_API_URL = DEFAULT_PROD_API_URL;
  }
  const currentStorefront = process.env.NEXT_PUBLIC_STOREFRONT_URL;
  if (!currentStorefront || /localhost|127\.|0\.|\[::1\]/.test(currentStorefront) || !currentStorefront.startsWith("https://")) {
    process.env.NEXT_PUBLIC_STOREFRONT_URL = DEFAULT_PROD_STOREFRONT_URL;
  }
}

if (isVercel || isStrictProduction) {
  for (const key of ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_STOREFRONT_URL"]) {
    const value = process.env[key];
    if (!value) throw new Error(`${key} must be configured for production.`);
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash ||
        /^(localhost|127\.|0\.|\[::1\])/.test(url.hostname)) {
      throw new Error(`${key} must be a public HTTPS URL without credentials, query, or fragment.`);
    }
    if (key === "NEXT_PUBLIC_API_URL" && !/^\/api(?:\/v1)?\/?$/.test(url.pathname)) {
      throw new Error("NEXT_PUBLIC_API_URL must include the /api suffix (or /api/v1).");
    }
    if (key === "NEXT_PUBLIC_STOREFRONT_URL" && url.pathname !== "/") {
      throw new Error("NEXT_PUBLIC_STOREFRONT_URL must be an origin without a path.");
    }
  }
}

function getApiRemotePattern(): { protocol: "http" | "https"; hostname: string; port?: string; pathname: string } | null {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) return null;
  try {
    const parsed = new URL(apiUrl);
    const protocol = parsed.protocol.replace(":", "") as "http" | "https";
    if ((protocol === "http" || protocol === "https") && parsed.hostname) {
      if (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") return null;
      return {
        protocol,
        hostname: parsed.hostname,
        port: parsed.port || undefined,
        pathname: "/uploads/**",
      };
    }
  } catch {
    // Ignore malformed URL during build
  }
  return null;
}

const apiRemotePattern = getApiRemotePattern();

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  compress: true,
  turbopack: {},
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      ...(!isProduction ? [{
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/**",
      } as const,
      {
        protocol: "http",
        hostname: "127.0.0.1",
        port: "8000",
        pathname: "/**",
      } as const] : []),
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "placehold.co",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "ui-avatars.com",
        pathname: "/**",
      },
      ...(apiRemotePattern ? [apiRemotePattern] : []),
    ],
  },
  experimental: {
    optimizePackageImports: ["lucide-react"],
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
  async headers() {
    const apiOrigin = new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api").origin;
    const contentSecurityPolicy = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https:" + (isProduction ? "" : " http://localhost:8000 http://127.0.0.1:8000"),
      "font-src 'self'",
      `connect-src 'self' ${apiOrigin}${isProduction ? "" : " ws://localhost:* ws://127.0.0.1:*"}`,
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      ...(isProduction ? ["upgrade-insecure-requests"] : []),
    ].join("; ");
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          ...(isProduction ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }] : []),
        ],
      },
    ];
  },
  webpack(config) {
    config.module.rules.push({
      test: /\.svg$/i,
      use: ["@svgr/webpack"],
    });
    return config;
  },
};

export default nextConfig;
