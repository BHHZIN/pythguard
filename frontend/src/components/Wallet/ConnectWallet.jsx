/**
 * ConnectWallet component.
 *
 * Renders the wallet connection button and shows the truncated
 * wallet address once connected. Supports Phantom and Solflare
 * via @solana/wallet-adapter-react.
 */
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";

/**
 * Truncates a Solana wallet address for display.
 * e.g. "4zMMC9...Hbp6" from a 44-char base58 address
 *
 * @param {string} walletAddress
 * @returns {string}
 */
function truncateWalletAddress(walletAddress) {
  if (walletAddress.length <= 12) return walletAddress;
  return `${walletAddress.slice(0, 6)}…${walletAddress.slice(-4)}`;
}

/**
 * @param {{ onWalletConnected: (address: string) => void }} props
 */
export function ConnectWallet({ onWalletConnected }) {
  const { publicKey, connected } = useWallet();

  // Notify parent when wallet connects
  if (connected && publicKey) {
    onWalletConnected(publicKey.toBase58());
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
      {connected && publicKey && (
        <span style={{
          color: "#94a3b8",
          fontSize: "13px",
          fontFamily: "monospace",
          background: "#1e293b",
          padding: "4px 10px",
          borderRadius: "6px",
        }}>
          {truncateWalletAddress(publicKey.toBase58())}
        </span>
      )}
      <WalletMultiButton style={{
        background: connected ? "#1e293b" : "#6366f1",
        border: "1px solid #334155",
        borderRadius: "8px",
        fontSize: "14px",
        fontWeight: 600,
        padding: "8px 16px",
        cursor: "pointer",
        transition: "background 0.2s ease",
      }} />
    </div>
  );
}
