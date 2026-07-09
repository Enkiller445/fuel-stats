import { useState, useRef, useEffect, type ReactNode } from "react";
import type { Level, Num } from "./types";
import { clsx, levelVar, delta as fmtDelta, deltaTone } from "./lib";

export function Card({
  children,
  className,
  accent,
  dim,
}: {
  children: ReactNode;
  className?: string;
  accent?: string;
  dim?: boolean;
}) {
  return (
    <div
      className={clsx(
        "rounded-2xl border p-4 transition-opacity",
        dim && "opacity-55",
        className
      )}
      style={{
        background: "var(--surface)",
        borderColor: accent ? accent : "var(--border)",
        borderLeftWidth: accent ? 3 : 1,
      }}
    >
      {children}
    </div>
  );
}

export function Chip({ level, children }: { level: Level; children: ReactNode }) {
  const c = levelVar(level);
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold"
      style={{ color: c, background: `color-mix(in srgb, ${c} 15%, transparent)` }}
    >
      {children}
    </span>
  );
}

export function Plaque({ label, ago, ok }: { label: string; ago: string; ok: boolean }) {
  const c = ok ? "var(--good)" : "var(--warn)";
  return (
    <div
      className="flex items-center gap-2 rounded-xl border px-3 py-1.5"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: c }} />
      <span className="text-xs" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <span className="text-xs font-medium tnum">{ago}</span>
    </div>
  );
}

export function Delta({ v, unit, goodUp }: { v: Num; unit: "rub" | "pp" | ""; goodUp: boolean }) {
  const t = fmtDelta(v, unit, unit === "rub" ? 2 : 1);
  if (!t) return null;
  return (
    <span className="text-xs font-medium tnum" style={{ color: deltaTone(v, goodUp) }}>
      {t}
    </span>
  );
}

// «?»-подсказка: клик открывает поповер с объяснением + авто-выводом
export function Help({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-block align-middle">
      <button
        onClick={() => setOpen((v) => !v)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold"
        style={{ background: "var(--line)", color: "var(--ink2)" }}
        aria-label={`Что значит: ${title}`}
      >
        ?
      </button>
      {open && (
        <span
          className="absolute right-0 z-20 mt-1 block w-64 rounded-xl border p-3 text-xs leading-relaxed shadow-lg"
          style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--ink2)" }}
        >
          <span className="mb-1 block font-semibold" style={{ color: "var(--ink)" }}>
            {title}
          </span>
          {children}
        </span>
      )}
    </span>
  );
}

// маленький «вывод по текущим данным» внутри поповера
export function Verdict({ children }: { children: ReactNode }) {
  return (
    <span className="mt-2 block border-t pt-2" style={{ borderColor: "var(--border)" }}>
      <span className="font-medium" style={{ color: "var(--ink)" }}>
        Вывод:{" "}
      </span>
      {children}
    </span>
  );
}

export function Sparkline({ vals, color, w = 96, h = 28 }: { vals: Num[]; color: string; w?: number; h?: number }) {
  const pts = vals.filter((v) => v != null) as number[];
  if (pts.length < 2) return <div style={{ width: w, height: h }} />;
  const min = Math.min(...pts),
    max = Math.max(...pts),
    rng = max - min || 1;
  const step = w / (pts.length - 1);
  const d = pts
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(h - ((v - min) / rng) * (h - 4) - 2).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={h - ((pts[pts.length - 1] - min) / rng) * (h - 4) - 2} r={2.5} fill={color} />
    </svg>
  );
}

export function SectionTitle({ children, help }: { children: ReactNode; help?: ReactNode }) {
  return (
    <h2 className="mb-3 mt-8 flex items-center text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
      {children}
      {help}
    </h2>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-xl", className)} style={{ background: "var(--line)" }} />;
}
