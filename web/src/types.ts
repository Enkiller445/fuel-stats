// Форма web/public/data.json (его пишет export_json.py)

export type Level = "good" | "warn" | "serious" | "crit";
export type Num = number | null;

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

export interface BrandPrice {
  brand: string;
  n: number;
  prices: Record<string, Num>;
}

export interface BrandGd {
  brand: string;
  n: number;
  yes: number;
  byFuel: Record<string, number>;
}

export interface Data {
  empty: boolean;
  generatedMsk: string | null;
  region: string;
  monitoringDays: number;
  measurements: number;
  freshDays: number;
  fresh: { pricesAgo: string; pricesOk: boolean; gdAgo: string; gdOk: boolean };
  fuels: string[];
  defaultFuel: string;
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
