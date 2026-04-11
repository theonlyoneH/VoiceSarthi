import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'VoiceForward GlassBox Copilot',
  description: 'Real-time AI copilot for crisis helpline operators — Human-first, always.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="min-h-screen bg-[#0A0B0F] text-slate-100 antialiased">
        {children}
      </body>
    </html>
  )
}
