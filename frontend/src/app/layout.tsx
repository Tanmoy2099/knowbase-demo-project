import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Knowbase",
  description: "AI-powered personal knowledge base",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-950 text-gray-100 antialiased">
        <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur">
          <div className="mx-auto max-w-7xl px-4 py-3 flex items-center gap-3">
            <span className="text-xl font-bold text-blue-400">Knowbase</span>
            <span className="text-xs text-gray-500 mt-0.5">AI-powered knowledge base</span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
