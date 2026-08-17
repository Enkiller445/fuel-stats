// Форма web/public/data.json (его пишет export_json.py)

export type Level = "good" | "warn" | "serious" | "crit";
export type Num = number | null;

// светофор доступности
export type TrafficLevel = "green" | "yellow" | "red" | "gray";

// «Когда заправляться»: профиль + автопроверка воспроизводимости
export interface WhenProfile {
  labels: string[];
  values: number[]; // шанс застать топливо, %
  best: string;
  worst: string;
  spread: number; // размах, п.п.
  noise: number; // собственный шум, п.п.
  reliability: number | null; // корреляция профилей 1-й и 2-й половины истории
  trust: boolean; // можно ли советовать время
}

export interface Forecast {
  typical: Num; // медианное изменение за сутки, п.п.
  band: Num; // p90 суточных изменений — честный коридор
  text: string;
}

export interface Verdict {
  word: string; // «Есть почти везде» / «Есть не на каждой» / «Редко» / «Наличие не подтверждено»
  action: string;
  trendLabel: string;
  confBadge: string;
  trendState: string; // накопление | up | down | stable
}

export interface Summary {
  level: Level;
  state: string;
  trend: string;
  action: string;
  baroLevel: Level;
  baroText: string;
  baroArrow: string;
}

export interface FuelSeries {
  price: Num[];
  now: Num[];
  spread: Num[];
  net: Num[];
  indep: Num[];
}

export interface Fuel {
  grade: string;
  color: string; // токен: f92 | f95 | f98 | f100 | fdt
  price: Num;
  price_d1: Num;
  price_d7: Num;
  n: Num;
  fresh: Num;
  navail: Num;
  now: Num;
  age: Num; // медианный возраст цен, дней
  // --- trust-first (ведущие) ---
  availShare: Num; // navail / все АЗС, % — ВЕРХНЯЯ граница (в прайсе + станция работает)
  physShare: Num; // now / все АЗС, % — НИЖНЯЯ граница (физически подтверждено gdebenz)
  r: Num; // now/navail — согласие источников
  gdShare: Num; // now / ответившие gdebenz, %
  blinded: boolean; // petrolplus почти не видит марку → вести по gdebenz
  cPrice: Num; // крауд-цена (gdebenz prices_now), если её дали ≥10 АЗС
  cPriceN: Num; // по скольким АЗС
  priceAgree: Num; // крауд − прайс, ₽ (независимая проверка)
  availConf: "high" | "low";
  level: TrafficLevel;
  verdict: Verdict;
  forecast: Forecast | null;
  priceTrusted: boolean; // показывать ли цену
  // --- прежние (в свёрнутых деталях) ---
  share_all: Num; // % от всех АЗС региона
  work_pct: Num; // % работающих среди продающих
  low: boolean; // мало свежих цен
  diverge: boolean; // расхождение источников (gdebenz «есть» ≫ свежих цен)
  priceReliable: boolean; // можно показывать медиану как цену
  priceSuspect: boolean; // «октановый абсурд» — выборка кривая
  spread: Num;
  spread_d7: Num;
  summary: Summary;
  series: FuelSeries;
}

export interface Overall {
  workPp: Num;
  workPp_d1: Num;
  workPp_d7: Num;
  gdBal: Num;
  gdBal_d7: Num;
  azsTotal: Num;
  azsAvailable: Num;
  gbYes: Num;
  gbNo: Num;
  gbQueue: Num;
  gbLow: Num;
}

export type BrandKind = "petrol" | "gas" | "none";

export interface BrandPrice {
  brand: string;
  n: number;
  kind: BrandKind;
  prices: Record<string, Num>;
}

export interface BrandGd {
  brand: string;
  n: number;
  resp: number; // ответивших (есть+нет+очередь+лимит)
  yes: number; // «есть» (вкл. очередь/лимит)
  availPct: Num; // yes / resp — без неизвестных
  kind: BrandKind;
  byFuel: Record<string, number>;
}

export interface FocusStation {
  brand: string;
  addr: string;
  status: string | null;
  statusText: string | null;
  fuels: string[];
  seenH: Num; // сколько часов назад видели
  stale: boolean; // наблюдение старше порога — не «сейчас»
}

// Весь файл: несколько регионов (Москва, Тверская обл.)
export interface AllData {
  regions: Data[];
  defaultRegion: string;
  empty: boolean;
}

export interface Data {
  slug: string;
  name: string;
  short: string;
  focusName: string | null;
  focusOther: string | null;
  focusStations: FocusStation[];
  seenFresh: Num;
  seenAny: Num;
  gbTotal: Num;
  empty: boolean;
  generatedMsk: string | null;
  region: string;
  monitoringDays: number;
  measurements: number;
  freshDays: number;
  fresh: { pricesAgo: string; pricesOk: boolean; gdAgo: string; gdOk: boolean };
  fuels: string[];
  defaultFuel: string;
  cityAvail: Num; // медиана availShare массовых марок (верхняя)
  cityPhys: Num; // медиана physShare массовых марок (нижняя)
  gdResp: Num;
  monDays: number;
  byFuel: Record<string, Fuel>;
  overall: Overall;
  days: string[];
  series: {
    workPp: Num[];
    gdBal: Num[];
    status: { yes: Num[]; no: Num[]; queue: Num[]; low: Num[] };
  };
  hourAvail: Num[];
  weekdayAvail: Num[];
  weekdays: string[];
  bestHour: number | null;
  bestDay: string | null;
  weekdaySpread: Num; // размах доступности по дням недели, п.п.
  whenHour: WhenProfile | null;
  whenDay: WhenProfile | null;
  alerts: string[];
  brandsPrice: BrandPrice[];
  brandsGd: BrandGd[];
  geo: Geo | null;
}

export interface GeoSide {
  resp: number;
  yes: number;
  pct: Num;
}
export interface Geo {
  in: GeoSide;
  out: GeoSide;
}
