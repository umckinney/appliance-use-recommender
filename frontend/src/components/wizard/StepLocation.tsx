"use client";

import { useEffect, useRef, useState } from "react";
import Button from "@/components/Button";
import Card from "@/components/Card";
import { api, UrdbTariff, UtilitySearchResult } from "@/lib/api";

// Fallback for self-hosters who contributed YAML rate files
const YAML_UTILITIES = [
  { id: "seattle_city_light", name: "Seattle City Light" },
];

// Extract a US 5-digit ZIP from an address string
function extractZip(address: string): string {
  const matches = address.match(/(?:^|[\s,])(\d{5})(?:-\d{4})?(?:\s|,|$)/g) ?? [];
  const last = matches[matches.length - 1];
  return last ? last.replace(/[^0-9]/g, "").slice(0, 5) : "";
}

// Detect likely non-US postal code (doesn't match 5-digit US pattern)
function isLikelyNonUS(postal: string): boolean {
  return postal.length > 0 && !/^\d{5}$/.test(postal.replace(/\s/g, ""));
}

function fmtCents(rate: number): string {
  return `${(rate * 100).toFixed(1)}¢/kWh`;
}

type LocationData = {
  address: string;
  postal_code?: string;
  utility_id: string;
  utility_name?: string;
  utility_eia_id?: number;
  utility_rate_avg?: number;
  utility_tier?: number;
};

type Props = {
  initial: LocationData;
  onNext: (data: LocationData) => void;
};

export default function StepLocation({ initial, onNext }: Props) {
  const [address, setAddress] = useState(initial.address);
  const [postalCode, setPostalCode] = useState(initial.postal_code ?? "");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<UtilitySearchResult[] | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [selected, setSelected] = useState<UtilitySearchResult | null>(null);
  const [manualUtility, setManualUtility] = useState(
    initial.utility_id || YAML_UTILITIES[0].id
  );

  // URDB tariff picker
  const [tariffs, setTariffs] = useState<UrdbTariff[] | null>(null);
  const [loadingTariffs, setLoadingTariffs] = useState(false);
  const [selectedTariff, setSelectedTariff] = useState<UrdbTariff | null>(null);

  const [error, setError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nonUS = isLikelyNonUS(postalCode);

  // Auto-extract ZIP from address when the address field loses focus
  function handleAddressBlur() {
    if (!postalCode) {
      const extracted = extractZip(address);
      if (extracted) setPostalCode(extracted);
    }
  }

  // Debounced utility lookup whenever postal code changes
  useEffect(() => {
    const zip = postalCode.replace(/\D/g, "").slice(0, 5);
    if (zip.length < 5) {
      setResults(null);
      setSelected(null);
      setWarning(null);
      setTariffs(null);
      setSelectedTariff(null);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const resp = await api.searchUtilities(zip);
        setResults(resp.utilities);
        setWarning(resp.warning ?? null);
        const auto = resp.utilities.length === 1 ? resp.utilities[0] : null;
        setSelected(auto);
        setTariffs(null);
        setSelectedTariff(null);
        if (auto) fetchTariffs(auto.eia_id);
      } catch {
        setResults([]);
        setWarning(null);
      } finally {
        setSearching(false);
      }
    }, 400);
  }, [postalCode]); // eslint-disable-line react-hooks/exhaustive-deps

  async function fetchTariffs(eiaId: number) {
    setLoadingTariffs(true);
    setTariffs(null);
    setSelectedTariff(null);
    try {
      const resp = await api.listTariffs(eiaId);
      setTariffs(resp.tariffs);
      // Auto-select if there's exactly one tariff
      if (resp.tariffs.length === 1) setSelectedTariff(resp.tariffs[0]);
    } catch {
      setTariffs([]);
    } finally {
      setLoadingTariffs(false);
    }
  }

  function handleSelectUtility(u: UtilitySearchResult) {
    setSelected(u);
    setTariffs(null);
    setSelectedTariff(null);
    fetchTariffs(u.eia_id);
  }

  function handleNext() {
    if (!address.trim()) {
      setError("Please enter your street address.");
      return;
    }
    setError("");

    // Non-US path: can't do utility lookup, proceed with no utility
    if (nonUS) {
      onNext({ address: address.trim(), postal_code: postalCode.trim() || undefined, utility_id: "" });
      return;
    }

    // ZIP lookup returned results
    if (results && results.length > 0) {
      const pick = selected ?? results.find((r) => r.is_primary) ?? results[0];

      if (selectedTariff) {
        // Tier 1 URDB — full TOU schedule available
        onNext({
          address: address.trim(),
          postal_code: postalCode.trim() || undefined,
          utility_id: selectedTariff.utility_id,
          utility_name: pick.utility_name,
          utility_eia_id: pick.eia_id,
          utility_tier: 1,
        });
      } else {
        // Tier 2 flat rate — no URDB tariff selected/available
        onNext({
          address: address.trim(),
          postal_code: postalCode.trim() || undefined,
          utility_id: pick.utility_id,
          utility_name: pick.utility_name,
          utility_eia_id: pick.eia_id,
          utility_rate_avg: pick.residential_rate_avg ?? undefined,
          utility_tier: 2,
        });
      }
      return;
    }

    // No ZIP data — fall back to YAML utility picker
    onNext({
      address: address.trim(),
      postal_code: postalCode.trim() || undefined,
      utility_id: manualUtility,
      utility_tier: 1,
    });
  }

  const showManualFallback =
    !nonUS && (results === null || results.length === 0) && !searching;

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Where are you located?</h2>
      <p className="text-sm text-gray-500 mb-6">
        We use your address for solar irradiance and your ZIP code to find your electric
        utility.
      </p>

      <div className="space-y-4">
        {/* Street address */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Street address
          </label>
          <input
            type="text"
            autoComplete="street-address"
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="123 Main St, Seattle, WA 98101"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onBlur={handleAddressBlur}
            onKeyDown={(e) => e.key === "Enter" && handleNext()}
          />
        </div>

        {/* Postal code */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            ZIP / Postal code
          </label>
          <input
            type="text"
            autoComplete="postal-code"
            inputMode="numeric"
            maxLength={10}
            className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="98101"
            value={postalCode}
            onChange={(e) => setPostalCode(e.target.value)}
          />
        </div>

        {/* Non-US advisory */}
        {nonUS && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
            FlowShift currently supports US addresses only. Carbon intensity and utility
            rate data are unavailable outside the US — solar estimates will still work.
          </div>
        )}

        {/* Utility lookup status */}
        {!nonUS && searching && (
          <p className="text-xs text-gray-400">Finding your utility…</p>
        )}

        {/* Regional advisory (TX retail choice, CA CCA) */}
        {!nonUS && warning && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 text-xs text-amber-800">
            {warning}
          </div>
        )}

        {/* Utility picker — populated from ZIP lookup */}
        {!nonUS && results && results.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5">
              {results.length === 1 ? "Your utility" : "Select your utility"}
            </p>
            <div className="space-y-1.5">
              {results.map((u) => (
                <button
                  key={u.eia_id}
                  type="button"
                  onClick={() => handleSelectUtility(u)}
                  className={`w-full text-left px-3 py-2.5 rounded-xl border text-sm transition-colors ${
                    selected?.eia_id === u.eia_id
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300 bg-white"
                  }`}
                >
                  <span className="font-medium text-gray-900">{u.utility_name}</span>
                  {u.state && <span className="text-gray-400 ml-1.5">{u.state}</span>}
                  {u.residential_rate_avg && (
                    <span className="float-right text-gray-400 text-xs">
                      ~{(u.residential_rate_avg * 100).toFixed(1)}¢/kWh avg
                    </span>
                  )}
                  {u.is_primary && results.length > 1 && (
                    <span className="ml-1.5 text-xs text-blue-500">(most common)</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* URDB tariff picker — shown after a utility is selected */}
        {selected && !loadingTariffs && tariffs && tariffs.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5">
              Rate plan{" "}
              <span className="font-normal text-gray-400">
                — {tariffs.length === 1 ? "1 plan found" : `${tariffs.length} plans found`}
              </span>
            </p>
            <div className="space-y-1.5">
              {tariffs.map((t) => {
                const rates = Object.entries(t.periods).sort(([, a], [, b]) => a - b);
                return (
                  <button
                    key={t.urdb_label}
                    type="button"
                    onClick={() => setSelectedTariff(t)}
                    className={`w-full text-left px-3 py-2.5 rounded-xl border text-sm transition-colors ${
                      selectedTariff?.urdb_label === t.urdb_label
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300 bg-white"
                    }`}
                  >
                    <div className="font-medium text-gray-900 truncate">
                      {t.name ?? t.urdb_label}
                    </div>
                    <div className="flex gap-2 mt-0.5 flex-wrap">
                      {rates.map(([period, rate]) => (
                        <span key={period} className="text-xs text-gray-500">
                          {period.replace("_", "-")}: {fmtCents(rate)}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-gray-400 mt-1.5">
              Selecting a rate plan enables accurate time-of-use pricing (Tier 1). Skip to
              use the flat average rate instead.
            </p>
          </div>
        )}

        {/* Tariff loading indicator */}
        {selected && loadingTariffs && (
          <p className="text-xs text-gray-400">Loading rate plans…</p>
        )}

        {/* Tier 2 notice when no URDB tariffs exist for selected utility */}
        {selected && !loadingTariffs && tariffs?.length === 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-3 py-2 text-xs text-yellow-800">
            No detailed rate plan found — flat average rate will be used. Cost estimates
            will be less precise but still directionally correct.
          </div>
        )}

        {/* Manual utility fallback when ZIP has no data */}
        {showManualFallback && postalCode.length === 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Electric utility
            </label>
            <select
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              value={manualUtility}
              onChange={(e) => setManualUtility(e.target.value)}
            >
              {YAML_UTILITIES.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              Not listed?{" "}
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
        )}

        {/* No utility found for entered ZIP */}
        {showManualFallback && postalCode.length === 5 && results?.length === 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2">
              No utility data found for this ZIP. Select from known utilities:
            </p>
            <select
              className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              value={manualUtility}
              onChange={(e) => setManualUtility(e.target.value)}
            >
              {YAML_UTILITIES.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-end pt-2">
          <Button onClick={handleNext}>Next →</Button>
        </div>
      </div>
    </Card>
  );
}
