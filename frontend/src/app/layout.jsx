import "./globals.css";

export const metadata = {
  title: "Cafe Assistant",
  description: "Chat-based cafe experience",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

// Root layout providing HTML skeleton and responsive viewport wrapper
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
