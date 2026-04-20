"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import QRCode from "qrcode";
import Card from "@/components/Card";
import Button from "@/components/Button";
import { api } from "@/lib/api";

type Appliance = { name: string; slug: string };

type Props = {
  apiKey: string;
  message: string;
  appliances?: Appliance[];
};

const ALL_OPTION: Appliance = { name: "All Appliances", slug: "all" };

function QRCodeDisplay({ url }: { url: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, url, { width: 160, margin: 1 });
    }
  }, [url]);

  return <canvas ref={canvasRef} className="rounded-lg" />;
}

export default function StepDone({ apiKey, message, appliances = [] }: Props) {
  const options: Appliance[] = appliances.length > 1
    ? [...appliances, ALL_OPTION]
    : appliances;

  const defaultSlug = appliances[0]?.slug ?? "dishwasher";
  const [selectedSlug, setSelectedSlug] = useState(defaultSlug);
  const [copied, setCopied] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [showQR, setShowQR] = useState(false);

  const selectedName = options.find((a) => a.slug === selectedSlug)?.name ?? selectedSlug;

  async function copyKey() {
    await navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function getApiBase(): string {
    if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
    if (typeof window === "undefined") return "http://localhost:8000";
    const host = window.location.hostname;
    return host === "localhost" || host === "127.0.0.1"
      ? "http://localhost:8000"
      : `http://${host}:8000`;
  }

  const baseUrl = getApiBase();
  const isLocalhost = baseUrl.includes("localhost") || baseUrl.includes("127.0.0.1");
  const isCloud = !!process.env.NEXT_PUBLIC_API_URL && !isLocalhost;

  const recommendEndpoint = selectedSlug === "all" ? "recommend/all" : `recommend/${selectedSlug}`;
  const siriUrl = `${baseUrl}/${recommendEndpoint}?api_key=${apiKey}`;
  const shortcutDownloadUrl = api.getShortcutUrl(selectedSlug, apiKey);
  const shortcutImportUrl = `shortcuts://import-workflow?url=${encodeURIComponent(shortcutDownloadUrl)}`;

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
        {options.length > 1 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {options.map((a) => (
              <button
                key={a.slug}
                onClick={() => { setSelectedSlug(a.slug); setShowQR(false); }}
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

        {/* Quick setup: Download Shortcut */}
        {isCloud && (
          <div className="mb-4">
            <p className="text-xs text-blue-700 font-medium mb-2">Quick setup</p>
            <div className="flex gap-2">
              <a
                href={shortcutDownloadUrl}
                download
                className="text-xs bg-blue-600 text-white rounded-lg px-3 py-2 hover:bg-blue-700 transition-colors"
              >
                ↓ Download Shortcut
              </a>
              <a
                href={shortcutImportUrl}
                className="text-xs bg-white text-blue-700 border border-blue-300 rounded-lg px-3 py-2 hover:bg-blue-50 transition-colors"
              >
                Open in Shortcuts
              </a>
            </div>

            {/* QR code (collapsible) */}
            <div className="mt-3">
              <button
                onClick={() => setShowQR((v) => !v)}
                className="text-xs text-blue-600 underline underline-offset-2"
              >
                {showQR ? "Hide QR code" : "Show QR code (scan on iPhone)"}
              </button>
              {showQR && (
                <div className="mt-2">
                  <QRCodeDisplay url={shortcutImportUrl} />
                  <p className="text-xs text-gray-400 mt-1">
                    Keep this URL private — it contains your API key.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Manual setup steps */}
        <details className={isCloud ? "mt-2" : undefined}>
          {isCloud && (
            <summary className="text-xs text-blue-600 cursor-pointer mb-2">
              Manual setup (7 steps)
            </summary>
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
              {isLocalhost && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 mt-1.5">
                  ⚠️ This URL won&apos;t work on your iPhone. Visit this page at{" "}
                  <strong>http://&lt;your-mac-ip&gt;:3000</strong> to get a usable URL.
                  Find your Mac&apos;s IP in{" "}
                  <strong>System Settings → Wi-Fi → Details</strong>.
                </p>
              )}
            </li>
            <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;dictionary&quot; → tap <strong>Get Dictionary from Input</strong></li>
            <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;dictionary&quot; → tap <strong>Get Dictionary Value</strong> → set Key to <strong>text</strong></li>
            <li>Tap <strong>+</strong> → <strong>Add Action</strong> → search &quot;speak&quot; → tap <strong>Speak Text</strong></li>
            <li>Rename to <strong>Should I run the {selectedName}?</strong></li>
          </ol>
        </details>

        {!isCloud && (
          <p className="text-xs text-blue-600">
            For always-available access, deploy to Fly.io and update the URL to your
            production address.
          </p>
        )}
      </div>

      <div className="flex gap-3">
        <Link href={`/dashboard?api_key=${apiKey}`} className="flex-1">
          <Button className="w-full">View dashboard →</Button>
        </Link>
      </div>
    </Card>
  );
}
