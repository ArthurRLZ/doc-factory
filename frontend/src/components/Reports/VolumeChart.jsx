// Volume diário do período (GET /relatorios → volume_diario), em SVG próprio.
import { data } from '../../utils/formatar';

const L = 700;
const A = 160;

export default function VolumeChart({ pontos = [] }) {
  const maior = Math.max(1, ...pontos.map(p => p.total));
  const passo = pontos.length > 1 ? L / (pontos.length - 1) : 0;
  const xy = pontos.map((p, i) => [Math.round(i * passo), Math.round(A - (A - 8) * (p.total / maior))]);
  const linha = xy.map(([x, y]) => `${x},${y}`).join(' ');
  const rotulos = pontos.filter((_, i) => i % Math.max(1, Math.ceil(pontos.length / 7)) === 0);
  const escala = [1, 0.75, 0.5, 0.25, 0].map(f => Math.round(maior * f));

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
          {escala.map((v, i) => <div key={i} className="border-b border-slate-100 pb-1">{v}</div>)}
        </div>
        <svg className="w-full h-full overflow-visible" viewBox={`0 0 ${L} ${A}`} role="img" aria-label="Volume diário de documentos">
          <defs>
            <linearGradient id="gradiente-volume" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.0" />
            </linearGradient>
          </defs>
          {xy.length > 1 && <polygon fill="url(#gradiente-volume)" points={`0,${A} ${linha} ${L},${A}`} />}
          <polyline fill="none" stroke="#6366f1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" points={linha} />
          {xy.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="4" className="fill-white stroke-indigo-600 stroke-2">
            <title>{`${data(pontos[i].data)}: ${pontos[i].total}`}</title>
          </circle>)}
        </svg>
        <div className="flex justify-between text-[11px] text-slate-400 mt-4 px-1">
          {rotulos.map(p => <span key={p.data}>{data(p.data).slice(0, 5)}</span>)}
        </div>
      </div>
    </div>
  );
}
