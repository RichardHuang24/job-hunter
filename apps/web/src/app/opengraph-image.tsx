import { ImageResponse } from "next/og";

export const alt = "Job Hunter — enter a target role, explore matches and build your own CV. Public project demo.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", background: "#f6f5f1", color: "#242724", padding: "52px 64px", display: "flex", flexDirection: "column", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><div style={{ fontSize: 30, fontWeight: 700 }}>JH / Job Hunter</div><div style={{ fontSize: 18, border: "1px solid #b7c7b8", padding: "10px 18px", borderRadius: 30, color: "#376344" }}>INTERACTIVE PROJECT</div></div>
      <div style={{ display: "flex", flexDirection: "column", marginTop: 42, fontSize: 66, lineHeight: 1.1, fontWeight: 700, letterSpacing: -3 }}><span>Your next role.</span><span style={{ color: "#73766f" }}>Your own workspace.</span></div>
      <div style={{ display: "flex", marginTop: 34, gap: 16 }}>
        {["01  Enter a role", "02  Explore & track", "03  Build your CV"].map((text) => <div key={text} style={{ display: "flex", flex: 1, padding: "24px 22px", background: "#ffffff", border: "1px solid #deded5", borderRadius: 14, fontSize: 23 }}>{text}</div>)}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "auto", borderTop: "1px solid #deded5", paddingTop: 22, fontSize: 17, color: "#73766f" }}><span>Sample jobs · Simulated scores · Your own blank CV</span><span>Python + Next.js</span></div>
    </div>, size,
  );
}
