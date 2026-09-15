"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/dashboard", "Control Tower"],
  ["/risk", "Risk & Coverage"],
  ["/planner", "Agentic Test Planner"],
  ["/shadow", "Shadow Planning"],
  ["/failures", "Failure Intelligence"],
  ["/provenance", "Provenance Ledger"],
  ["/reliability", "Agent Reliability Lab"],
  ["/admin", "Admin & Policy"],
] as const;

export function Nav() {
  const path = usePathname();
  return (
    <nav className="nav" aria-label="Main">
      <h1>E/E Validation Intelligence</h1>
      <p className="sub">Agentic Test Control Tower</p>
      {LINKS.map(([href, text]) => (
        <Link key={href} href={href} aria-current={path?.startsWith(href) ? "page" : undefined}>
          {text}
        </Link>
      ))}
    </nav>
  );
}
