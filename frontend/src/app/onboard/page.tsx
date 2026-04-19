"use client";

import { useState } from "react";
import Link from "next/link";
import { api, OnboardPayload } from "@/lib/api";
import StepIndicator from "@/components/StepIndicator";
import StepLocation from "@/components/wizard/StepLocation";
import StepSolar from "@/components/wizard/StepSolar";
import StepAppliances from "@/components/wizard/StepAppliances";
import StepPreferences from "@/components/wizard/StepPreferences";
import Spinner from "@/components/Spinner";
import StepDone from "@/components/wizard/StepDone";

function RecoveryPanel() {
  const [open, setOpen] = useState(false);
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
    <div className="text-center text-sm text-gray-500 mb-6 space-y-1">
      <p>
        Already have an API key?{" "}
        <Link
          href="/dashboard"
          className="text-blue-600 hover:underline font-medium"
        >
          Go to dashboard →
        </Link>
      </p>
      <p>
        <button
          onClick={() => { setOpen((o) => !o); setFoundKey(""); setNotFound(false); }}
          className="text-blue-600 hover:underline font-medium"
        >
          Registered before? Recover your key →
        </button>
      </p>
      {open && (
        <div className="mt-3 bg-white border border-gray-200 rounded-xl p-4 text-left shadow-sm">
          <p className="text-xs font-medium text-gray-600 mb-2">Enter your registered email:</p>
          <div className="flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLookup()}
              placeholder="you@example.com"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleLookup}
              disabled={loading}
              className="shrink-0 text-sm bg-blue-600 text-white rounded-lg px-4 py-1.5 hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? "…" : "Find my key"}
            </button>
          </div>
          {notFound && (
            <p className="text-xs text-red-500 mt-2">No account found for that email.</p>
          )}
          {foundKey && (
            <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3">
              <p className="text-xs text-green-700 font-medium mb-1">Found your account!</p>
              <code className="text-xs font-mono text-gray-800 break-all">{foundKey}</code>
              <div className="mt-2">
                <Link
                  href={`/dashboard?api_key=${encodeURIComponent(foundKey)}`}
                  className="text-xs text-blue-600 hover:underline font-medium"
                >
                  Go to dashboard →
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const STEPS = ["Location", "Solar", "Appliances", "Preferences"];

type WizardState = OnboardPayload & {
  appliances: NonNullable<OnboardPayload["appliances"]>;
};

const DEFAULT_STATE: WizardState = {
  address: "",
  utility_id: "seattle_city_light",
  has_solar: false,
  net_metering: false,
  optimization_weight: 0.5,
  appliances: [],
};

export default function OnboardPage() {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(DEFAULT_STATE);
  const [result, setResult] = useState<{ api_key: string; message: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function merge(patch: Partial<WizardState>) {
    setState((s) => ({ ...s, ...patch }));
  }

  async function submit(prefs: { name?: string; email?: string; optimization_weight: number }) {
    merge(prefs);
    setSubmitting(true);
    setError("");
    try {
      const payload: OnboardPayload = { ...state, ...prefs };
      const res = await api.onboard(payload);
      setResult(res);
      setStep(4); // done step
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-slate-100 flex items-start justify-center p-4 pt-12">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">⚡ FlowShift</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Run appliances at the cheapest, cleanest time
          </p>
        </div>

        {step < 4 && <RecoveryPanel />}
        {step < 4 && <StepIndicator steps={STEPS} current={step} />}

        {step === 0 && (
          <StepLocation
            initial={{ address: state.address, utility_id: state.utility_id }}
            onNext={(d) => {
              merge(d);
              setStep(1);
            }}
          />
        )}

        {step === 1 && (
          <StepSolar
            initial={{
              has_solar: state.has_solar ?? false,
              net_metering: state.net_metering ?? false,
              solar_capacity_kw: state.solar_capacity_kw,
              solar_tilt_deg: state.solar_tilt_deg,
              solar_azimuth_deg: state.solar_azimuth_deg,
              solaredge_site_id: state.solaredge_site_id,
              solaredge_api_key: state.solaredge_api_key,
            }}
            onNext={(d) => {
              merge(d);
              setStep(2);
            }}
            onBack={() => setStep(0)}
          />
        )}

        {step === 2 && (
          <StepAppliances
            initial={state.appliances}
            onNext={(appliances) => {
              merge({ appliances });
              setStep(3);
            }}
            onBack={() => setStep(1)}
          />
        )}

        {step === 3 && (
          <>
            <StepPreferences
              initial={{
                name: state.name,
                email: state.email,
                optimization_weight: state.optimization_weight ?? 0.5,
              }}
              onNext={submit}
              onBack={() => setStep(2)}
            />
            {submitting && (
              <div className="flex items-center justify-center gap-2 mt-4 text-sm text-gray-500">
                <Spinner size="sm" />
                Creating your account…
              </div>
            )}
            {error && (
              <p className="text-center text-sm text-red-500 mt-4">{error}</p>
            )}
          </>
        )}

        {step === 4 && result && (
          <StepDone apiKey={result.api_key} message={result.message} appliances={state.appliances} />
        )}
      </div>
    </main>
  );
}
