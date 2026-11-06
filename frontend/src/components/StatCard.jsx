
export default function StatCard({ title, value, subtext, color = 'indigo' }) {
  const borderColors = {
    indigo: 'border-t-indigo-500',
    red: 'border-t-rose-500',
    amber: 'border-t-amber-500',
    emerald: 'border-t-emerald-500',
  };

  return (
    <div className={`bg-white p-5 rounded-2xl border border-slate-100 shadow-sm border-t-4 ${borderColors[color]}`}>
      <p className="text-xs font-semibold text-slate-500 mb-2">{title}</p>
      <div className="flex items-baseline justify-between">
        <h3 className="text-3xl font-extrabold text-slate-900 tracking-tight">{value}</h3>
      </div>
      <p className="text-xs text-slate-400 mt-3 font-medium">{subtext}</p>
    </div>
  );
}