"use client";

import { useState } from "react";
import Button from "@/components/Button";
import Card from "@/components/Card";

type Props = {
  initial: { name?: string; email?: string; optimization_weight: number };
  onNext: (data: { name?: string; email?: string; optimization_weight: number }) => void;
  onBack: () => void;
};

const WEIGHT_OPTIONS = [
  { label: "Save money", emoji: "💰", value: 0.0 },
  { label: "Balance both", emoji: "⚖️", value: 0.5 },
  { label: "Minimize carbon", emoji: "🌱", value: 1.0 },
] as const;

export function WeightSelector({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {WEIGHT_OPTIONS.map((opt) => {
        const selected = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex flex-col items-center gap-1 rounded-xl border-2 px-3 py-3 text-center transition-colors
              ${selected
                ? "border-blue-600 bg-blue-50 text-blue-700"
                : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
              }`}
          >
            <span className="text-xl">{opt.emoji}</span>
            <span className="text-xs font-medium leading-tight">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export default function StepPreferences({ initial, onNext, onBack }: Props) {
  const [name, setName] = useState(initial.name ?? "");
  const [email, setEmail] = useState(initial.email ?? "");
  const [weight, setWeight] = useState(initial.optimization_weight);

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">A few last details</h2>
      <p className="text-sm text-gray-500 mb-6">
        Optional, but helps personalise your experience.
      </p>

      <div className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-gray-400">(optional)</span>
            </label>
            <input
              type="text"
              placeholder="Alex"
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email <span className="text-gray-400">(optional — lets you recover your key)</span>
            </label>
            <input
              type="email"
              placeholder="alex@example.com"
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Optimise for
          </label>
          <WeightSelector value={weight} onChange={setWeight} />
          <p className="text-xs text-gray-400 mt-2">
            You can change this from the dashboard.
          </p>
        </div>

        <div className="flex justify-between pt-2">
          <Button variant="secondary" onClick={onBack}>
            ← Back
          </Button>
          <Button
            onClick={() =>
              onNext({
                name: name || undefined,
                email: email || undefined,
                optimization_weight: weight,
              })
            }
          >
            Create my account →
          </Button>
        </div>
      </div>
    </Card>
  );
}
