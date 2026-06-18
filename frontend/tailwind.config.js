/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'springfield-bg': '#1a1a2e',
        'springfield-yellow': '#FFD90F',
        'radioactive-green': '#39FF14',
        'mapple-silver': '#E5E5E5',
        'burns-red': '#FF3B30',
        'lisa-blue': '#007AFF'
      },
      fontFamily: {
        'comic': ['Impact', 'Arial Black', 'sans-serif'],
        'mono': ['VT323', 'monospace']
      },
      boxShadow: {
        'comic': '8px 8px 0px 0px rgba(0,0,0,1)',
        'comic-sm': '4px 4px 0px 0px rgba(0,0,0,1)',
      }
    },
  },
  plugins: [],
}

