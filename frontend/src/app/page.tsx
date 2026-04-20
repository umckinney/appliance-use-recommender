import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-slate-100 flex items-center justify-center p-6">
      <div className="max-w-lg text-center">
        <div className="text-6xl mb-4">⚡</div>
        <h1 className="text-4xl font-bold text-gray-900 mb-3">FlowShift</h1>
        <p className="text-lg text-gray-600 mb-2">
          Run your appliances at the cheapest, cleanest time.
        </p>
        <p className="text-sm text-gray-400 mb-10">
          Real-time grid carbon intensity + utility TOU rates + your solar generation
          — delivered to Siri on your HomePod.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/onboard"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl shadow transition-colors"
          >
            Get started →
          </Link>
          <a
            href="https://github.com/umckinney/appliance-use-recommender"
            target="_blank"
            rel="noreferrer"
            className="px-6 py-3 bg-white hover:bg-gray-50 text-gray-700 font-medium rounded-xl border border-gray-200 shadow-sm transition-colors"
          >
            View on GitHub
          </a>
        </div>

        <div className="mt-16 grid grid-cols-3 gap-6 text-left">
          {[
            {
              icon: "🌱",
              title: "Grid-aware",
              body: "Live BPA carbon data for Seattle — EIA for the rest of the US.",
            },
            {
              icon: "☀️",
              title: "Solar-native",
              body: "SolarEdge live output or irradiance-based forecast. Net metering credit applied.",
            },
            {
              icon: "🎙️",
              title: "Siri-ready",
              body: '"Should I run the dishwasher?" — spoken answer on your HomePod in seconds.',
            },
          ].map(({ icon, title, body }) => (
            <div key={title}>
              <div className="text-2xl mb-2">{icon}</div>
              <h3 className="text-sm font-semibold text-gray-800 mb-1">{title}</h3>
              <p className="text-xs text-gray-500 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
