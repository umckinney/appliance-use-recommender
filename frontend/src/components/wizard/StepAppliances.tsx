"use client";

import { useEffect, useRef, useState } from "react";
import { api, AppliancePreset, ModelSearchResult } from "@/lib/api";
import Button from "@/components/Button";
import Card from "@/components/Card";
import Spinner from "@/components/Spinner";

type SelectedAppliance = Pick<
  AppliancePreset,
  "name" | "slug" | "cycle_kwh" | "cycle_minutes"
>;

type Props = {
  initial: SelectedAppliance[];
  onNext: (appliances: SelectedAppliance[]) => void;
  onBack: () => void;
};

// Categories that support ENERGY STAR model search
const SEARCHABLE = new Set(["dishwasher", "washer", "dryer"]);

const iconFor: Record<string, string> = {
  dishwasher: "🍽️",
  washer: "👕",
  dryer: "🌀",
  ev_charger: "⚡",
  pool_pump: "🏊",
  hvac: "❄️",
};

type Override = { cycle_kwh: string; cycle_minutes: string };

function ModelSearch({
  category,
  onSelect,
}: {
  category: string;
  onSelect: (r: ModelSearchResult) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ModelSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<ModelSearchResult | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleChange(val: string) {
    setQuery(val);
    setSelected(null);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!val.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        let res = await api.searchModels(category, val);
        // If no results and query has spaces (e.g. "LG DLEX3900B"), retry with just the model token
        if (res.length === 0 && val.trim().includes(" ")) {
          const lastWord = val.trim().split(/\s+/).pop() ?? val;
          res = await api.searchModels(category, lastWord);
          // If still nothing, try dropping the last character (handles "DLEX3900B" → "DLEX3900*")
          if (res.length === 0 && lastWord.length > 4) {
            res = await api.searchModels(category, lastWord.slice(0, -1));
          }
        }
        setResults(res.slice(0, 8));
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
        setSearched(true);
      }
    }, 300);
  }

  return (
    <div className="mt-2">
      <label className="block text-xs font-medium text-gray-600 mb-1">
        Search by brand / model (optional)
      </label>
      <input
        type="text"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        placeholder="e.g. Bosch, Samsung"
        className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      {searching && (
        <p className="text-xs text-gray-400 mt-1 animate-pulse">Searching ENERGY STAR…</p>
      )}
      {searched && !searching && results.length === 0 && query.trim() && !selected && (
        <p className="text-xs text-gray-400 mt-1">No ENERGY STAR results found — enter values manually.</p>
      )}
      {selected && (
        <p className="text-xs text-green-600 mt-1">✓ {selected.brand} {selected.model} — values applied</p>
      )}
      {results.length > 0 && (
        <ul className="mt-1 border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-48 overflow-y-auto">
          {results.map((r, i) => (
            <li key={i}>
              <button
                type="button"
                onClick={() => {
                  onSelect(r);
                  setSelected(r);
                  setQuery(`${r.brand} ${r.model}`);
                  setResults([]);
                }}
                className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 transition-colors"
              >
                <span className="font-medium text-gray-800">
                  {r.brand} {r.model}
                </span>
                <span className="text-gray-500 ml-2">
                  {r.cycle_kwh} kWh
                  {r.cycle_minutes ? ` · ${r.cycle_minutes} min` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function StepAppliances({ initial, onNext, onBack }: Props) {
  const [presets, setPresets] = useState<AppliancePreset[]>([]);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initial.map((a) => a.slug))
  );
  const [overrides, setOverrides] = useState<Record<string, Override>>(
    Object.fromEntries(
      initial.map((a) => [
        a.slug,
        { cycle_kwh: String(a.cycle_kwh), cycle_minutes: String(a.cycle_minutes) },
      ])
    )
  );
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .presets()
      .then(setPresets)
      .catch(() => {
        setPresets([
          { id: 1, name: "Dishwasher", slug: "dishwasher", cycle_kwh: 1.5, cycle_minutes: 90 },
          { id: 2, name: "Clothes Washer", slug: "washer", cycle_kwh: 0.5, cycle_minutes: 45 },
          { id: 3, name: "Electric Dryer", slug: "dryer", cycle_kwh: 5.0, cycle_minutes: 60 },
          { id: 4, name: "EV Charger (Level 2)", slug: "ev_charger", cycle_kwh: 25.0, cycle_minutes: 240 },
          { id: 5, name: "Pool Pump", slug: "pool_pump", cycle_kwh: 1.5, cycle_minutes: 60 },
          { id: 6, name: "HVAC (1 hour)", slug: "hvac", cycle_kwh: 3.5, cycle_minutes: 60 },
        ]);
      })
      .finally(() => setLoading(false));
  }, []);

  function toggle(p: AppliancePreset) {
    const slug = p.slug;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        next.delete(slug);
        setExpanded((e) => (e === slug ? null : e));
      } else {
        next.add(slug);
        setOverrides((o) => ({
          ...o,
          [slug]: { cycle_kwh: String(p.cycle_kwh), cycle_minutes: String(p.cycle_minutes) },
        }));
        setExpanded(slug);
      }
      return next;
    });
  }

  function resetToDefault(p: AppliancePreset) {
    setOverrides((o) => ({
      ...o,
      [p.slug]: { cycle_kwh: String(p.cycle_kwh), cycle_minutes: String(p.cycle_minutes) },
    }));
  }

  function handleNext() {
    const chosen = presets
      .filter((p) => selected.has(p.slug))
      .map((p) => {
        const ov = overrides[p.slug];
        return {
          name: p.name,
          slug: p.slug,
          cycle_kwh: ov ? parseFloat(ov.cycle_kwh) || p.cycle_kwh : p.cycle_kwh,
          cycle_minutes: ov ? parseInt(ov.cycle_minutes) || p.cycle_minutes : p.cycle_minutes,
        };
      });
    onNext(chosen.length ? chosen : [presets[0]]);
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">
        Which appliances do you want to schedule?
      </h2>
      <p className="text-sm text-gray-500 mb-6">
        Select the appliances you&apos;d like Siri recommendations for. You can add more later.
      </p>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-gray-400">
          <Spinner size="sm" />
          Loading appliances…
        </div>
      ) : (
        <div className="space-y-2 mb-6">
          {presets.map((p) => {
            const on = selected.has(p.slug);
            const isOpen = expanded === p.slug && on;
            const ov = overrides[p.slug];

            return (
              <div key={p.slug}>
                <button
                  onClick={() => {
                    if (on) {
                      setExpanded((e) => (e === p.slug ? null : p.slug));
                    } else {
                      toggle(p);
                    }
                  }}
                  className={`w-full rounded-xl border-2 px-4 py-3 text-left flex items-center gap-3 transition-colors
                    ${on ? "border-blue-600 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}
                >
                  <span className="text-xl shrink-0">{iconFor[p.slug] ?? "🔌"}</span>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-medium ${on ? "text-blue-700" : "text-gray-700"}`}>
                      {p.name}
                    </div>
                    <div className="text-xs text-gray-400">
                      {ov && on
                        ? `${ov.cycle_kwh} kWh · ${ov.cycle_minutes} min`
                        : `${p.cycle_kwh} kWh · ${p.cycle_minutes} min`}
                    </div>
                  </div>
                  {on && (
                    <span
                      className="text-xs text-blue-400 shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggle(p);
                      }}
                    >
                      ✕ remove
                    </span>
                  )}
                </button>

                {isOpen && (
                  <div className="border border-blue-100 bg-blue-50/50 rounded-xl px-4 py-3 mt-0.5 space-y-3">
                    {SEARCHABLE.has(p.slug) && (
                      <ModelSearch
                        category={p.slug === "washer" ? "washer" : p.slug}
                        onSelect={(r) => {
                          setOverrides((o) => ({
                            ...o,
                            [p.slug]: {
                              cycle_kwh: String(r.cycle_kwh),
                              cycle_minutes: String(r.cycle_minutes ?? (ov?.cycle_minutes ?? p.cycle_minutes)),
                            },
                          }));
                        }}
                      />
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">
                          Energy per cycle (kWh)
                        </label>
                        <input
                          type="number"
                          min="0.01"
                          step="0.1"
                          value={ov?.cycle_kwh ?? p.cycle_kwh}
                          onChange={(e) =>
                            setOverrides((o) => ({
                              ...o,
                              [p.slug]: { ...o[p.slug], cycle_kwh: e.target.value },
                            }))
                          }
                          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">
                          Cycle duration (min)
                        </label>
                        <input
                          type="number"
                          min="1"
                          step="1"
                          value={ov?.cycle_minutes ?? p.cycle_minutes}
                          onChange={(e) =>
                            setOverrides((o) => ({
                              ...o,
                              [p.slug]: { ...o[p.slug], cycle_minutes: e.target.value },
                            }))
                          }
                          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => resetToDefault(p)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Use default ({p.cycle_kwh} kWh · {p.cycle_minutes} min)
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>
          ← Back
        </Button>
        <Button onClick={handleNext} disabled={loading}>
          Next →
        </Button>
      </div>
    </Card>
  );
}
