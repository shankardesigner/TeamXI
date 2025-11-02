import { useEffect, useMemo } from "react";

export default function ConfettiOverlay({ duration = 4200, onComplete }) {
  const dots = useMemo(() => {
    const palette = [0, 18, 45, 122, 180, 210, 255, 300, 330];
    const count = 620;
    return Array.from({ length: count }, () => {
      const radius = 22 + Math.random() * 95;
      const angle = Math.random() * Math.PI * 2;
      const dx = Math.cos(angle) * radius;
      const dy = Math.sin(angle) * radius;
      const fall = 88 + Math.random() * 52;
      const midFactor = 0.58 + Math.random() * 0.18;
      const size = 3 + Math.random() * 5;
      const hue = palette[Math.floor(Math.random() * palette.length)];
      return {
        dxMid: dx * midFactor,
        dyMid: dy * midFactor * 0.85,
        dxEnd: dx,
        dyFall: dy + fall,
        size,
        color: `hsla(${hue}, 78%, ${52 + Math.random() * 16}%, ${
          0.82 + Math.random() * 0.15
        })`,
        delay: Math.random() * 0.22,
        duration: 1.4 + Math.random() * 0.7,
        blur: Math.random() * 1.2,
        glow: 6 + Math.random() * 12,
      };
    });
  }, []);

  useEffect(() => {
    if (!onComplete) {
      return undefined;
    }
    const timer = setTimeout(() => onComplete(), Math.max(duration - 900, 0));
    return () => clearTimeout(timer);
  }, [duration, onComplete]);

  return (
    <div className="confetti-overlay" aria-hidden="true">
      {dots.map((dot, idx) => (
        <span
          key={idx}
          className="confetti-dot"
          style={{
            "--dx-mid": `${dot.dxMid}vw`,
            "--dy-mid": `${dot.dyMid}vh`,
            "--dx-end": `${dot.dxEnd}vw`,
            "--dy-fall": `${dot.dyFall}vh`,
            "--animation-duration": `${dot.duration}s`,
            "--animation-delay": `${dot.delay}s`,
            width: `${dot.size}px`,
            height: `${dot.size}px`,
            backgroundColor: dot.color,
            filter: `blur(${dot.blur}px)`,
            boxShadow: `0 0 ${dot.glow}px ${dot.color}`,
          }}
        />
      ))}
    </div>
  );
}
