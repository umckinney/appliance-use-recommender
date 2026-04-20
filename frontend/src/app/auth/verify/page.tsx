"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Phase = "loading" | "error";

function VerifyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setErrorMsg("Missing sign-in token.");
      setPhase("error");
      return;
    }
    // The backend redirect happens server-side; if the user lands here via the
    // frontend route (not the backend URL), redirect them to the backend verify endpoint.
    // In production the magic link points directly at the backend /auth/magic-link/verify
    // which issues a redirect → /dashboard. This page is a fallback in case the frontend
    // intercepts the route.
    window.location.href = `${BASE}/auth/magic-link/verify?token=${encodeURIComponent(token)}`;
  }, [params, router]);

  if (phase === "error") {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="text-center space-y-4">
          <h1 className="text-xl font-semibold text-gray-900">Invalid link</h1>
          <p className="text-sm text-gray-600">{errorMsg}</p>
          <a href="/auth/login" className="inline-block text-sm text-blue-600 hover:underline">
            Return to sign in
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm text-gray-600">Signing you in…</p>
      </div>
    </main>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
