function rotulo(data) {
  return new Date(`${data}T12:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

export default function VolumeChart({ volume = [] }) {
  const max = Math.max(...volume.map((ponto) => ponto.total), 0);
  const points = volume.map((ponto, index) => ({
    ...ponto,
    x: volume.length > 1 ? (index / (volume.length - 1)) * 700 : 350,
    y: max ? 145 - (ponto.total / max) * 125 : 145,
  }));
  const polyline = points.map(({ x, y }) => `${x},${y}`).join(' ');
  const area = points.length
    ? `0,160 ${polyline} 700,160`
    : '';
  const labels = volume.filter((_, index) => (
    index === 0 || index === volume.length - 1 || index % Math.ceil(volume.length / 6) === 0
  ));

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h4 className="font-bold text-slate-800 text-sm">Volume de documentos</h4>
          <p className="text-xs text-slate-400">Documentos processados ao longo do período</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-indigo-600" />
          <span className="text-xs text-slate-500 font-medium">Processados</span>
        </div>
      </div>

      <div className="relative h-52 w-full pt-4">
        <div className="absolute inset-0 flex flex-col justify-between text-[10px] text-slate-300 pointer-events-none">
          {[1, 0.75, 0.5, 0.25, 0].map((factor) => (
            <div key={factor} className="border-b border-slate-100 pb-1">{Math.round(max * factor)}</div>
          ))}
        </div>

        <svg className="w-full h-full overflow-visible" viewBox="0 0 700 160" role="img" aria-label="Volume diário de documentos">
          <defs>
            <linearGradient id="gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#4f46e5" stopOpacity="0" />
            </linearGradient>
          </defs>
          {points.length > 1 && <polygon fill="url(#gradient)" points={area} />}
          {points.length > 1 && (
            <polyline fill="none" stroke="#6366f1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" points={polyline} />
          )}
          {points.map((point) => (
            <circle key={point.data} cx={point.x} cy={point.y} r="3" className="fill-white stroke-indigo-600 stroke-2">
              <title>{`${rotulo(point.data)}: ${point.total}`}</title>
            </circle>
          ))}
        </svg>
        {!volume.length && <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">Sem documentos no período.</p>}

        <div className="flex justify-between text-[11px] text-slate-400 mt-4 px-1">
          {labels.map((ponto) => <span key={ponto.data}>{rotulo(ponto.data)}</span>)}
        </div>
      </div>
    </div>
  );
}
