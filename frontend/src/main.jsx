import React from "react";
import ReactDOM from "react-dom/client";
import App from "./pages/index.jsx";

// Global reset — dark background, no default margins
const globalStyleElement = document.createElement("style");
globalStyleElement.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #020817; color: #e2e8f0; }
  a { text-decoration: none; }
`;
document.head.appendChild(globalStyleElement);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
