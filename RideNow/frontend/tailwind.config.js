/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f6f6f6',
          100: '#e7e7e7',
          200: '#d1d1d1',
          300: '#b0b0b0',
          400: '#888888',
          500: '#6d6d6d',
          600: '#5d5d5d',
          700: '#4f4f4f',
          800: '#1E293B',
          900: '#0F172A',
          950: '#05070A', // Deep black background
        },
        dark: {
          bg: '#05070A',
          card: '#0A0F14',
          cardHover: '#0D141B',
          cardBorder: '#1E293B',
          panel: '#101820',
          panelBorder: '#1A232E',
        },
        cyan: {
          400: '#38BDF8',
          500: '#0EA5E9',
          600: '#0284C7',
          DEFAULT: '#38BDF8',
          glow: '#5CC8FF',
        },
        accent: {
          DEFAULT: '#38BDF8', // Electric Cyan
          hover: '#0EA5E9',
          glow: 'rgba(56, 189, 248, 0.25)',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.4)',
        'float': '0 10px 30px -10px rgba(0, 0, 0, 0.5)',
        'up': '0 -4px 10px -2px rgba(0, 0, 0, 0.3)',
        'glow-cyan': '0 0 20px -2px rgba(56, 189, 248, 0.3)',
        'glow-green': '0 0 15px -2px rgba(16, 185, 129, 0.3)',
      },
      animation: {
        'progress': 'progress 2s ease-in-out infinite',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        progress: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        }
      }
    },
  },
  plugins: [],
}
