import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

const backendUrl = process.env.NEXT_PUBLIC_API_URL;
if (!backendUrl) {
  throw new Error("NEXT_PUBLIC_API_URL must be set when building the frontend.");
}

const backendOrigin = new URL(backendUrl).origin;

nextConfig.rewrites = async () => ({
  beforeFiles: [
    { source: "/", destination: "/homepage.html" },
    { source: "/category/:slug", destination: "/category.html" },
    { source: "/restaurant/:restaurantId", destination: "/restaurant.html" },
    { source: "/restaurant/:restaurantId/", destination: "/restaurant.html" },
    { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
    { source: "/media/:path*", destination: `${backendOrigin}/media/:path*` },
    { source: "/certificate.html", destination: `${backendOrigin}/certificate.html` },
    {
      source: "/certificate_verification.html",
      destination: `${backendOrigin}/certificate_verification.html`,
    },
  ],
});

export default nextConfig;
