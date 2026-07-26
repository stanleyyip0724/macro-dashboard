import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "US Macroeconomic Health Dashboard",
  description:
    "Business cycle phase, composite risk index, and systemic alerts built from FRED data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
