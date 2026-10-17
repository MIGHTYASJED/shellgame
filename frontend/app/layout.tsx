import type { Metadata, Viewport } from "next";
import "@fontsource-variable/newsreader/opsz.css";
import "@fontsource-variable/newsreader/opsz-italic.css";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shell Game",
  description: "Trace a counterparty through offshore ownership to sanctions exposure, with the graph path as proof.",
};
export const viewport: Viewport = { themeColor: "#F7F6F2" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh flex flex-col">{children}</body>
    </html>
  );
}
