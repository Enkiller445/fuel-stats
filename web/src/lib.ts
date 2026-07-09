import type { Level, Num } from "./types";

// --- форматирование чисел ---
const nf1 = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf0 = new Intl.NumberFormat("ru-RU");

export const rub = (v: Num) => (v == null ? "—" : `${nf1.format(v)} ₽`);
export const pct = (v: Num) => (v == null ? "—" : `${Math.round(v)}%`);
export const int = (v: Num) => (v == null ? "—" : nf0.format(Math.round(v)));

// знаковая дельта: «+0,12 ₽» / «−1,4 п.п.» / «0»
export function delta(v: Num, unit: "rub" | "pp" | "", digits = 2): string {
  if (v == null) return "";
  const a = Math.abs(v);
  if (a < (digits === 2 ? 0.005 : 0.05)) return "0";
  const sign = v > 0 ? "+" : "−";
  const num =
    digits === 2 ? nf1.format(a) : new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(a);
  const u = unit === "rub" ? " ₽" : unit === "pp" ? " п.п." : "";
  return `${sign}${num}${u}`;
}

// цвет знака дельты (рост цены — плохо, рост доступности — хорошо)
export function deltaTone(v: Num, goodWhenUp: boolean): string {
  if (v == null || Math.abs(v) < 0.005) return "var(--muted)";
  const up = v > 0;
  return up === goodWhenUp ? "var(--good)" : "var(--crit)";
}

// --- цвета ---
export const fuelVar = (token: string) => `var(--${token})`;

const LEVEL_VAR: Record<Level, string> = {
  good: "var(--good)",
  warn: "var(--warn)",
  serious: "var(--serious)",
  crit: "var(--crit)",
};
export const levelVar = (l: Level) => LEVEL_VAR[l];

export const LEVEL_LABEL: Record<Level, string> = {
  good: "спокойно",
  warn: "напряжённо",
  serious: "дефицит",
  crit: "острый дефицит",
};

// «5 мин / м» серии для Recharts: [{x, y}]
export function toXY(labels: string[], vals: Num[]) {
  return labels.map((x, i) => ({ x, y: vals[i] ?? null }));
}

// есть ли достаточно точек, чтобы что-то рисовать
export const enough = (vals: Num[], n = 2) => vals.filter((v) => v != null).length >= n;

export const clsx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");
