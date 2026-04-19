"use client";

import { useState } from "react";
import Button from "@/components/Button";
import Card from "@/components/Card";

const UTILITIES = [
  { id: "seattle_city_light", name: "Seattle City Light" },
  // more added here as community contributes YAML files
];

type Props = {
  initial: { address: string; utility_id: string };
  onNext: (data: { address: string; utility_id: string }) => void;
};

export default function StepLocation({ initial, onNext }: Props) {
  const [address, setAddress] = useState(initial.address);
  const [utility, setUtility] = useState(initial.utility_id || UTILITIES[0].id);
  const [error, setError] = useState("");

  function handleNext() {
    if (!address.trim()) {
      setError("Please enter your street address.");
      return;
    }
    setError("");
    onNext({ address: address.trim(), utility_id: utility });
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Where are you located?</h2>
      <p className="text-sm text-gray-500 mb-6">
        We use your full street address to get accurate solar irradiance and locate your
        grid zone.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Street address
          </label>
          <input
            type="text"
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="123 Main St, Seattle, WA 98101"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleNext()}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Electric utility
          </label>
          <select
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            value={utility}
            onChange={(e) => setUtility(e.target.value)}
          >
            {UTILITIES.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-400 mt-1">
            Don&apos;t see yours?{" "}
            <a
              href="https://github.com/your-org/flowshift"
              className="text-blue-500 hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              Contribute a rate file
            </a>
          </p>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-end pt-2">
          <Button onClick={handleNext}>Next →</Button>
        </div>
      </div>
    </Card>
  );
}
