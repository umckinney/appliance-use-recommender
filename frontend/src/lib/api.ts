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
  postal_code?: string;
  utility_id: string;
  utility_name?: string;
  utility_eia_id?: number;
  utility_rate_avg?: number;
  utility_tier?: number;
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

export type UtilitySearchResult = {
  eia_id: number;
  utility_name: string;
  state: string | null;
  ownership_type: string | null;
  residential_rate_avg: number | null;
  source_year: number | null;
  is_primary: boolean;
  utility_id: string;
};

export type UtilitySearchResponse = {
  zipcode: string;
  utilities: UtilitySearchResult[];
  warning: string | null;
};

export type UrdbTariff = {
  urdb_label: string;
  name: string | null;
  utility_id: string;  // "urdb_{label}"
  effective_date: string | null;
  is_active: boolean;
  periods: Record<string, number>;  // {"off_peak": 0.07, "peak": 0.17}
  net_metering_credit: number;
};

export type TariffListResponse = {
  eia_id: number;
  utility_name: string | null;
  tariffs: UrdbTariff[];
};

export type DataSourceInfo = {
  source: string;
  tier: number | null;
  detail: string | null;
  freshness: string | null;
};

export type DataSourcesResponse = {
  utility: DataSourceInfo;
  carbon: DataSourceInfo;
  solar: DataSourceInfo;
  rates: DataSourceInfo;
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

export type AllRecommendResponse = {
  text: string;
  best_shared_start: string;
  per_appliance: RecommendResponse[];
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

  getBrands: (category: string) =>
    request<string[]>(`/appliances/brands?category=${encodeURIComponent(category)}`),

  getModelsForBrand: (category: string, brand: string) =>
    request<ModelSearchResult[]>(
      `/appliances/models?category=${encodeURIComponent(category)}&brand=${encodeURIComponent(brand)}`
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

  recommendAll: (apiKey: string) =>
    request<AllRecommendResponse>(
      `/recommend/all?api_key=${encodeURIComponent(apiKey)}`
    ),

  getShortcutUrl: (slug: string, apiKey: string): string =>
    `${BASE}/shortcuts/${encodeURIComponent(slug)}?api_key=${encodeURIComponent(apiKey)}`,

  updatePreferences: (apiKey: string, optimizationWeight: number) =>
    request<{ optimization_weight: number }>(
      `/account/preferences?api_key=${encodeURIComponent(apiKey)}`,
      {
        method: "PATCH",
        body: JSON.stringify({ optimization_weight: optimizationWeight }),
      }
    ),

  searchUtilities: (zip: string) =>
    request<UtilitySearchResponse>(`/utilities/search?zip=${encodeURIComponent(zip)}`),

  listTariffs: (eiaId: number) =>
    request<TariffListResponse>(`/utilities/tariffs?eia_id=${eiaId}`),

  getDataSources: (apiKey: string) =>
    request<DataSourcesResponse>(`/data-sources?api_key=${encodeURIComponent(apiKey)}`),
};
