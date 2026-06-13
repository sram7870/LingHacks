export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F7F5F0",
        surface: "#FFFFFF",
        surfaceAlt: "#F2EFE9",
        border: "#E0DDD6",
        borderDark: "#C8C4BC",
        ink: "#1A1814",
        inkSec: "#6B6760",
        inkTer: "#9E9B96",
        green: "#2D6A4F",
        greenLight: "#D8EDDF",
        greenMid: "#52B788",
        amber: "#B5600A",
        amberLight: "#FDEFD3",
        red: "#C0392B",
        redLight: "#FDECEA",
        blue: "#1B4F8A",
        blueLight: "#DDEAF8",
      },
      fontFamily: {
        playfair: ["Playfair Display", "serif"],
        lato: ["Lato", "sans-serif"],
        dmmono: ["DM Mono", "monospace"],
      },
      boxShadow: {
        panel: "0 4px 20px rgba(0, 0, 0, 0.08)",
      },
    },
  },
  plugins: [],
};
