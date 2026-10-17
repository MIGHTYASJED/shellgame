"use client";
import { useEffect, useRef } from "react";

/** Guilloche rosette (hypotrochoid layers) drawn once per size; rotation is pure CSS. */
function rosette(cv: HTMLCanvasElement, R: number, r: number, layers: number, ink: string, alpha: number) {
  const S = cv.clientWidth;
  if (!S) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = cv.height = Math.round(S * dpr);
  const c = cv.getContext("2d")!;
  c.setTransform(dpr, 0, 0, dpr, (S / 2) * dpr, (S / 2) * dpr);
  const gcd = (a: number, b: number): number => (b ? gcd(b, a % b) : a);
  const g = gcd(R, r), T = (2 * Math.PI * r) / g, k = (R - r) / r, lobes = R / g, sc = (S / 2 - 2) / R, steps = Math.ceil(T * 40);
  c.lineWidth = 0.55;
  for (let i = 0; i < layers; i++) {
    const f = i / layers, d = r * (0.35 + 0.65 * f), rot = (f * 2 * Math.PI) / lobes, cr = Math.cos(rot), sr = Math.sin(rot);
    c.strokeStyle = `rgba(${ink},${alpha * (0.4 + 0.6 * Math.sin(f * Math.PI))})`;
    c.beginPath();
    for (let j = 0; j <= steps; j++) {
      const t = (j / steps) * T;
      const x = (R - r) * Math.cos(t) + d * Math.cos(k * t), y = (R - r) * Math.sin(t) - d * Math.sin(k * t);
      const X = (x * cr - y * sr) * sc, Y = (x * sr + y * cr) * sc;
      j ? c.lineTo(X, Y) : c.moveTo(X, Y);
    }
    c.stroke();
  }
}

export function Seal({ className = "" }: { className?: string }) {
  const a = useRef<HTMLCanvasElement>(null);
  const b = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const draw = () => {
      if (a.current) rosette(a.current, 120, 33, 16, "31,74,55", 0.17);
      if (b.current) rosette(b.current, 96, 28, 12, "168,138,78", 0.2);
    };
    draw();
    const ro = new ResizeObserver(draw);
    if (a.current) ro.observe(a.current);
    return () => ro.disconnect();
  }, []);
  return (
    <div aria-hidden className={`pointer-events-none aspect-square ${className}`}>
      <canvas ref={a} className="spin-slow absolute inset-0 w-full h-full" />
      <canvas ref={b} className="spin-slower absolute inset-[10%] w-[80%] h-[80%]" />
    </div>
  );
}
