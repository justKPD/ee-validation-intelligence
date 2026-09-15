import type { Metadata } from "next";
import { Nav } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "E/E Validation Control Tower",
  description: "Risk-based test prioritization, evidence traceability and policy-gated agentic test management (synthetic data).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <Nav />
          <main className="main">
            {children}
            <footer className="footer">
              Independent portfolio project inspired by publicly available automotive E/E validation and Agentic-AI research.
              Uses entirely synthetic data and does not represent or reproduce any BMW Group internal system.
            </footer>
          </main>
        </div>
      </body>
    </html>
  );
}
