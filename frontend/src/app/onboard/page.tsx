"use client";

import { useState } from "react";
import { api, OnboardPayload } from "@/lib/api";
import StepIndicator from "@/components/StepIndicator";
import StepLocation from "@/components/wizard/StepLocation";
import StepSolar from "@/components/wizard/StepSolar";
import StepAppliances from "@/components/wizard/StepAppliances";
import StepPreferences from "@/components/wizard/StepPreferences";
import StepDone from "@/components/wizard/StepDone";

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
              <p className="text-center text-sm text-gray-500 mt-4">
                Creating your account…
              </p>
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
