/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0B0F2E',
          light: '#131947',
          dark: '#050718',
          glass: 'rgba(11, 15, 46, 0.75)',
        },
        gold: {
          DEFAULT: '#C9A84C',
          light: '#DBC075',
          dark: '#B09033',
          glow: 'rgba(201, 168, 76, 0.3)',
        }
      },
      fontFamily: {
        outfit: ['Outfit', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
