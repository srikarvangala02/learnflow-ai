// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#1a1a2e',
        surface: '#16213e',
        border: '#0f3460',
        accent: '#7c3aed',
        'accent-hover': '#6d28d9',
        'text-primary': '#e0e0ff',
        'text-secondary': '#c0c0e0',
        success: '#22c55e',
        error: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
