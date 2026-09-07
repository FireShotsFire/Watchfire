import "./globals.css";
import React from "react";

export const metadata = {
  title: "Watchfire | Sanctions & Compliance Screening",
  description: "Multi-jurisdictional compliance watchlisting and risk aggregator",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-900 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
