import { useEffect, useState } from "react";
import type { Data } from "./types";
import { Skeleton } from "./ui";
import {
  Header,
  FuelSelector,
  Hero,
  FuelCards,
  Charts,
  BrandTables,
  Alerts,
  Footer,
} from "./sections";

export default function App() {
  const [data, setData] = useState<Data | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [fuel, setFuel] = useState<string>("АИ-95");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data.json?v=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: Data) => {
        setData(d);
        if (d.defaultFuel) setFuel(d.defaultFuel);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
      {err ? (
        <Fail msg={err} />
      ) : !data ? (
        <Loading />
      ) : data.empty ? (
        <Empty />
      ) : (
        <Dashboard data={data} fuel={fuel} setFuel={setFuel} />
      )}
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

      <details className="mt-8 group">
        <summary
          className="cursor-pointer select-none rounded-xl border px-4 py-2.5 text-sm font-medium"
          style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--ink2)" }}
        >
          Подробности и графики (цены, тренды, бренды, гео)
        </summary>
        <div className="mt-2">
          <Charts d={data} f={f} />
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
