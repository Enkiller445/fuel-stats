import { useEffect, useState } from "react";
import type { AllData, Data } from "./types";
import { Skeleton } from "./ui";
import {
  Header,
  FuelSelector,
  Hero,
  FuelCards,
  FocusStations,
  Charts,
  BrandTables,
  Alerts,
  Footer,
} from "./sections";

export default function App() {
  const [all, setAll] = useState<AllData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [fuel, setFuel] = useState<string>("АИ-95");
  const [region, setRegion] = useState<string>("");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data.json?v=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: AllData) => {
        setAll(d);
        setRegion(d.defaultRegion || d.regions?.[0]?.slug || "");
        const f = d.regions?.[0]?.defaultFuel;
        if (f) setFuel(f);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  const regions = all?.regions ?? [];
  const data = regions.find((r) => r.slug === region) ?? regions[0];

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
      {err ? (
        <Fail msg={err} />
      ) : !all ? (
        <Loading />
      ) : (
        <>
          {regions.length > 1 && (
            <RegionTabs regions={regions} active={data?.slug ?? ""} onPick={setRegion} />
          )}
          {!data || data.empty ? <Empty /> : <Dashboard data={data} fuel={fuel} setFuel={setFuel} />}
        </>
      )}
    </div>
  );
}

function RegionTabs({
  regions,
  active,
  onPick,
}: {
  regions: Data[];
  active: string;
  onPick: (s: string) => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-1.5 rounded-xl border p-1" style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
      {regions.map((r) => {
        const on = r.slug === active;
        return (
          <button
            key={r.slug}
            onClick={() => onPick(r.slug)}
            className="rounded-lg px-3.5 py-1.5 text-sm font-semibold transition-colors"
            style={{
              background: on ? "var(--ink)" : "transparent",
              color: on ? "var(--surface)" : "var(--ink2)",
            }}
          >
            {r.short || r.name}
          </button>
        );
      })}
    </div>
  );
}

function Dashboard({ data, fuel, setFuel }: { data: Data; fuel: string; setFuel: (f: string) => void }) {
  const f = data.byFuel[fuel] ?? data.byFuel[data.defaultFuel];
  return (
    <>
      <Header d={data} />
      <FuelSelector d={data} active={fuel} onPick={setFuel} />
      <Alerts d={data} />
      <Hero d={data} f={f} />
      <FuelCards d={data} active={fuel} onPick={setFuel} />
      <FocusStations d={data} />

      <details className="mt-8 group">
        <summary
          className="cursor-pointer select-none rounded-xl border px-4 py-2.5 text-sm font-medium"
          style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--ink2)" }}
        >
          Подробности и графики (цены, тренды, бренды, гео)
        </summary>
        <div className="mt-2">
          <Charts d={data} f={f} onPickFuel={setFuel} />
          <BrandTables d={data} />
        </div>
      </details>

      <Footer d={data} />
    </>
  );
}

function Loading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-64" />
      <div className="flex gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-16" />
        ))}
      </div>
      <Skeleton className="h-32 w-full" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    </div>
  );
}

function Empty() {
  return (
    <div className="py-24 text-center" style={{ color: "var(--muted)" }}>
      <p className="text-lg font-semibold">Пока нет данных</p>
      <p className="mt-1 text-sm">Дождитесь первого сбора — дашборд наполнится автоматически.</p>
    </div>
  );
}

function Fail({ msg }: { msg: string }) {
  return (
    <div className="py-24 text-center" style={{ color: "var(--muted)" }}>
      <p className="text-lg font-semibold" style={{ color: "var(--crit)" }}>
        Не удалось загрузить данные
      </p>
      <p className="mt-1 text-sm tnum">{msg}</p>
    </div>
  );
}
