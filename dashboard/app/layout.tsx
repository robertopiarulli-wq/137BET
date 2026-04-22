export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="it">
      <head>
        {/* Caricamento rapido di Tailwind CSS via CDN */}
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body className="bg-[#0f172a] text-white antialiased min-h-screen">
        {children}
      </body>
    </html>
  )
}
