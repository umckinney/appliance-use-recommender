"use client";

import { useState } from "react";
import Button from "@/components/Button";
import Card from "@/components/Card";

type Props = {
  initial: { name?: string; email?: string; optimization_weight: number };
  onNext: (data: { name?: string; email?: string; optimization_weight: number }) => void;
  onBack: () => void;
};

export default function StepPreferences({ initial, onNext, onBack }: Props) {
  const [name, setName] = useState(initial.name ?? "");
  const [email, setEmail] = useState(initial.email ?? "");
  const [weight, setWeight] = useState(initial.optimization_weight);

  const weightLabel =
    weight < 0.2
      ? "Cost-focused"
      : weight > 0.8
        ? "Carbon-focused"
        : weight === 0.5
          ? "Balanced"
          : weight < 0.5
            ? "Mostly cost"
            : "Mostly carbon";

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
            Optimise for:{" "}
            <span className="text-blue-600 font-semibold">{weightLabel}</span>
          </label>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 w-16 text-right">💰 Cost</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              className="flex-1 accent-blue-600"
              value={weight}
              onChange={(e) => setWeight(parseFloat(e.target.value))}
            />
            <span className="text-xs text-gray-500 w-16">🌱 Carbon</span>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            You can adjust this per query later via the API.
          </p>
        </div>

        <div className="flex justify-between pt-2">
          <Button variant="secondary" onClick={onBack}>
            ← Back
          </Button>
          <Button onClick={() => onNext({ name: name || undefined, email: email || undefined, optimization_weight: weight })}>
            Create my account →
          </Button>
        </div>
      </div>
    </Card>
  );
}
