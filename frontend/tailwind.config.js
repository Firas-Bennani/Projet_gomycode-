/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        industrial: {
          bg: "#080d1a",
          card: "#0f172a",
          border: "#1e293b",
          cyan: "#00f0ff",
          blue: "#38bdf8",
          accent: "#2563eb",
          critical: "#ef4444",
          warning: "#f59e0b",
          success: "#10b981",
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 240, 255, 0.25)',
        'glow-red': '0 0 20px rgba(239, 68, 68, 0.35)',
        'glow-amber': '0 0 20px rgba(245, 158, 11, 0.35)',
      }
    },
  },
  plugins: [],
}
