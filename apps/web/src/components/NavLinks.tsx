"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Pages join this list as their features move in (docs/roadmap.md).
const LINKS = [
  { href: "/", label: "Dashboard", wide: true }, // on phones the logo is the way home
  { href: "/jobs", label: "Jobs" },
  { href: "/applications", label: "Applications" },
  { href: "/cv", label: "CV" },
  { href: "/settings", label: "Settings" },
];

export default function NavLinks({ admin = false }: { admin?: boolean }) {
  const pathname = usePathname();
  const links = admin ? [...LINKS, { href: "/admin", label: "Admin" }] : LINKS;
  return (
    <nav aria-label="Main" className="flex min-w-0 gap-0.5 overflow-x-auto text-sm [scrollbar-width:none]">
      {links.map((link) => {
        const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`shrink-0 rounded-lg px-2 py-1.5 whitespace-nowrap transition-colors sm:px-3 ${"wide" in link ? "hidden sm:block" : ""} ${
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
