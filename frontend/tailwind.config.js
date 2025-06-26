/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        spotify: {
          green: '#1db954',
          black: '#191414',
          gray: '#535353'
        }
      }
    },
  },
  plugins: [],
}

