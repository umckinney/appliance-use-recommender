"use client";

import { useEffect, useState } from "react";
import { api, AppliancePreset } from "@/lib/api";
import Button from "@/components/Button";
import Card from "@/components/Card";

type SelectedAppliance = Pick<
  AppliancePreset,
  "name" | "slug" | "cycle_kwh" | "cycle_minutes"
>;

type Props = {
  initial: SelectedAppliance[];
  onNext: (appliances: SelectedAppliance[]) => void;
  onBack: () => void;
};

export default function StepAppliances({ initial, onNext, onBack }: Props) {
  const [presets, setPresets] = useState<AppliancePreset[]>([]);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initial.map((a) => a.slug))
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .presets()
      .then(setPresets)
      .catch(() => {
        // Fallback presets if API unreachable during onboarding
        setPresets([
          { id: 1, name: "Dishwasher", slug: "dishwasher", cycle_kwh: 1.5, cycle_minutes: 90 },
          { id: 2, name: "Clothes Washer", slug: "washer", cycle_kwh: 0.5, cycle_minutes: 45 },
          { id: 3, name: "Electric Dryer", slug: "dryer", cycle_kwh: 5.0, cycle_minutes: 60 },
          {
            id: 4,
            name: "EV Charger (Level 2)",
            slug: "ev_charger",
            cycle_kwh: 25.0,
            cycle_minutes: 240,
          },
          {
            id: 5,
            name: "Pool Pump",
            slug: "pool_pump",
            cycle_kwh: 1.5,
            cycle_minutes: 60,
          },
          { id: 6, name: "HVAC (1 hour)", slug: "hvac", cycle_kwh: 3.5, cycle_minutes: 60 },
        ]);
      })
      .finally(() => setLoading(false));
  }, []);

  function toggle(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(slug) ? next.delete(slug) : next.add(slug);
      return next;
    });
  }

  function handleNext() {
    const chosen = presets.filter((p) => selected.has(p.slug));
    // Default to dishwasher if nothing selected
    onNext(chosen.length ? chosen : [presets[0]]);
  }

  const iconFor: Record<string, string> = {
    dishwasher: "🍽️",
    washer: "👕",
    dryer: "🌀",
    ev_charger: "⚡",
    pool_pump: "🏊",
    hvac: "❄️",
  };

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">
        Which appliances do you want to schedule?
      </h2>
      <p className="text-sm text-gray-500 mb-6">
        Select the appliances you&apos;d like Siri recommendations for. You can add more
        later.
      </p>

      {loading ? (
        <div className="text-sm text-gray-400 py-8 text-center">Loading appliances…</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          {presets.map((p) => {
            const on = selected.has(p.slug);
            return (
              <button
                key={p.slug}
                onClick={() => toggle(p.slug)}
                className={`rounded-xl border-2 p-4 text-left transition-colors
                  ${on ? "border-blue-600 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}
              >
                <div className="text-2xl mb-1">{iconFor[p.slug] ?? "🔌"}</div>
                <div className={`text-sm font-medium ${on ? "text-blue-700" : "text-gray-700"}`}>
                  {p.name}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {p.cycle_kwh} kWh · {p.cycle_minutes} min
                </div>
              </button>
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
