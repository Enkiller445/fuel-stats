// «Вывод по текущим данным» для подсказок «?» — короткие пороговые формулировки.
import type { Fuel, Overall, Num } from "./types";

export function vWork(o: Overall): string {
  const v = o.workPp;
  if (v == null) return "Пока нет данных.";
  const base =
    v >= 90 ? "почти все точки отпускают топливо — рынок спокоен."
    : v >= 75 ? "большинство точек работают, но не все — лёгкая напряжённость."
    : v >= 55 ? "заметная доля точек стоит без топлива — дефицит ощутим."
    : "работает меньше половины — острый дефицит.";
  return `${Math.round(v)}% АЗС с этим топливом — ${base}`;
}

export function vGdBal(o: Overall): string {
  const v = o.gdBal;
  if (v == null) return "Пока нет данных.";
  return `${Math.round(v)}% сообщений — «топливо есть». Это оценка снизу по краудсорсу gdebenz, а не точная доступность: про пустые АЗС пишут чаще.`;
}

export function vBestHour(h: number | null): string {
  if (h == null) return "Пока мало наблюдений по часам.";
  return `Больше всего работающих АЗС наблюдалось около ${String(h).padStart(2, "0")}:00. Это по полной базе petrolplus, не по отметкам пользователей.`;
}

export function vBestDay(d: string | null): string {
  if (!d) return "Пока мало дней наблюдений.";
  return `В среднем больше работающих АЗС в ${d.toLowerCase()}. По мере накопления данных вывод уточнится.`;
}

export function vSpread(f: Fuel): string {
  const s = f.spread;
  if (s == null) return "Пока нет пары сети/независимые.";
  if (s <= 0.5) return `Разницы почти нет (${s.toFixed(2)} ₽). Рынок сбалансирован.`;
  return `Независимые дороже сетей на ${s.toFixed(2)} ₽ — это направление напряжённости (кто «ловит» дефицит), а не абсолютная переплата.`;
}

export function vPrice(f: Fuel): string {
  if (f.price == null) return "Пока нет свежих цен.";
  if (!f.priceReliable)
    return `Свежих цен всего ${f.fresh ?? 0} — медиана ${f.price.toFixed(2)} ₽ собрана с горстки (часто дорогих) АЗС и не отражает рынок. Ориентируйтесь на цены крупных сетей.`;
  const d = f.price_d7;
  const t =
    d == null ? "динамику за неделю посчитаем позже."
    : Math.abs(d) < 0.05 ? "за неделю практически без изменений."
    : d > 0 ? `за неделю +${d.toFixed(2)} ₽.` : `за неделю ${d.toFixed(2)} ₽.`;
  return `Медиана свежих цен. ${t}`;
}

export function vFuelAvail(f: Fuel): string {
  if (f.work_pct == null || f.n == null) return "Пока нет данных.";
  const rare = f.share_all != null && f.share_all < 25
    ? ` Это лишь ${f.share_all}% всех АЗС — марку держат немногие, «${f.work_pct}%» не значит «легко найти».`
    : "";
  return `Марку продают на ${f.n} АЗС, из них реально отпускают сейчас ${f.work_pct}% (${f.navail}).${rare}`;
}

export function vShare(f: Fuel, total: Num): string {
  if (f.n == null || total == null) return "Пока нет данных.";
  return `${f.n} из ${total} АЗС региона держат в прайсе ${f.grade} (${f.share_all}%). Редкие марки (98/100) есть не везде — отсюда меньше данных.`;
}
