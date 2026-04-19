"use client";

import { useState } from "react";
import Button from "@/components/Button";
import Card from "@/components/Card";

type SolarData = {
  has_solar: boolean;
  net_metering: boolean;
  solar_capacity_kw?: number;
  solar_tilt_deg?: number;
  solar_azimuth_deg?: number;
  solaredge_site_id?: string;
  solaredge_api_key?: string;
};

type Props = {
  initial: SolarData;
  onNext: (data: SolarData) => void;
  onBack: () => void;
};

export default function StepSolar({ initial, onNext, onBack }: Props) {
  const [hasSolar, setHasSolar] = useState(initial.has_solar);
  const [netMetering, setNetMetering] = useState(initial.net_metering);
  const [capacityKw, setCapacityKw] = useState(initial.solar_capacity_kw?.toString() ?? "");
  const [tiltDeg, setTiltDeg] = useState(initial.solar_tilt_deg?.toString() ?? "20");
  const [azimuthDeg, setAzimuthDeg] = useState(initial.solar_azimuth_deg?.toString() ?? "180");
  const [siteId, setSiteId] = useState(initial.solaredge_site_id ?? "");
  const [apiKey, setApiKey] = useState(initial.solaredge_api_key ?? "");

  function handleNext() {
    onNext({
      has_solar: hasSolar,
      net_metering: hasSolar ? netMetering : false,
      solar_capacity_kw: capacityKw ? parseFloat(capacityKw) : undefined,
      solar_tilt_deg: tiltDeg ? parseFloat(tiltDeg) : undefined,
      solar_azimuth_deg: azimuthDeg ? parseFloat(azimuthDeg) : undefined,
      solaredge_site_id: siteId || undefined,
      solaredge_api_key: apiKey || undefined,
    });
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Do you have solar panels?</h2>
      <p className="text-sm text-gray-500 mb-6">
        FlowShift uses your solar generation to reduce appliance cost estimates via net
        metering.
      </p>

      <div className="space-y-5">
        <div className="flex gap-3">
          {[true, false].map((v) => (
            <button
              key={String(v)}
              onClick={() => setHasSolar(v)}
              className={`flex-1 py-3 rounded-xl border-2 text-sm font-medium transition-colors
                ${hasSolar === v ? "border-blue-600 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-500 hover:border-gray-300"}`}
            >
              {v ? "Yes, I have solar" : "No solar"}
            </button>
          ))}
        </div>

        {hasSolar && (
          <>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 accent-blue-600"
                checked={netMetering}
                onChange={(e) => setNetMetering(e.target.checked)}
              />
              <span className="text-sm text-gray-700">
                I have net metering (utility credits my excess solar export)
              </span>
            </label>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  System size (kW)
                </label>
                <input
                  type="number"
                  min="0.1"
                  step="0.1"
                  placeholder="e.g. 7.2"
                  className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={capacityKw}
                  onChange={(e) => setCapacityKw(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tilt (degrees)
                </label>
                <input
                  type="number"
                  min="0"
                  max="90"
                  placeholder="20"
                  className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={tiltDeg}
                  onChange={(e) => setTiltDeg(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Azimuth (degrees)
                </label>
                <input
                  type="number"
                  min="0"
                  max="360"
                  placeholder="180 = south"
                  className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={azimuthDeg}
                  onChange={(e) => setAzimuthDeg(e.target.value)}
                />
              </div>
            </div>

            <details className="group">
              <summary className="text-sm text-blue-600 cursor-pointer hover:underline list-none">
                + SolarEdge integration (optional)
              </summary>
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Site ID
                  </label>
                  <input
                    type="text"
                    placeholder="1234567"
                    className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={siteId}
                    onChange={(e) => setSiteId(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    API Key
                  </label>
                  <input
                    type="password"
                    placeholder="from monitoring.solaredge.com"
                    className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
              </div>
            </details>
          </>
        )}

        <div className="flex justify-between pt-2">
          <Button variant="secondary" onClick={onBack}>
            ← Back
          </Button>
          <Button onClick={handleNext}>Next →</Button>
        </div>
      </div>
    </Card>
  );
}
