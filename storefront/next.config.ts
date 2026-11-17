import type { NextConfig } from "next";

const isVercel = process.env.VERCEL === "1";
const isStrictProduction = process.env.STRICT_PRODUCTION_URLS === "true";

// Defaults for production deployments when not explicitly overridden
const DEFAULT_PROD_API_URL = "https://blue-panda-api-demo.onrender.com/api";
const DEFAULT_PROD_MANAGEMENT_URL = "https://blue-panda-management.vercel.app";

if (isVercel || isStrictProduction) {
  const currentApi = process.env.NEXT_PUBLIC_API_URL;
  if (!currentApi || /localhost|127\.|0\.|\[::1\]/.test(currentApi) || !currentApi.startsWith("https://")) {
    process.env.NEXT_PUBLIC_API_URL = DEFAULT_PROD_API_URL;
  }
  const currentManagement = process.env.NEXT_PUBLIC_MANAGEMENT_URL;
  if (!currentManagement || /localhost|127\.|0\.|\[::1\]/.test(currentManagement) || !currentManagement.startsWith("https://")) {
    process.env.NEXT_PUBLIC_MANAGEMENT_URL = DEFAULT_PROD_MANAGEMENT_URL;
  }
}

if (isVercel || isStrictProduction) {
  for (const key of ["NEXT_PUBLIC_API_URL", "NEXT_PUBLIC_MANAGEMENT_URL"]) {
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
    if (key === "NEXT_PUBLIC_MANAGEMENT_URL" && url.pathname !== "/") {
      throw new Error("NEXT_PUBLIC_MANAGEMENT_URL must be an origin without a path.");
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
        pathname: "/**",
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
  turbopack: {},
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/**",
      },
      {
        protocol: "http",
        hostname: "127.0.0.1",
        port: "8000",
        pathname: "/**",
      },
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
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
  webpack(config) {
    config.module.rules.push({
      test: /\.svg$/i,
      use: [{ loader: require.resolve("./scripts/svg-loader.mjs") }],
    });
    return config;
  },
};

export default nextConfig;
