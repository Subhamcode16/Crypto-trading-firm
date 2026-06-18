/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./App.{js,jsx,ts,tsx}", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        'radioactive-green': '#39FF14',
        'burns-red': '#FF0000',
      },
      fontFamily: {
        comic: ['"Comic Sans MS"', 'Chalkboard SE', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
