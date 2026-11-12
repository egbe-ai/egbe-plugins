import type { Metadata } from "next";
import { EgbeAnalytics } from "@/components/egbe-analytics";
import "./globals.css";

export const metadata: Metadata = {
  title: "Product",
  description: "Product homepage",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {children}
        <EgbeAnalytics />
      </body>
    </html>
  );
}
