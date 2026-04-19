"use client";

import { useState } from "react";
import Link from "next/link";
import Card from "@/components/Card";
import Button from "@/components/Button";

type Appliance = { name: string; slug: string };

type Props = {
  apiKey: string;
  message: string;
  appliances?: Appliance[];
};

export default function StepDone({ apiKey, message, appliances = [] }: Props) {
  const defaultSlug = appliances[0]?.slug ?? "dishwasher";
  const defaultName = appliances[0]?.name ?? "dishwasher";

  const [copied, setCopied] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [selectedSlug, setSelectedSlug] = useState(defaultSlug);

  const selectedName =
    appliances.find((a) => a.slug === selectedSlug)?.name ?? selectedSlug;

  async function copyKey() {
    await navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const siriUrl = `${baseUrl}/recommend/${selectedSlug}?api_key=${apiKey}`;

  async function copySiriUrl() {
    await navigator.clipboard.writeText(siriUrl);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  }

  return (
    <Card>
      <div className="text-center mb-6">
        <div className="text-4xl mb-3">🎉</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">You&apos;re all set!</h2>
        <p className="text-sm text-gray-500">{message}</p>
      </div>

      {/* API key */}
      <div className="bg-gray-50 rounded-xl p-4 mb-6">
        <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
          Your API key
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-sm font-mono text-gray-800 break-all">{apiKey}</code>
          <button
            onClick={copyKey}
            className="shrink-0 text-xs text-gray-700 bg-white border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            {copied ? "✓ Copied" : "Copy"}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Save this — it&apos;s your permanent access key. Share it with household members
          to use the same profile.
        </p>
      </div>

      {/* Siri setup */}
      <div className="border border-blue-100 bg-blue-50 rounded-xl p-4 mb-6">
        <h3 className="text-sm font-semibold text-blue-800 mb-3">
          📱 Set up Siri on your iPhone
        </h3>

        {/* Appliance selector */}
        {appliances.length > 1 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {appliances.map((a) => (
              <button
                key={a.slug}
                onClick={() => setSelectedSlug(a.slug)}
                className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                  selectedSlug === a.slug
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-blue-700 border-blue-300 hover:bg-blue-100"
                }`}
              >
                {a.name}
              </button>
            ))}
          </div>
        )}

        <ol className="text-sm text-blue-700 space-y-1.5 list-decimal list-inside mb-3">
          <li>Open the <strong>Shortcuts</strong> app</li>
          <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;URL&quot; → tap <strong>Get contents of URL</strong></li>
          <li>
            Paste this URL into the URL field:
            <div className="flex items-start gap-2 mt-1">
              <code className="flex-1 text-xs bg-white rounded-lg p-2 break-all text-gray-700">
                {siriUrl}
              </code>
              <button
                onClick={copySiriUrl}
                className="shrink-0 text-xs text-gray-700 bg-white border border-gray-300 rounded-lg px-2 py-1.5 hover:bg-gray-50 transition-colors"
              >
                {copiedUrl ? "✓" : "Copy"}
              </button>
            </div>
          </li>
          <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;dictionary&quot; → tap <strong>Get Dictionary from Input</strong></li>
          <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;dictionary&quot; → tap <strong>Get Dictionary Value</strong> → set Key to <strong>text</strong></li>
          <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;speak&quot; → tap <strong>Speak Text</strong></li>
          <li>Tap the shortcut title at the top → rename to <strong>Should I run the {selectedName}?</strong></li>
          <li>Say &quot;Hey Siri, should I run the {selectedName}?&quot;</li>
        </ol>

        <p className="text-xs text-blue-600">
          This URL only works on the same Wi-Fi network as this computer. For always-available
          access, deploy to Fly.io and update the URL to your production address.
        </p>
      </div>

      <div className="flex gap-3">
        <Link href={`/dashboard?api_key=${apiKey}`} className="flex-1">
          <Button className="w-full">View dashboard →</Button>
        </Link>
      </div>
    </Card>
  );
}
