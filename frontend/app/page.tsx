import Link from 'next/link'

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-[#0A0B0F] px-6">
      {/* Hero */}
      <div className="text-center mb-14 fade-in">
        <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold tracking-widest uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
          Hackathon Build · VoiceForward GlassBox
        </div>
        <h1 className="text-5xl font-bold tracking-tight text-white mb-4">
          AI Copilot for Crisis Helplines
        </h1>
        <p className="text-slate-400 text-lg max-w-xl mx-auto">
          Real-time multilingual risk assessment, guidance, and dispatch — 
          always human-first, never autonomous.
        </p>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 w-full max-w-3xl mb-12">
        <Link href="/operator/demo_call_001" className="glass p-6 rounded-xl hover:border-indigo-500/30 transition-all hover:-translate-y-1 group">
          <div className="text-2xl mb-3">🎧</div>
          <h2 className="font-semibold text-white mb-1 group-hover:text-indigo-300 transition-colors">Operator HUD</h2>
          <p className="text-slate-400 text-sm">Live call interface with real-time AI guidance</p>
          <div className="mt-4 text-xs text-indigo-400 font-mono">/operator/[callSid] →</div>
        </Link>

        <Link href="/supervisor" className="glass p-6 rounded-xl hover:border-indigo-500/30 transition-all hover:-translate-y-1 group">
          <div className="text-2xl mb-3">📊</div>
          <h2 className="font-semibold text-white mb-1 group-hover:text-indigo-300 transition-colors">Supervisor Board</h2>
          <p className="text-slate-400 text-sm">Live call queue, risk overview, diversions</p>
          <div className="mt-4 text-xs text-indigo-400 font-mono">/supervisor →</div>
        </Link>

        <Link href="/login" className="glass p-6 rounded-xl hover:border-indigo-500/30 transition-all hover:-translate-y-1 group">
          <div className="text-2xl mb-3">🔐</div>
          <h2 className="font-semibold text-white mb-1 group-hover:text-indigo-300 transition-colors">Login</h2>
          <p className="text-slate-400 text-sm">Operator &amp; Supervisor JWT authentication</p>
          <div className="mt-4 text-xs text-indigo-400 font-mono">/login →</div>
        </Link>
      </div>

      {/* Demo quick-launch */}
      <div className="glass p-5 rounded-xl w-full max-w-3xl mb-8">
        <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Demo — Quick Launch
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Scenario 1', desc: 'High-risk Hinglish', sid: 'demo_hinglish_001', color: 'text-red-400' },
            { label: 'Scenario 2', desc: 'DV + Child Crying', sid: 'demo_dv_001', color: 'text-orange-400' },
            { label: 'Scenario 3', desc: 'Conflicting Signals', sid: 'demo_conflict_001', color: 'text-amber-400' },
          ].map(s => (
            <Link key={s.sid} href={`/operator/${s.sid}`}
              className="bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 hover:border-slate-600/50 rounded-lg p-3 transition-all">
              <div className={`text-xs font-semibold ${s.color} mb-0.5`}>{s.label}</div>
              <div className="text-xs text-slate-400">{s.desc}</div>
            </Link>
          ))}
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Run <code className="text-indigo-400 bg-slate-900 px-1 rounded">python demo/simulator.py --scenario high_risk_hinglish</code> to inject live events
        </p>
      </div>

      {/* Ethics footer */}
      <div className="text-xs text-slate-600 text-center">
        <span className="text-indigo-500/70">GlassBox AI</span> · Explainable by design · DPDPA 2023 compliant · Human-first
      </div>
    </main>
  )
}
