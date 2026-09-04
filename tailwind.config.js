/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./static/**/*.html', './static/**/*.js'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: { smart: { 50:'#ecfdf5', 100:'#d1fae5', 500:'#10b981', 600:'#059669', 700:'#047857', 950:'#052e2b' } },
      fontFamily: { sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'] },
      borderRadius: { 'sw': '1.25rem' },
      boxShadow: { 'sw': '0 18px 55px rgba(5,46,43,.14)' },
      transitionTimingFunction: { 'sw': 'cubic-bezier(.22,1,.36,1)' }
    }
  },
  plugins: []
};
