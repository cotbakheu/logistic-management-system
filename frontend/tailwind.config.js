/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: { 
        sans: ['"Plus Jakarta Sans"', 'sans-serif'] 
      },
      colors: {
        navy: '#1E3A8A',
        amber: '#F59E0B',
        success: '#10B981',
        danger: '#EF4444'
      }
    },
  },
  plugins: [],
}