// The browser only ever talks to this site: every /api/* request is proxied to the FastAPI service. That keeps the
// demo working on any address the site is served from (production alias, preview or per-deployment URL) and on
// networks that block the API's own domain, with no cross-origin requests at all.
// NEXT_PUBLIC_API_URL is the proxy target, read at build time (Vercel: the Railway API URL; Docker: http://api:8000).
const API_TARGET = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_TARGET}/:path*` }];
  },
};

export default nextConfig;
