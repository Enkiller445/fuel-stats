import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import type { Num } from "./types";
import { enough } from "./lib";

const AXIS = { fontSize: 11, fill: "var(--muted)" };
const GRID = "var(--line)";
const tickNum = (v: number) =>
  Number(v).toLocaleString("ru-RU", { maximumFractionDigits: 2 });

function Empty({ h }: { h: number }) {
  return (
    <div className="flex items-center justify-center text-xs" style={{ height: h, color: "var(--muted)" }}>
      Недостаточно данных для графика
    </div>
  );
}

function Box({ label, rows }: { label: string; rows: { name: string; val: string; color: string }[] }) {
  return (
    <div
      className="rounded-lg border px-2.5 py-1.5 text-xs shadow-md"
      style={{ background: "var(--surface)", borderColor: "var(--border)" }}
    >
      <div className="mb-1 font-medium" style={{ color: "var(--muted)" }}>
        {label}
      </div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />
          <span style={{ color: "var(--ink2)" }}>{r.name}</span>
          <span className="ml-auto font-semibold tnum" style={{ color: "var(--ink)" }}>
            {r.val}
          </span>
        </div>
      ))}
    </div>
  );
}

export interface Series {
  key: string;
  name: string;
  vals: Num[];
  color: string;
  dashed?: boolean;
}

export function LineTrend({
  labels,
  series,
  height = 220,
  unit = "",
  domain = ["auto", "auto"] as [any, any],
}: {
  labels: string[];
  series: Series[];
  height?: number;
  unit?: string;
  domain?: [any, any];
}) {
  const anyData = series.some((s) => enough(s.vals));
  if (!anyData) return <Empty h={height} />;
  const data = labels.map((x, i) => {
    const row: any = { x };
    series.forEach((s) => (row[s.key] = s.vals[i] ?? null));
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -4 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="x" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52} domain={domain} tickFormatter={tickNum} />
        <Tooltip
          cursor={{ stroke: "var(--muted)", strokeDasharray: "3 3" }}
          content={({ active, payload, label }) =>
            active && payload && payload.length ? (
              <Box
                label={String(label)}
                rows={payload.map((p: any) => ({
                  name: series.find((s) => s.key === p.dataKey)?.name ?? p.dataKey,
                  val: p.value == null ? "—" : `${Number(p.value).toLocaleString("ru-RU")}${unit}`,
                  color: p.color,
                }))}
              />
            ) : null
          }
        />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            stroke={s.color}
            strokeWidth={2.25}
            strokeDasharray={s.dashed ? "5 4" : undefined}
            dot={false}
            activeDot={{ r: 3.5, strokeWidth: 0 }}
            connectNulls
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function StatusStack({
  labels,
  yes,
  queue,
  low,
  no,
  height = 200,
}: {
  labels: string[];
  yes: Num[];
  queue: Num[];
  low: Num[];
  no: Num[];
  height?: number;
}) {
  if (![yes, no].some((v) => enough(v))) return <Empty h={height} />;
  const data = labels.map((x, i) => ({
    x,
    yes: yes[i] ?? null,
    queue: queue[i] ?? null,
    low: low[i] ?? null,
    no: no[i] ?? null,
  }));
  const S = [
    { key: "yes", name: "Есть", color: "var(--good)" },
    { key: "queue", name: "Очередь", color: "var(--warn)" },
    { key: "low", name: "Мало/лимит", color: "var(--serious)" },
    { key: "no", name: "Нет", color: "var(--crit)" },
  ];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="x" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip
          content={({ active, payload, label }) =>
            active && payload && payload.length ? (
              <Box
                label={String(label)}
                rows={[...payload].reverse().map((p: any) => ({
                  name: S.find((s) => s.key === p.dataKey)?.name ?? p.dataKey,
                  val: p.value == null ? "—" : Number(p.value).toLocaleString("ru-RU"),
                  color: p.color,
                }))}
              />
            ) : null
          }
        />
        {S.map((s) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            stackId="1"
            stroke={s.color}
            fill={s.color}
            fillOpacity={0.22}
            strokeWidth={1.5}
            connectNulls
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function Bars({
  labels,
  vals,
  color,
  highlight,
  unit = "",
  height = 180,
}: {
  labels: string[];
  vals: Num[];
  color: string;
  highlight?: number | null;
  unit?: string;
  height?: number;
}) {
  if (!enough(vals, 3)) return <Empty h={height} />;
  const nums = vals.filter((v) => v != null) as number[];
  const min = Math.min(...nums);
  const data = labels.map((x, i) => ({ x, y: vals[i] ?? null, i }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="x" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval={0} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={44} domain={[Math.floor(min * 0.98), "auto"]} />
        <Tooltip
          cursor={{ fill: "color-mix(in srgb, var(--muted) 12%, transparent)" }}
          content={({ active, payload, label }) =>
            active && payload && payload.length ? (
              <Box
                label={String(label)}
                rows={[{ name: "Значение", val: `${Number(payload[0].value).toLocaleString("ru-RU")}${unit}`, color }]}
              />
            ) : null
          }
        />
        <Bar dataKey="y" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {data.map((d) => (
            <Cell
              key={d.x}
              fill={color}
              fillOpacity={highlight != null && d.i === highlight ? 1 : 0.45}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SpreadChart({
  labels,
  net,
  indep,
  height = 200,
  netColor,
}: {
  labels: string[];
  net: Num[];
  indep: Num[];
  height?: number;
  netColor: string;
}) {
  if (![net, indep].some((v) => enough(v))) return <Empty h={height} />;
  return (
    <LineTrend
      labels={labels}
      height={height}
      unit=" ₽"
      series={[
        { key: "net", name: "Сети", vals: net, color: netColor },
        { key: "indep", name: "Независимые", vals: indep, color: "var(--muted)", dashed: true },
      ]}
    />
  );
}

export { ReferenceLine };
