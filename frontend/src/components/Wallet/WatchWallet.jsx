/**
 * WatchWallet component.
 *
 * Allows anyone to enter any Solana wallet address and view
 * its open positions in read-only mode — no wallet connection needed.
 *
 * This is the "Watch Mode" — useful for judges, researchers,
 * or anyone wanting to inspect a specific wallet's risk profile.
 */
import { useState } from "react";

// Known Solana wallet addresses with active Marginfi/Kamino positions
// for quick testing without having to find one manually
const EXAMPLE_WALLETS = [
  {
    label: "Example — Marginfi",
    address: "GErBBMFBnBnFUuQFBhf3JF1HFVB2T5RGiUWNDe6Ap3Vo",
  },
  {
    label: "Example — Kamino",
    address: "7NHkRqmf8r9U7GuzQnRB8qVz1bX2mKGGJYQYDm7NGMKE",
  },
];

/**
 * @param {{
 *   onWatch: (address: string) => void,
 *   onClear: () => void,
 *   currentWatchedAddress: string | null
 * }} props
 */
export function WatchWallet({ onWatch, onClear, currentWatchedAddress }) {
  const [inputValue, setInputValue]   = useState("");
  const [validationError, setValidationError] = useState("");

  function handleWatch() {
    const trimmedAddress = inputValue.trim();

    // Basic Solana address validation — base58, 32-44 chars
    if (trimmedAddress.length < 32 || trimmedAddress.length > 44) {
      setValidationError("Invalid Solana address — must be 32–44 characters");
      return;
    }

    setValidationError("");
    onWatch(trimmedAddress);
  }

  function handleClear() {
    setInputValue("");
    setValidationError("");
    onClear();
  }

  function handleExampleClick(address) {
    setInputValue(address);
    setValidationError("");
    onWatch(address);
  }

  function handleKeyDown(keyboardEvent) {
    if (keyboardEvent.key === "Enter") handleWatch();
  }

  // If already watching a wallet, show the active state
  if (currentWatchedAddress) {
    return (
      <div style={activeWatchContainerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={watchingDotStyle} />
          <span style={{ color: "#60a5fa", fontSize: "11px", fontWeight: 600, letterSpacing: "1px" }}>
            WATCHING
          </span>
        </div>
        <span style={{ color: "#475569", fontSize: "11px", fontFamily: "monospace" }}>
          {currentWatchedAddress.slice(0, 6)}…{currentWatchedAddress.slice(-4)}
        </span>
        <button onClick={handleClear} style={clearButtonStyle}>✕</button>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => { setInputValue(e.target.value); setValidationError(""); }}
          onKeyDown={handleKeyDown}
          placeholder="Watch any Solana wallet…"
          style={inputStyle}
        />
        <button onClick={handleWatch} style={watchButtonStyle}>
          Watch
        </button>
      </div>

      {/* Validation error */}
      {validationError && (
        <div style={{ color: "#f87171", fontSize: "11px", marginTop: "4px" }}>
          {validationError}
        </div>
      )}

      {/* Example wallets for quick testing */}
      <div style={{ display: "flex", gap: "6px", marginTop: "6px", flexWrap: "wrap" }}>
        {EXAMPLE_WALLETS.map((exampleWallet) => (
          <button
            key={exampleWallet.address}
            onClick={() => handleExampleClick(exampleWallet.address)}
            style={exampleButtonStyle}
            title={exampleWallet.address}
          >
            {exampleWallet.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────

const containerStyle = {
  display: "flex",
  flexDirection: "column",
};

const activeWatchContainerStyle = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  background: "rgba(96,165,250,0.08)",
  border: "1px solid rgba(96,165,250,0.25)",
  borderRadius: "8px",
  padding: "6px 12px",
};

const watchingDotStyle = {
  width: "7px",
  height: "7px",
  borderRadius: "50%",
  background: "#60a5fa",
  boxShadow: "0 0 6px #60a5fa",
  animation: "pulse 2s infinite",
};

const inputStyle = {
  background: "#0f172a",
  border: "1px solid #1e293b",
  borderRadius: "8px",
  color: "#e2e8f0",
  fontSize: "12px",
  padding: "7px 12px",
  width: "240px",
  outline: "none",
  fontFamily: "monospace",
};

const watchButtonStyle = {
  background: "rgba(96,165,250,0.1)",
  border: "1px solid rgba(96,165,250,0.3)",
  borderRadius: "8px",
  color: "#60a5fa",
  fontSize: "12px",
  fontWeight: 600,
  padding: "7px 14px",
  cursor: "pointer",
  whiteSpace: "nowrap",
};

const clearButtonStyle = {
  background: "transparent",
  border: "none",
  color: "#475569",
  cursor: "pointer",
  fontSize: "14px",
  padding: "0 2px",
};

const exampleButtonStyle = {
  background: "transparent",
  border: "1px solid #1e293b",
  borderRadius: "6px",
  color: "#475569",
  fontSize: "10px",
  padding: "3px 8px",
  cursor: "pointer",
};
