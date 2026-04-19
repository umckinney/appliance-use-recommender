"use client";

import { useState } from "react";
import Link from "next/link";
import Card from "@/components/Card";
import Button from "@/components/Button";

type Props = {
  apiKey: string;
  message: string;
};

export default function StepDone({ apiKey, message }: Props) {
  const [copied, setCopied] = useState(false);

  async function copyKey() {
    await navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const siriUrl = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/recommend/dishwasher?api_key=${apiKey}`;

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
            className="shrink-0 text-xs bg-white border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition-colors"
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
        <h3 className="text-sm font-semibold text-blue-800 mb-2">
          📱 Set up Siri on your iPhone
        </h3>
        <ol className="text-sm text-blue-700 space-y-1 list-decimal list-inside">
          <li>Open the Shortcuts app</li>
          <li>Create a new shortcut → Add action → &quot;Get contents of URL&quot;</li>
          <li>
            Set URL to:
            <code className="block text-xs bg-white rounded-lg p-2 mt-1 break-all text-gray-700">
              {siriUrl}
            </code>
          </li>
          <li>Add &quot;Get dictionary from input&quot; → get value for key &quot;text&quot;</li>
          <li>Add &quot;Speak text&quot; — plays on HomePod</li>
          <li>Add to Siri: &quot;Should I run the dishwasher?&quot;</li>
        </ol>
      </div>

      <div className="flex gap-3">
        <Link href={`/dashboard?api_key=${apiKey}`} className="flex-1">
          <Button className="w-full">View dashboard →</Button>
        </Link>
      </div>
    </Card>
  );
}
