import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import Nav from "@/components/Nav";
import { demoMode } from "@/lib/demo";

// Where this copy's source code is. Change it if you run a modified version.
const SOURCE_URL = process.env.SOURCE_URL || "https://github.com/RichardHuang24/job-hunter";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Job Hunter",
  description: "Start with your target role. Explore opportunities, track applications and build your own CV in an independent demo workspace.",
  metadataBase: new URL(process.env.AUTH_URL || "http://localhost:3420"),
  openGraph: { title: "Job Hunter — Your next role. Your own workspace.", description: "Enter a job title to explore the interactive project. Your CV starts blank. Sample jobs, simulated scores and independent visitor workspaces.", type: "website", url: "/", siteName: "Job Hunter" },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        {demoMode() && (
          <p className="bg-foreground px-4 py-2 text-center text-sm text-background">
            Public demo · Fictional sample jobs · Simulated scores · Independent workspaces expire after {Number(process.env.DEMO_ACCOUNT_HOURS || 24)} hours.{" "}
            <a href={SOURCE_URL} className="underline underline-offset-2">
              Run your own
            </a>
          </p>
        )}
        <Nav />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
        <footer className="border-t border-hairline">
          <div className="mx-auto flex max-w-6xl flex-wrap gap-x-5 gap-y-1 px-4 py-5 text-sm text-ink-muted sm:px-6">
            <Link href="/privacy" className="hover:text-ink">
              Privacy
            </Link>
            {/* AGPL-3.0, section 13: everyone using this over the network can get its source. */}
            <a href={SOURCE_URL} className="hover:text-ink">
              Source code (AGPL-3.0)
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
