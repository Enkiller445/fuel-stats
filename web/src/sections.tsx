import type { ReactNode } from "react";
import type { Data, Fuel } from "./types";
import { rub, pct, int, fuelVar, LEVEL_LABEL, clsx, plural, ageText } from "./lib";
import { Card, Chip, Plaque, Delta, Help, Verdict, Sparkline, SectionTitle } from "./ui";
import { LineTrend, StatusStack, Bars, SpreadChart } from "./charts";
import * as V from "./verdicts";

// ---------------------------------------------------------------- Header
export function Header({ d }: { d: Data }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Бензин · {d.region || "Москва"}
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          Наблюдаем {d.monitoringDays}{" "}
          {plural(d.monitoringDays, "день", "дня", "дней")} · {int(d.measurements)} замеров ·
          обновляется ежечасно
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Plaque label="Цены" ago={d.fresh.pricesAgo} ok={d.fresh.pricesOk} />
        <Plaque label="Наличие" ago={d.fresh.gdAgo} ok={d.fresh.gdOk} />
      </div>
    </header>
  );
}

// -------------------------------------------------------- Fuel selector
export function FuelSelector({
  d,
  active,
  onPick,
}: {
  d: Data;
  active: string;
  onPick: (f: string) => void;
}) {
  return (
    <div className="mt-5 flex flex-wrap gap-2">
      {d.fuels.map((name) => {
        const f = d.byFuel[name];
        const c = fuelVar(f.color);
        const on = name === active;
        return (
          <button
            key={name}
            onClick={() => onPick(name)}
            className={clsx(
              "rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-colors",
              f.low && "opacity-70"
            )}
            style={{
              color: on ? "#fff" : c,
              background: on ? c : "transparent",
              borderColor: c,
            }}
          >
            {name}
            {f.low && <span className="ml-1 text-[10px] font-normal opacity-80">мало</span>}
          </button>
        );
      })}
    </div>
  );
}

// -------------------------------------------------------- Assistant panel
export function Assistant({ f }: { f: Fuel }) {
  const c = fuelVar(f.color);
  const s = f.summary;
  return (
    <Card className="mt-4" accent={c}>
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold" style={{ color: c }}>
          {f.grade === "ДТ" ? "ДТ" : `АИ-${f.grade}`}
        </span>
        <Chip level={s.level}>{LEVEL_LABEL[s.level]}</Chip>
      </div>
      {!f.priceReliable && (
        <p className="mt-2 rounded-lg px-3 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--warn) 14%, transparent)", color: "var(--ink2)" }}>
          ⚠ <b>Цена ненадёжна.</b>{" "}
          {f.priceSuspect
            ? `медиана ${rub(f.price)} выше более высокооктанового топлива — так не бывает, значит свежих цен мало (${int(f.fresh)}) и они с дорогих единичных АЗС. Не ориентир рынка.`
            : `свежих цен всего ${int(f.fresh)} — медиана ${rub(f.price)} собрана с горстки точек, не отражает рынок.`}
        </p>
      )}
      <p className="mt-2 text-base leading-snug" style={{ color: "var(--ink)" }}>
        {s.state}
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            Чего ждать
          </div>
          <p className="text-sm" style={{ color: "var(--ink2)" }}>
            {s.trend}
          </p>
          {s.baroText && (
            <div className="mt-2">
              <Chip level={s.baroLevel}>
                {s.baroArrow} {s.baroText}
              </Chip>
            </div>
          )}
        </div>
        <div>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            Что делать
          </div>
          <p className="text-sm" style={{ color: "var(--ink2)" }}>
            {s.action}
          </p>
        </div>
      </div>
    </Card>
  );
}

// ----------------------------------------------------------------- KPI row
function Kpi({
  label,
  help,
  value,
  sub,
  right,
}: {
  label: string;
  help?: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-center text-xs" style={{ color: "var(--muted)" }}>
        {label}
        {help}
      </div>
      <div className="mt-1 flex items-end justify-between gap-2">
        <div>
          <div className="text-2xl font-bold tnum">{value}</div>
          {sub && <div className="mt-0.5 text-xs">{sub}</div>}
        </div>
        {right}
      </div>
    </Card>
  );
}

function Meter({ v, color }: { v: number; color: string }) {
  return (
    <div className="h-2 w-24 overflow-hidden rounded-full" style={{ background: "var(--line)" }}>
      <div className="h-full rounded-full" style={{ width: `${Math.max(3, Math.min(100, v))}%`, background: color }} />
    </div>
  );
}

export function KpiRow({ d, f }: { d: Data; f: Fuel }) {
  const c = fuelVar(f.color);
  const tot = d.overall.azsTotal;
  const age = ageText(f.age, d.freshDays);
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label={`Цена ${f.grade === "ДТ" ? "ДТ" : "АИ-" + f.grade}`}
        help={<Help title="Цена — медиана свежих цен"><Verdict>{V.vPrice(f)}</Verdict></Help>}
        value={
          f.priceReliable ? (
            rub(f.price)
          ) : (
            <span style={{ color: "var(--muted)" }}>≈{rub(f.price)}</span>
          )
        }
        sub={
          f.priceReliable ? (
            <span className="flex items-center gap-2">
              <Delta v={f.price_d1} unit="rub" goodUp={false} />
              <span style={{ color: age.stale ? "var(--warn)" : "var(--muted)" }}>· {age.text}</span>
            </span>
          ) : (
            <span style={{ color: "var(--warn)" }}>ненадёжно · {int(f.fresh)} свежих цен</span>
          )
        }
        right={f.priceReliable ? <Sparkline vals={f.series.price} color={c} /> : undefined}
      />
      <Kpi
        label="Работают сейчас"
        help={<Help title="Работающих АЗС по марке">% — среди тех, кто продаёт марку. Но саму марку держат не все АЗС: смотрите абсолют «из скольких всего».<Verdict>{V.vFuelAvail(f)}</Verdict></Help>}
        value={f.work_pct == null ? "—" : pct(f.work_pct)}
        sub={
          <span style={{ color: "var(--muted)" }}>
            продают на {int(f.n)} из {int(tot)}
            {f.share_all != null && <span style={{ color: f.share_all < 25 ? "var(--serious)" : "var(--muted)" }}> · {f.share_all}% всех</span>}
          </span>
        }
        right={f.work_pct != null ? <Meter v={f.work_pct} color={c} /> : undefined}
      />
      <Kpi
        label="Спред сети−независимые"
        help={<Help title="Разница цен">Насколько независимые АЗС дороже сетевых — направление напряжённости, не абсолют.<Verdict>{V.vSpread(f)}</Verdict></Help>}
        value={
          !f.priceReliable || f.spread == null ? (
            <span style={{ color: "var(--muted)" }}>—</span>
          ) : (
            `${f.spread.toFixed(2)} ₽`
          )
        }
        sub={
          !f.priceReliable || f.spread == null ? (
            <span style={{ color: "var(--muted)" }}>мало данных</span>
          ) : (
            <Delta v={f.spread_d7} unit="rub" goodUp={false} />
          )
        }
        right={f.priceReliable && f.spread != null ? <Sparkline vals={f.series.spread} color={c} /> : undefined}
      />
      <Kpi
        label="gdebenz: «есть»"
        help={<Help title="Сообщений «есть»">Сколько АЗС по краудсорсу gdebenz сейчас отмечены как «топливо есть» (вкл. очередь/лимит). Оценка снизу — про пустые пишут чаще.<Verdict>{V.vShare(f, tot)}</Verdict></Help>}
        value={int(f.now)}
        sub={
          f.diverge ? (
            <span style={{ color: "var(--warn)" }}>но свежих цен {int(f.fresh)} — расходится</span>
          ) : (
            <span style={{ color: "var(--muted)" }}>{f.share_all != null ? `в прайсе у ${f.share_all}% АЗС` : ""}</span>
          )
        }
        right={<Sparkline vals={f.series.now} color={c} />}
      />
    </div>
  );
}

// --------------------------------------------------------------- Fuel cards
export function FuelCards({ d, active, onPick }: { d: Data; active: string; onPick: (f: string) => void }) {
  const tot = d.overall.azsTotal;
  return (
    <>
      <SectionTitle>Все марки</SectionTitle>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {d.fuels.map((name) => {
          const f = d.byFuel[name];
          const c = fuelVar(f.color);
          const on = name === active;
          const age = ageText(f.age, d.freshDays);
          return (
            <button key={name} onClick={() => onPick(name)} className="text-left">
              <Card accent={on ? c : undefined} dim={!f.priceReliable} className={clsx(on && "ring-2")}>
                <div className="flex items-center justify-between">
                  <span className="font-bold" style={{ color: c }}>
                    {name}
                  </span>
                  {!f.priceReliable ? (
                    <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: "color-mix(in srgb, var(--warn) 20%, transparent)", color: "var(--warn)" }}>
                      ЦЕНА НЕНАДЁЖНА
                    </span>
                  ) : (
                    <Chip level={f.summary.level}>{LEVEL_LABEL[f.summary.level]}</Chip>
                  )}
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl font-bold tnum" style={{ color: f.priceReliable ? "var(--ink)" : "var(--muted)" }}>
                    {f.priceReliable ? rub(f.price) : `≈${rub(f.price)}`}
                  </span>
                  <span className="text-[11px]" style={{ color: age.stale ? "var(--warn)" : "var(--muted)" }}>
                    {f.priceReliable ? age.text : `по ${int(f.fresh)} ценам`}
                  </span>
                </div>
                <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  Продают на {int(f.n)} из {int(tot)}
                  {f.share_all != null && (
                    <b style={{ color: f.share_all < 25 ? "var(--serious)" : "var(--ink2)" }}> · {f.share_all}% всех</b>
                  )}
                </div>
                <div className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
                  Работают {pct(f.work_pct)} · gdebenz {int(f.now)} «есть»
                </div>
                {f.diverge && (
                  <div className="mt-1 text-xs leading-snug" style={{ color: "var(--warn)" }}>
                    ⚠ gdebenz: {int(f.now)} «есть», а свежих цен {int(f.fresh)} — наличие вида под вопросом
                  </div>
                )}
              </Card>
            </button>
          );
        })}
      </div>
    </>
  );
}

// ------------------------------------------------------------------- Charts
export function Charts({ d, f }: { d: Data; f: Fuel }) {
  const c = fuelVar(f.color);
  const grade = f.grade === "ДТ" ? "ДТ" : "АИ-" + f.grade;
  const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
  const bestDayIdx = d.bestDay ? d.weekdays.indexOf(d.bestDay) : null;
  return (
    <>
      <SectionTitle help={<Help title="Цена — медиана">{V.vPrice(f)}</Help>}>Цена {grade}</SectionTitle>
      <Card>
        <LineTrend labels={d.days} unit=" ₽" series={[{ key: "p", name: grade, vals: f.series.price, color: c }]} />
      </Card>

      <SectionTitle
        help={
          <Help title="Две честные метрики доступности">
            «Работающих АЗС %» — по полной базе petrolplus, честная доступность. «Баланс сообщений» — по краудсорсу
            gdebenz, оценка снизу (про пустые пишут чаще), не доступность.
          </Help>
        }
      >
        Доступность (все марки)
      </SectionTitle>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <Capt help={<Help title="Работающих АЗС, %"><Verdict>{V.vWork(d.overall)}</Verdict></Help>}>
            Работающих АЗС, % · petrolplus
          </Capt>
          <LineTrend labels={d.days} unit="%" domain={[0, 100]} series={[{ key: "w", name: "Работают", vals: d.series.workPp, color: "var(--good)" }]} />
        </Card>
        <Card>
          <Capt help={<Help title="Баланс сообщений «есть», %"><Verdict>{V.vGdBal(d.overall)}</Verdict></Help>}>
            Баланс сообщений «есть», % · gdebenz (оценка снизу)
          </Capt>
          <LineTrend labels={d.days} unit="%" domain={[0, 100]} series={[{ key: "g", name: "«Есть»", vals: d.series.gdBal, color: "var(--muted)", dashed: true }]} />
        </Card>
      </div>

      <GeoCard d={d} />

      <SectionTitle>Сообщения gdebenz по статусам</SectionTitle>
      <Card>
        <StatusStack labels={d.days} yes={d.series.status.yes} queue={d.series.status.queue} low={d.series.status.low} no={d.series.status.no} />
      </Card>

      <SectionTitle help={<Help title="Спред">{V.vSpread(f)}</Help>}>Цены сетей и независимых · {grade}</SectionTitle>
      <Card>
        <SpreadChart labels={d.days} net={f.series.net} indep={f.series.indep} netColor={c} />
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        <div>
          <SectionTitle help={<Help title="Лучший час"><Verdict>{V.vBestHour(d.bestHour)}</Verdict></Help>}>Когда больше работающих АЗС</SectionTitle>
          <Card>
            <Bars labels={hours} vals={d.hourAvail} color="var(--good)" highlight={d.bestHour} />
          </Card>
        </div>
        <div>
          <SectionTitle help={<Help title="Лучший день"><Verdict>{V.vBestDay(d.bestDay)}</Verdict></Help>}>По дням недели</SectionTitle>
          <Card>
            <Bars labels={d.weekdays} vals={d.weekdayAvail} color="var(--good)" highlight={bestDayIdx} />
          </Card>
        </div>
      </div>
    </>
  );
}

function GeoCard({ d }: { d: Data }) {
  const g = d.geo;
  if (!g || (!g.in.resp && !g.out.resp)) return null;
  const rows = [
    { label: "Внутри МКАД", s: g.in },
    { label: "За МКАД (область)", s: g.out },
  ];
  const diff = g.in.pct != null && g.out.pct != null ? g.in.pct - g.out.pct : null;
  return (
    <>
      <SectionTitle
        help={
          <Help title="Москва ↔ область">
            Доля АЗС с сообщением «есть» (вкл. очередь/лимит) отдельно внутри МКАД и за ним — по координатам gdebenz.
            {diff != null && (
              <Verdict>
                {Math.abs(diff) < 4
                  ? "Сейчас разницы между городом и областью почти нет."
                  : diff > 0
                    ? `Внутри МКАД наличие на ${Math.abs(diff)} п.п. лучше, чем в области.`
                    : `В области наличие на ${Math.abs(diff)} п.п. лучше, чем внутри МКАД.`}
              </Verdict>
            )}
          </Help>
        }
      >
        Наличие: город ↔ область
      </SectionTitle>
      <Card>
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((r) => (
            <div key={r.label}>
              <div className="flex items-baseline justify-between">
                <span className="text-sm" style={{ color: "var(--ink2)" }}>{r.label}</span>
                <span className="text-lg font-bold tnum">{r.s.pct != null ? `${r.s.pct}%` : "—"}</span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--line)" }}>
                <div className="h-full rounded-full" style={{ width: `${r.s.pct ?? 0}%`, background: "var(--good)" }} />
              </div>
              <div className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                {r.s.yes} «есть» из {r.s.resp} ответивших
              </div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function Capt({ children, help }: { children: ReactNode; help?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center text-xs font-medium" style={{ color: "var(--muted)" }}>
      {children}
      {help}
    </div>
  );
}

// ------------------------------------------------------------- Brand tables
export function BrandTables({ d }: { d: Data }) {
  if (!d.brandsPrice.length && !d.brandsGd.length) return null;
  const dimKind = (k: string) => k !== "petrol";
  return (
    <>
      <SectionTitle
        help={
          <Help title="Две разные базы АЗС">
            Слева — petrolplus (цены), справа — gdebenz (наличие, краудсорс). Это <b>разные наборы</b> АЗС:
            число точек по одной сети не совпадает, поэтому построчно сети между таблицами не сравнивайте.
            Газовые АЗС (АГЗС/пропан) и нераспознанные бренды вынесены отдельными строками, чтобы не искажать бензиновые сети.
          </Help>
        }
      >
        По брендам
      </SectionTitle>
      <div className="grid gap-3 lg:grid-cols-2">
        {d.brandsPrice.length > 0 && (
          <Card>
            <Capt>Медианы цен по бензиновым сетям, ₽ · petrolplus</Capt>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--muted)" }}>
                    <th className="pb-1 text-left font-medium">Сеть</th>
                    {d.fuels.map((f) => (
                      <th key={f} className="pb-1 text-right font-medium" style={{ color: fuelVar(d.byFuel[f].color) }}>
                        {f.replace("АИ-", "")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.brandsPrice.map((b) => (
                    <tr key={b.brand} className="border-t" style={{ borderColor: "var(--border)", opacity: dimKind(b.kind) ? 0.6 : 1 }}>
                      <td className="py-1">{b.brand} <span style={{ color: "var(--muted)" }}>· {b.n}</span></td>
                      {d.fuels.map((f) => (
                        <td key={f} className="py-1 text-right tnum">
                          {b.prices[f] != null ? b.prices[f]!.toFixed(2) : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>
              Газовые АЗС исключены (их цены — не бензин). 98/100 по сетям — мало точек, значения ориентировочные.
            </div>
          </Card>
        )}
        {d.brandsGd.length > 0 && (
          <Card>
            <Capt help={<Help title="Есть %">Считается как «есть» ÷ «ответившие» (есть+нет+очередь+лимит). Точки без данных в знаменатель НЕ идут — иначе процент занижается. Рядом — сколько АЗС ответили из скольких.</Help>}>
              Наличие по сетям · gdebenz
            </Capt>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--muted)" }}>
                    <th className="pb-1 text-left font-medium">Сеть</th>
                    <th className="pb-1 text-right font-medium">Есть %</th>
                    <th className="pb-1 text-right font-medium">Ответили</th>
                    {d.fuels.map((f) => (
                      <th key={f} className="pb-1 text-right font-medium" style={{ color: fuelVar(d.byFuel[f].color) }}>
                        {f.replace("АИ-", "")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.brandsGd.map((b) => (
                    <tr key={b.brand} className="border-t" style={{ borderColor: "var(--border)", opacity: dimKind(b.kind) ? 0.6 : 1 }}>
                      <td className="py-1">{b.brand}</td>
                      <td className="py-1 text-right font-semibold tnum" style={{ color: availColor(b.availPct) }}>
                        {b.availPct != null ? `${b.availPct}%` : "—"}
                      </td>
                      <td className="py-1 text-right tnum" style={{ color: "var(--muted)" }}>
                        {b.resp}/{b.n}
                      </td>
                      {d.fuels.map((f) => (
                        <td key={f} className="py-1 text-right tnum">
                          {b.byFuel[d.byFuel[f].grade] ?? 0}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>
              «Ответили N/M» — у части точек статус неизвестен; их исключаем из «Есть %».
            </div>
          </Card>
        )}
      </div>
    </>
  );
}

function availColor(pct: number | null): string {
  if (pct == null) return "var(--muted)";
  if (pct >= 80) return "var(--good)";
  if (pct >= 60) return "var(--warn)";
  if (pct >= 40) return "var(--serious)";
  return "var(--crit)";
}

// -------------------------------------------------------------- Alerts + Footer
export function Alerts({ d }: { d: Data }) {
  if (!d.alerts.length) return null;
  return (
    <Card className="mt-6" accent="var(--crit)">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--crit)" }}>
        Внимание
      </div>
      <ul className="list-disc pl-5 text-sm" style={{ color: "var(--ink2)" }}>
        {d.alerts.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
    </Card>
  );
}

export function Footer({ d }: { d: Data }) {
  return (
    <footer className="mt-10 border-t pt-4 text-xs leading-relaxed" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
      <p>
        Источники: petrolplus.ru (цены и наличие по полной базе) и gdebenz.ru (краудсорс наличия). «Свежими» считаются
        цены не старше {d.freshDays} дней. Данные — оценка ситуации, не гарантия наличия конкретного топлива на
        конкретной АЗС.
      </p>
      {d.generatedMsk && <p className="mt-1">Обновлено: {d.generatedMsk} МСК.</p>}
    </footer>
  );
}

