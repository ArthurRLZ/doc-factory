export default function VolumeChart() {
  const points = [
    { date: '01 Nov', val: 102 },
    { date: '05 Nov', val: 114 },
    { date: '10 Nov', val: 135 },
    { date: '15 Nov', val: 125 },
    { date: '20 Nov', val: 148 },
    { date: '25 Nov', val: 142 },
    { date: '30 Nov', val: 164 },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Volume de documentos</h4>
          <p className="text-xs text-slate-400">Documentos processados ao longo do período</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-indigo-600"></span>
          <span className="text-xs text-slate-500 font-medium">Processados</span>
        </div>
      </div>

      <div className="relative h-52 w-full pt-4">
        <div className="absolute inset-0 flex flex-col justify-between text-[10px] text-slate-300 pointer-events-none">
          <div className="border-b border-slate-100 pb-1">200</div>
          <div className="border-b border-slate-100 pb-1">150</div>
          <div className="border-b border-slate-100 pb-1">100</div>
          <div className="border-b border-slate-100 pb-1">50</div>
          <div className="border-b border-slate-100 pb-1">0</div>
        </div>

        <svg className="w-full h-full overflow-visible" viewBox="0 0 700 160">
          <defs>
            <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          <polygon
            fill="url(#gradient)"
            points="0,160 0,98 116,86 233,65 350,75 466,52 583,58 700,36 700,160"
          />

          <polyline
            fill="none"
            stroke="#6366f1"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            points="0,98 116,86 233,65 350,75 466,52 583,58 700,36"
          />

          {[
            [0, 98],
            [116, 86],
            [233, 65],
            [350, 75],
            [466, 52],
            [583, 58],
            [700, 36],
          ].map(([x, y], i) => (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="4"
              className="fill-white stroke-indigo-600 stroke-2 hover:r-6 transition-all cursor-pointer"
            />
          ))}
        </svg>

        <div className="flex justify-between text-[11px] text-slate-400 mt-4 px-1">
          {points.map((p, idx) => (
            <span key={idx}>{p.date}</span>
          ))}
        </div>
      </div>
    </div>
  );
}