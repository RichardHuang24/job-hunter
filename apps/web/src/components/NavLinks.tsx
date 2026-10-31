"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Pages join this list as their features move in (docs/roadmap.md).
const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/settings", label: "Settings" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex min-w-0 gap-0.5 text-sm">
      {LINKS.map((link) => {
        const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-lg px-2.5 py-1.5 transition-colors sm:px-3 ${
              active ? "bg-ink/[0.07] font-medium text-ink" : "text-ink-secondary hover:bg-ink/[0.04] hover:text-ink"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
