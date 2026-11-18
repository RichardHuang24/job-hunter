import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: "*", allow: ["/", "/signin", "/privacy", "/opengraph-image"], disallow: ["/api/", "/demo/", "/jobs", "/cv", "/settings", "/applications", "/admin", "/onboarding"] } };
}
