"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import {
  api,
  ApplianceOut,
  ForecastHour,
  ForecastResponse,
  ModelSearchResult,
  RecommendResponse,
  StatusResponse,
} from "@/lib/api";
import Card from "@/components/Card";
import Spinner from "@/components/Spinner";

// ─── Helpers ────────────────────────────────────────────────────────────────

function carbonColor(label: string): string {
  switch (label) {
    case "very clean": return "text-green-600 bg-green-50";
    case "clean":      return "text-green-500 bg-green-50";
    case "moderate":   return "text-yellow-600 bg-yellow-50";
    case "dirty":      return "text-orange-600 bg-orange-50";
    case "very dirty": return "text-red-600 bg-red-50";
    default:           return "text-gray-600 bg-gray-50";
  }
}

function rateColor(period: string): string {
  switch (period) {
    case "off_peak":  return "text-green-700 bg-green-50";
    case "mid_peak":  return "text-yellow-700 bg-yellow-50";
    case "peak":      return "text-red-700 bg-red-50";
    default:          return "text-gray-700 bg-gray-50";
  }
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", hour12: true });
  } catch {
    return iso;
  }
}

function fmtRate(r: number): string {
  return `${(r * 100).toFixed(1)}¢`;
}

const SLUG_ICON: Record<string, string> = {
  dishwasher: "🍽️",
  washer:     "👕",
  dryer:      "🌀",
  ev_charger: "⚡",
  pool_pump:  "🏊",
  hvac:       "❄️",
};

const SLUG_COLOR: Record<string, { bar: string; light: string }> = {
  dishwasher: { bar: "bg-blue-500",   light: "bg-blue-100"   },
  washer:     { bar: "bg-teal-500",   light: "bg-teal-100"   },
  dryer:      { bar: "bg-orange-500", light: "bg-orange-100" },
  ev_charger: { bar: "bg-purple-500", light: "bg-purple-100" },
  pool_pump:  { bar: "bg-cyan-500",   light: "bg-cyan-100"   },
  hvac:       { bar: "bg-rose-500",   light: "bg-rose-100"   },
};

function applianceColor(slug: string) {
  return SLUG_COLOR[slug] ?? { bar: "bg-gray-500", light: "bg-gray-100" };
}

// ─── ForecastBar ────────────────────────────────────────────────────────────

function ForecastBar({ hour, isBest }: { hour: ForecastHour; isBest: boolean }) {
  const maxRate = 0.20;
  const widthPct = Math.min(100, (hour.rate_usd_kwh / maxRate) * 100);
  return (
    <div
      className={`flex items-center gap-3 py-1.5 px-2 rounded-lg transition-colors ${
        isBest ? "bg-blue-50 ring-1 ring-blue-300" : "hover:bg-gray-50"
      }`}
    >
      <span className="text-xs text-gray-500 w-14 shrink-0">{fmtTime(hour.hour_local)}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div
          className={`h-2 rounded-full ${
            hour.rate_period === "peak"
              ? "bg-red-400"
              : hour.rate_period === "mid_peak"
              ? "bg-yellow-400"
              : "bg-green-400"
          }`}
          style={{ width: `${widthPct}%` }}
        />
      </div>
      <span className="text-xs text-gray-600 w-10 text-right shrink-0">
        {fmtRate(hour.rate_usd_kwh)}
      </span>
      {hour.solar_kw !== null && hour.solar_kw > 0 && (
        <span className="text-xs text-yellow-500" title={`${hour.solar_kw.toFixed(1)} kW solar`}>
          ☀️
        </span>
      )}
      {isBest && (
        <span className="text-xs text-blue-600 font-semibold shrink-0">★ best</span>
      )}
    </div>
  );
}

// ─── ScheduleSection ────────────────────────────────────────────────────────

function ScheduleSection({
  appliances,
  apiKey,
  forecastHours,
}: {
  appliances: ApplianceOut[];
  apiKey: string;
  forecastHours: ForecastHour[];
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [recs, setRecs] = useState<Record<string, RecommendResponse>>({});
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());

  // Map hour_local → index for O(1) lookup
  const hourIndexMap = useMemo(() => {
    const m: Record<string, number> = {};
    forecastHours.forEach((h, i) => { m[h.hour_local] = i; });
    return m;
  }, [forecastHours]);

  async function fetchRec(slug: string) {
    setLoadingSet((s) => new Set([...s, slug]));
    try {
      const r = await api.recommend(apiKey, slug);
      setRecs((prev) => ({ ...prev, [slug]: r }));
    } catch {
      // silently ignore — appliance just won't show on timeline
    } finally {
      setLoadingSet((s) => { const n = new Set(s); n.delete(slug); return n; });
    }
  }

  function toggle(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
        setRecs((r) => { const n = { ...r }; delete n[slug]; return n; });
      } else {
        next.add(slug);
        fetchRec(slug);
      }
      return next;
    });
  }

  // Compute timeline bars for selected appliances that have recommendations
  type Bar = {
    slug: string;
    name: string;
    startIdx: number;
    spanCols: number;
    rec: RecommendResponse;
  };

  const bars: Bar[] = useMemo(() => {
    return appliances
      .filter((a) => selected.has(a.slug) && recs[a.slug])
      .map((a) => {
        const rec = recs[a.slug];
        const startIdx = hourIndexMap[rec.best_windows[0]?.hour_local ?? ""] ?? -1;
        const spanCols = Math.max(1, Math.ceil(a.cycle_minutes / 60));
        return { slug: a.slug, name: a.name, startIdx, spanCols, rec };
      })
      .filter((b) => b.startIdx >= 0);
  }, [appliances, selected, recs, hourIndexMap]);

  // Detect overlapping bars
  const overlapWarnings = useMemo(() => {
    const warnings: string[] = [];
    for (let i = 0; i < bars.length; i++) {
      for (let j = i + 1; j < bars.length; j++) {
        const a = bars[i];
        const b = bars[j];
        const aEnd = a.startIdx + a.spanCols;
        const bEnd = b.startIdx + b.spanCols;
        if (a.startIdx < bEnd && b.startIdx < aEnd) {
          warnings.push(`${a.name} and ${b.name} overlap — check your panel capacity`);
        }
      }
    }
    return warnings;
  }, [bars]);

  if (appliances.length === 0) return null;

  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 mb-3">Schedule for today</h2>
      <p className="text-xs text-gray-400 mb-3">
        Select appliances to see their best run windows on the timeline below.
      </p>

      {/* Toggle pills */}
      <div className="flex flex-wrap gap-2 mb-4">
        {appliances.map((a) => {
          const on = selected.has(a.slug);
          const spinning = loadingSet.has(a.slug);
          return (
            <button
              key={a.slug}
              onClick={() => toggle(a.slug)}
              disabled={spinning}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-colors ${
                on
                  ? `${applianceColor(a.slug).light} border-transparent font-medium text-gray-800`
                  : "bg-white border-gray-300 text-gray-600 hover:border-gray-400"
              } disabled:opacity-60`}
            >
              <span>{SLUG_ICON[a.slug] ?? "🔌"}</span>
              <span>{a.name}</span>
              {spinning && <Spinner size="sm" />}
            </button>
          );
        })}
      </div>

      {/* Timeline */}
      {forecastHours.length > 0 && (
        <div className="overflow-x-auto pb-1">
          <div className="min-w-[480px]">
            {/* Hour labels (every 3h) */}
            <div className="relative h-5 mb-0.5">
              {[0, 3, 6, 9, 12, 15, 18, 21].map((i) => (
                <span
                  key={i}
                  className="absolute text-xs text-gray-400 transform -translate-x-1/2"
                  style={{ left: `${(i / 24) * 100}%` }}
                >
                  {fmtTime(forecastHours[i]?.hour_local ?? "")}
                </span>
              ))}
            </div>

            {/* Rate period background */}
            <div
              className="flex gap-px h-3 rounded overflow-hidden mb-2"
            >
              {forecastHours.map((h, i) => (
                <div
                  key={i}
                  className={`flex-1 ${
                    h.rate_period === "peak"
                      ? "bg-red-300"
                      : h.rate_period === "mid_peak"
                      ? "bg-yellow-300"
                      : "bg-green-300"
                  }`}
                />
              ))}
            </div>

            {/* Appliance bars */}
            {bars.length === 0 && selected.size > 0 && loadingSet.size === 0 && (
              <p className="text-xs text-gray-400 py-2">
                No recommendation available for the selected appliance(s).
              </p>
            )}
            <div className="space-y-1.5">
              {bars.map((bar) => {
                const { bar: barColor } = applianceColor(bar.slug);
                const leftPct = (bar.startIdx / 24) * 100;
                const widthPct = (Math.min(bar.spanCols, 24 - bar.startIdx) / 24) * 100;
                const w = bar.rec.best_windows[0];
                return (
                  <div key={bar.slug} className="relative h-7">
                    {/* Background track */}
                    <div className="absolute inset-0 bg-gray-100 rounded" />
                    {/* Colored bar */}
                    <div
                      className={`absolute top-0 h-full rounded ${barColor} opacity-90`}
                      style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                    />
                    {/* Label inside bar */}
                    <div
                      className="absolute top-0 h-full flex items-center px-1.5 overflow-hidden"
                      style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                    >
                      <span className="text-xs text-white font-medium truncate">
                        {SLUG_ICON[bar.slug] ?? "🔌"} {bar.name}
                      </span>
                    </div>
                    {/* Summary to the right of bar (if space) */}
                    <div
                      className="absolute top-0 h-full flex items-center pl-1 overflow-hidden"
                      style={{ left: `${leftPct + widthPct}%`, maxWidth: `${100 - leftPct - widthPct}%` }}
                    >
                      <span className="text-xs text-gray-500 whitespace-nowrap">
                        {fmtTime(w.hour_local)} · {fmtRate(w.rate_usd_kwh)} · {w.carbon_kg.toFixed(2)} kg
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            <div className="flex gap-4 mt-3 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-300 inline-block" /> Off-peak
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-yellow-300 inline-block" /> Mid-peak
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-300 inline-block" /> Peak
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Overlap warnings */}
      {overlapWarnings.map((w, i) => (
        <p key={i} className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 mt-2">
          ⚠️ {w}
        </p>
      ))}

      {/* Per-appliance summary */}
      {bars.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-gray-100 pt-3">
          {bars.map((bar) => {
            const w = bar.rec.best_windows[0];
            return (
              <p key={bar.slug} className="text-xs text-gray-600">
                {SLUG_ICON[bar.slug] ?? "🔌"}{" "}
                <span className="font-medium">{bar.name}</span> at{" "}
                {fmtTime(w.hour_local)} —{" "}
                {fmtRate(w.rate_usd_kwh)}/kWh · {w.carbon_kg.toFixed(2)} kg CO₂
              </p>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// ─── AppliancesCard ──────────────────────────────────────────────────────────

const SEARCHABLE_CATEGORIES = ["dishwasher", "washer", "dryer"];

function AppliancesCard({
  apiKey,
  appliances,
  onAppliancesChange,
}: {
  apiKey: string;
  appliances: ApplianceOut[];
  onAppliancesChange: (a: ApplianceOut[]) => void;
}) {
  const [deleting, setDeleting] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const [addName, setAddName] = useState("");
  const [addKwh, setAddKwh] = useState("");
  const [addMin, setAddMin] = useState("");
  const [addCategory, setAddCategory] = useState("dishwasher");
  const [addError, setAddError] = useState("");
  const [adding, setAdding] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ModelSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleDelete(slug: string) {
    setDeleting(slug);
    try {
      await api.deleteAppliance(apiKey, slug);
      onAppliancesChange(appliances.filter((x) => x.slug !== slug));
    } finally {
      setDeleting(null);
    }
  }

  function handleSearchChange(val: string) {
    setSearchQuery(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!val.trim() || !SEARCHABLE_CATEGORIES.includes(addCategory)) {
      setSearchResults([]);
      return;
    }
    timerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.searchModels(addCategory, val);
        setSearchResults(res.slice(0, 8));
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  }

  function selectModel(r: ModelSearchResult) {
    setAddKwh(String(r.cycle_kwh));
    if (r.cycle_minutes) setAddMin(String(r.cycle_minutes));
    setSearchQuery(`${r.brand} ${r.model}`);
    setSearchResults([]);
  }

  async function handleAdd() {
    if (!addName.trim() || !addKwh || !addMin) {
      setAddError("Name, kWh, and minutes are required.");
      return;
    }
    const slug = addName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    setAdding(true);
    setAddError("");
    try {
      const created = await api.addAppliance(apiKey, {
        name: addName.trim(),
        slug,
        cycle_kwh: parseFloat(addKwh),
        cycle_minutes: parseInt(addMin),
      });
      const idx = appliances.findIndex((x) => x.slug === created.slug);
      onAppliancesChange(
        idx >= 0 ? appliances.map((x, i) => (i === idx ? created : x)) : [...appliances, created]
      );
      setShowAdd(false);
      setAddName(""); setAddKwh(""); setAddMin("");
      setSearchQuery(""); setSearchResults([]);
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add appliance.");
    } finally {
      setAdding(false);
    }
  }

  return (
    <Card>
      <h2 className="text-sm font-semibold text-gray-700 mb-4">Your appliances</h2>

      {appliances.length === 0 ? (
        <p className="text-sm text-gray-400 mb-4">No appliances added yet.</p>
      ) : (
        <div className="space-y-1 mb-4">
          {appliances.map((a) => (
            <div key={a.slug} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-50">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-gray-800">{a.name}</span>
                <span className="text-xs text-gray-400 ml-2">
                  {a.cycle_kwh} kWh · {a.cycle_minutes} min
                </span>
              </div>
              <button
                onClick={() => handleDelete(a.slug)}
                disabled={deleting === a.slug}
                className="text-xs text-red-400 hover:text-red-600 transition-colors shrink-0"
              >
                {deleting === a.slug ? "…" : "Delete"}
              </button>
            </div>
          ))}
        </div>
      )}

      {!showAdd ? (
        <button onClick={() => setShowAdd(true)} className="text-sm text-blue-600 hover:underline">
          + Add appliance
        </button>
      ) : (
        <div className="border border-gray-200 rounded-xl p-4 space-y-3">
          <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Add appliance</p>

          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Name</label>
              <input
                type="text"
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
                placeholder="e.g. My Dishwasher"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Category (for model search)</label>
              <select
                value={addCategory}
                onChange={(e) => { setAddCategory(e.target.value); setSearchQuery(""); setSearchResults([]); }}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="dishwasher">Dishwasher</option>
                <option value="washer">Clothes Washer</option>
                <option value="dryer">Dryer</option>
                <option value="other">Other (manual entry)</option>
              </select>
            </div>

            {SEARCHABLE_CATEGORIES.includes(addCategory) && (
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">Search brand / model (optional)</label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder="e.g. Bosch, Samsung"
                  className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {searching && <p className="text-xs text-gray-400 mt-1 animate-pulse">Searching ENERGY STAR…</p>}
                {searchResults.length > 0 && (
                  <ul className="mt-1 border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-40 overflow-y-auto">
                    {searchResults.map((r, i) => (
                      <li key={i}>
                        <button
                          type="button"
                          onClick={() => selectModel(r)}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 transition-colors"
                        >
                          <span className="font-medium text-gray-800">{r.brand} {r.model}</span>
                          <span className="text-gray-500 ml-2">
                            {r.cycle_kwh} kWh{r.cycle_minutes ? ` · ${r.cycle_minutes} min` : ""}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">kWh / cycle</label>
              <input
                type="number" min="0.01" step="0.1" value={addKwh}
                onChange={(e) => setAddKwh(e.target.value)} placeholder="e.g. 1.5"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Cycle duration (min)</label>
              <input
                type="number" min="1" step="1" value={addMin}
                onChange={(e) => setAddMin(e.target.value)} placeholder="e.g. 90"
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {addError && <p className="text-xs text-red-500">{addError}</p>}

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleAdd} disabled={adding}
              className="text-xs bg-blue-600 text-white rounded-lg px-4 py-1.5 hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {adding ? "Adding…" : "Add"}
            </button>
            <button
              onClick={() => { setShowAdd(false); setAddError(""); }}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}

// ─── Recovery panel (no API key state) ───────────────────────────────────────

function KeyRecoveryPanel() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [foundKey, setFoundKey] = useState("");
  const [notFound, setNotFound] = useState(false);

  async function handleLookup() {
    if (!email.trim()) return;
    setLoading(true);
    setNotFound(false);
    setFoundKey("");
    try {
      const res = await api.accountLookup(email.trim());
      setFoundKey(res.api_key);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <p className="text-sm font-medium text-gray-700 mb-3">Recover your API key</p>
      <div className="flex gap-2">
        <input
          type="email" value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLookup()}
          placeholder="your@email.com"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleLookup} disabled={loading}
          className="shrink-0 text-sm bg-blue-600 text-white rounded-lg px-4 py-1.5 hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "…" : "Find my key"}
        </button>
      </div>
      {notFound && <p className="text-xs text-red-500 mt-2">No account found for that email.</p>}
      {foundKey && (
        <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3">
          <p className="text-xs text-green-700 font-medium mb-1">Found your account!</p>
          <code className="text-xs font-mono text-gray-800 break-all">{foundKey}</code>
          <div className="mt-2">
            <a
              href={`/dashboard?api_key=${encodeURIComponent(foundKey)}`}
              className="text-xs text-blue-600 hover:underline font-medium"
            >
              Go to dashboard →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── DashboardContent ─────────────────────────────────────────────────────────

function DashboardContent() {
  const params = useSearchParams();
  const router = useRouter();
  const apiKey = params.get("api_key") ?? "";

  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [appliances, setAppliances] = useState<ApplianceOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!apiKey) { setLoading(false); return; }
    Promise.all([api.status(apiKey), api.forecast(apiKey), api.listAppliances(apiKey)])
      .then(([s, f, a]) => { setStatus(s); setForecast(f); setAppliances(a); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [apiKey]);

  if (!apiKey) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 mb-2">No API key found.</p>
        <button
          onClick={() => router.push("/onboard")}
          className="text-blue-600 hover:underline text-sm"
        >
          Complete onboarding →
        </button>
        <KeyRecoveryPanel />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-gray-400 text-sm">
        <Spinner size="md" />
        Loading your grid snapshot…
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 text-sm mb-2">{error}</p>
        <button
          onClick={() => router.push("/onboard")}
          className="text-blue-600 hover:underline text-sm"
        >
          ← Back to onboarding
        </button>
        <KeyRecoveryPanel />
      </div>
    );
  }

  const bestHour = forecast?.best_window_start;

  return (
    <div className="space-y-6">
      {/* Status strip */}
      {status && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card className="text-center">
            <p className="text-xs text-gray-500 mb-1">Grid carbon</p>
            <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${carbonColor(status.carbon_label)}`}>
              {status.carbon_label}
            </span>
            <p className="text-xs text-gray-400 mt-1">{status.carbon_intensity_g_kwh.toFixed(0)} g/kWh</p>
          </Card>
          <Card className="text-center">
            <p className="text-xs text-gray-500 mb-1">Rate now</p>
            <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${rateColor(status.rate_period)}`}>
              {status.rate_period.replace("_", " ")}
            </span>
            <p className="text-xs text-gray-400 mt-1">{fmtRate(status.current_rate_usd_kwh)}/kWh</p>
          </Card>
          {status.solar_kw !== null && (
            <Card className="text-center">
              <p className="text-xs text-gray-500 mb-1">Solar now</p>
              <p className="text-lg font-semibold text-yellow-500">{status.solar_kw.toFixed(1)} kW</p>
            </Card>
          )}
          <Card className="text-center">
            <p className="text-xs text-gray-500 mb-1">Best window</p>
            <p className="text-sm font-semibold text-blue-700">{bestHour ? fmtTime(bestHour) : "—"}</p>
            <p className="text-xs text-gray-400 mt-1">lowest cost+carbon</p>
          </Card>
        </div>
      )}

      {/* 24h forecast */}
      {forecast && (
        <Card>
          <h2 className="text-sm font-semibold text-gray-700 mb-4">24-hour rate forecast</h2>
          <div className="space-y-0.5">
            {forecast.hours.map((h) => (
              <ForecastBar key={h.hour_local} hour={h} isBest={h.hour_local === bestHour} />
            ))}
          </div>
          <div className="flex gap-4 mt-4 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-400 inline-block" /> Off-peak
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" /> Mid-peak
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-400 inline-block" /> Peak
            </span>
          </div>
        </Card>
      )}

      {/* Schedule for today */}
      {forecast && (
        <ScheduleSection
          appliances={appliances}
          apiKey={apiKey}
          forecastHours={forecast.hours}
        />
      )}

      {/* Appliance management */}
      <AppliancesCard
        apiKey={apiKey}
        appliances={appliances}
        onAppliancesChange={setAppliances}
      />

      {/* API key reminder */}
      <Card className="bg-gray-50">
        <p className="text-xs text-gray-500">
          <span className="font-medium">Your API key:</span>{" "}
          <code className="text-gray-700">{apiKey}</code>
          <span className="ml-2 text-gray-400">
            — use this in Siri shortcuts and the FlowShift API
          </span>
        </p>
      </Card>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-slate-100 p-4 pt-12">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-gray-900">⚡ FlowShift</h1>
          <a href="/onboard" className="text-sm text-blue-600 hover:underline">Update settings</a>
        </div>
        <Suspense fallback={<div className="text-center py-20 text-gray-400 text-sm">Loading…</div>}>
          <DashboardContent />
        </Suspense>
      </div>
    </main>
  );
}
