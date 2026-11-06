import { Search, ChevronDown } from 'lucide-react';

export default function DocumentsFilters() {
  const filterOptions = [
    { label: 'Todos: Setores' },
    { label: 'Todos: Prioridades' },
    { label: 'Todos: Tipos' },
    { label: 'Todos: Prazos' },
  ];

  return (
    <div className="bg-white p-4 rounded-t-2xl border border-slate-100 border-b-0 flex flex-col md:flex-row md:items-center justify-between gap-4">
      {/* Dropdown Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        {filterOptions.map((filter, idx) => (
          <button
            key={idx}
            className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-600 font-medium hover:bg-slate-100 transition-colors"
          >
            <span>{filter.label}</span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>
        ))}
      </div>

      {/* Search Input */}
      <div className="relative w-full md:w-64">
        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Buscar nesta lista"
          className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-8 pr-3 py-1.5 text-xs outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 placeholder:text-slate-400"
        />
      </div>
    </div>
  );
}