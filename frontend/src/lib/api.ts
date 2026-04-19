/**
 * FlowShift API client — thin wrapper around fetch.
 * Base URL is read from NEXT_PUBLIC_API_URL env var (defaults to localhost:8000).
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AppliancePreset = {
  id: number;
  name: string;
  slug: string;
  cycle_kwh: number;
  cycle_minutes: number;
};

export type ApplianceOut = AppliancePreset & { notes?: string };

export type ModelSearchResult = {
  brand: string;
  model: string;
  cycle_kwh: number;
  cycle_minutes: number | null;
};

export type OnboardPayload = {
  name?: string;
  email?: string;
  address: string;
  utility_id: string;
  rate_plan?: string;
  net_metering?: boolean;
  has_solar?: boolean;
  solar_capacity_kw?: number;
  solar_tilt_deg?: number;
  solar_azimuth_deg?: number;
  solaredge_site_id?: string;
  solaredge_api_key?: string;
  optimization_weight?: number;
  appliances?: Pick<AppliancePreset, "name" | "slug" | "cycle_kwh" | "cycle_minutes">[];
};

export type OnboardResponse = {
  api_key: string;
  message: string;
};

export type StatusResponse = {
  grid_zone: string;
  carbon_intensity_g_kwh: number;
  carbon_label: string;
  current_rate_usd_kwh: number;
  rate_period: string;
  solar_kw: number | null;
  timestamp: string;
};

export type ForecastHour = {
  hour_local: string;
  carbon_g_kwh: number;
  rate_usd_kwh: number;
  rate_period: string;
  solar_kw: number | null;
};

export type ForecastResponse = {
  hours: ForecastHour[];
  best_window_start: string;
  utility_id: string;
};

export type RecommendWindow = {
  hour_utc: string;
  hour_local: string;
  rate_usd_kwh: number;
  carbon_g_kwh: number;
  solar_kw: number;
  net_cost_usd: number;
  carbon_kg: number;
  score: number;
};

export type RecommendResponse = {
  appliance: string;
  text: string;
  best_windows: RecommendWindow[];
  current_window: RecommendWindow;
  cost_now_usd: number;
  cost_best_usd: number;
  carbon_now_kg: number;
  carbon_best_kg: number;
  data_sources: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  onboard: (payload: OnboardPayload) =>
    request<OnboardResponse>("/onboard", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  presets: () => request<AppliancePreset[]>("/appliances/presets"),

  listAppliances: (apiKey: string) =>
    request<ApplianceOut[]>(`/appliances?api_key=${encodeURIComponent(apiKey)}`),

  addAppliance: (
    apiKey: string,
    a: Omit<ApplianceOut, "id">
  ) =>
    request<ApplianceOut>(`/appliances?api_key=${encodeURIComponent(apiKey)}`, {
      method: "POST",
      body: JSON.stringify(a),
    }),

  deleteAppliance: (apiKey: string, slug: string) =>
    request<void>(
      `/appliances/${encodeURIComponent(slug)}?api_key=${encodeURIComponent(apiKey)}`,
      { method: "DELETE" }
    ),

  searchModels: (category: string, q: string) =>
    request<ModelSearchResult[]>(
      `/appliances/search?category=${encodeURIComponent(category)}&q=${encodeURIComponent(q)}`
    ),

  status: (apiKey: string) =>
    request<StatusResponse>(`/status?api_key=${encodeURIComponent(apiKey)}`),

  forecast: (apiKey: string) =>
    request<ForecastResponse>(`/forecast?api_key=${encodeURIComponent(apiKey)}`),

  recommend: (apiKey: string, slug: string) =>
    request<RecommendResponse>(
      `/recommend/${slug}?api_key=${encodeURIComponent(apiKey)}`
    ),
};
