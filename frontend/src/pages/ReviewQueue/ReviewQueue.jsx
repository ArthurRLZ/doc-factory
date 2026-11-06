import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, ChevronLeft, ChevronRight, Clock3, FileText, LoaderCircle, RotateCw } from 'lucide-react';
import Header from '../../components/Header';
import Sidebar from '../../components/Sidebar';
import { useAuth } from '../../context/useAuth';
import api from '../../services/api';

const ITENS_POR_PAGINA = 5;
const buttonBase = 'inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50';

function mensagemErro(error) {
  return error.response?.data?.detail
    || error.response?.data?.erro?.mensagem
    || 'Não foi possível carregar a fila de revisão.';
}

function confiancaPercentual(documento) {
  return Number.isFinite(documento?.confianca) ? Math.round(documento.confianca * 100) : null;
}

function corConfianca(percentual) {
  if (percentual === null) return 'bg-slate-100 text-slate-600';
  if (percentual < 60) return 'bg-rose-50 text-rose-700';
  if (percentual < 80) return 'bg-amber-50 text-amber-700';
  return 'bg-emerald-50 text-emerald-700';
}

export default function ReviewQueue() {
  const { user } = useAuth();
  const [documentos, setDocumentos] = useState([]);
  const [tipos, setTipos] = useState([]);
  const [setorAtivo, setSetorAtivo] = useState('Todos');
  const [documentoId, setDocumentoId] = useState('');
  const [tipoSelecionado, setTipoSelecionado] = useState(null);
  const [pagina, setPagina] = useState(1);
  const [pdfUrl, setPdfUrl] = useState('');
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);

  const carregarFila = useCallback(async () => {
    try {
      const { data } = await api.get('/revisao/fila');
      setDocumentos(data);
      setErro('');
      return data;
    } catch (error) {
      setErro(mensagemErro(error));
      return null;
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    let ativo = true;
    Promise.all([api.get('/revisao/fila'), api.get('/tipos')])
      .then(([fila, tiposResponse]) => {
        if (!ativo) return;
        setDocumentos(fila.data);
        setTipos(tiposResponse.data);
        setErro('');
      })
      .catch((error) => {
        if (ativo) setErro(mensagemErro(error));
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    const timer = setInterval(() => {
      if (ativo) carregarFila();
    }, 8000);
    return () => {
      ativo = false;
      clearInterval(timer);
    };
  }, [carregarFila]);

  const setores = useMemo(
    () => ['Todos', ...new Set(documentos.map((item) => item.setor).filter(Boolean).sort())],
    [documentos],
  );
  const documentosFiltrados = useMemo(() => {
    const filtrados = setorAtivo === 'Todos'
      ? documentos
      : documentos.filter((item) => item.setor === setorAtivo);
    return [...filtrados].sort((a, b) => {
      const confiancaA = a.confianca ?? 1;
      const confiancaB = b.confianca ?? 1;
      return confiancaA - confiancaB;
    });
  }, [documentos, setorAtivo]);
  const totalPaginas = Math.max(1, Math.ceil(documentosFiltrados.length / ITENS_POR_PAGINA));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const inicio = (paginaAtual - 1) * ITENS_POR_PAGINA;
  const documentosPagina = documentosFiltrados.slice(inicio, inicio + ITENS_POR_PAGINA);
  const documento = documentosFiltrados.find((item) => item.id === documentoId) || documentosPagina[0] || null;
  const percentual = confiancaPercentual(documento);
  const documentoAtualId = documento?.id;
  const podeRevisar = user?.perfil === 'revisor' || user?.perfil === 'admin';
  const tipo = documentoAtualId && tipoSelecionado?.documentoId === documentoAtualId
    ? tipoSelecionado.valor
    : documento?.tipo || '';

  useEffect(() => {
    if (!documentoAtualId) return undefined;
    let ativo = true;
    let url = '';
    api.get(`/documentos/${documentoAtualId}/pdf`, { responseType: 'blob' })
      .then(({ data }) => {
        if (!ativo) return;
        url = URL.createObjectURL(data);
        setPdfUrl({ documentoId: documentoAtualId, url });
      })
      .catch((error) => {
        if (ativo) setErro(mensagemErro(error));
      });
    return () => {
      ativo = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentoAtualId]);

  function selecionarSetor(setor) {
    setSetorAtivo(setor);
    setPagina(1);
    setDocumentoId('');
  }

  function selecionarDocumento(item) {
    setDocumentoId(item.id);
  }

  async function revisar(acao, extras = {}) {
    if (!documento || salvando) return;
    setSalvando(true);
    setErro('');
    const indiceAtual = documentosFiltrados.findIndex((item) => item.id === documento.id);
    try {
      await api.post(`/documentos/${documento.id}/revisao`, { acao, ...extras });
      const atualizados = await carregarFila();
      if (atualizados) {
        const proximos = setorAtivo === 'Todos'
          ? atualizados
          : atualizados.filter((item) => item.setor === setorAtivo);
        const ordenados = [...proximos].sort((a, b) => (a.confianca ?? 1) - (b.confianca ?? 1));
        const proximo = ordenados[Math.min(indiceAtual, ordenados.length - 1)];
        setDocumentoId(proximo?.id || '');
        setPagina(Math.floor(Math.max(indiceAtual, 0) / ITENS_POR_PAGINA) + 1);
      }
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setSalvando(false);
    }
  }

  const iniciar = inicio + 1;
  const fim = Math.min(inicio + ITENS_POR_PAGINA, documentosFiltrados.length);

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans antialiased">
      <Sidebar />
      <div className="flex-1 ml-64 flex min-w-0 flex-col">
        <Header />
        <main className="p-5 md:p-8 max-w-7xl w-full mx-auto space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs text-slate-400 font-medium mb-1">Início / Fila de revisão</p>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Fila de revisão</h1>
              <p className="text-sm text-slate-500 mt-1">Confira documentos que precisam de validação antes de serem publicados.</p>
            </div>
            <div className="rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
              <strong className="text-lg">{documentos.length}</strong>
              <span className="ml-2">pendentes</span>
            </div>
          </div>

          {erro && (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              <span>{erro}</span>
              <button type="button" className="inline-flex items-center gap-2 font-semibold underline" onClick={carregarFila}>
                <RotateCw className="h-4 w-4" /> Tentar novamente
              </button>
            </div>
          )}

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <nav aria-label="Filtrar por setor" className="flex flex-wrap gap-1">
                {setores.map((setor) => (
                  <button
                    type="button"
                    key={setor}
                    onClick={() => selecionarSetor(setor)}
                    className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                      setorAtivo === setor ? 'bg-indigo-50 text-indigo-800' : 'text-slate-500 hover:bg-slate-50'
                    }`}
                  >
                    {setor}
                  </button>
                ))}
              </nav>
              <span className="text-xs text-slate-400">Ordenados pela menor confiança</span>
            </div>

            {carregando && documentos.length === 0 ? (
              <div className="flex min-h-72 items-center justify-center gap-2 text-sm text-slate-500">
                <LoaderCircle className="h-4 w-4 animate-spin" /> Carregando fila de revisão...
              </div>
            ) : documentosFiltrados.length === 0 ? (
              <div className="flex min-h-72 flex-col items-center justify-center px-6 text-center">
                <Check className="mb-3 h-9 w-9 rounded-full bg-emerald-50 p-2 text-emerald-600" />
                <h2 className="font-semibold text-slate-800">Fila vazia</h2>
                <p className="mt-1 text-sm text-slate-500">Não há documentos pendentes de revisão{setorAtivo !== 'Todos' ? ` em ${setorAtivo}` : ''}.</p>
              </div>
            ) : (
              <div className="grid min-h-[620px] grid-cols-1 lg:grid-cols-[220px_minmax(0,1fr)_250px]">
                <section className="border-b border-slate-100 lg:border-b-0 lg:border-r">
                  <div className="flex h-10 items-center justify-between border-b border-slate-100 px-3 text-xs">
                    <strong className="text-slate-700">Documentos</strong>
                    <span className="text-slate-400">{documentosFiltrados.length} itens</span>
                  </div>
                  <div className="max-h-72 overflow-y-auto lg:max-h-[570px]">
                    {documentosPagina.map((item) => {
                      const confidence = confiancaPercentual(item);
                      const ativo = documento?.id === item.id;
                      return (
                        <button
                          type="button"
                          key={item.id}
                          onClick={() => selecionarDocumento(item)}
                          className={`flex w-full items-center gap-2 border-b border-slate-100 px-3 py-3 text-left transition-colors ${
                            ativo ? 'border-l-2 border-l-indigo-700 bg-indigo-50/60' : 'hover:bg-slate-50'
                          }`}
                        >
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
                            <FileText className="h-4 w-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-semibold text-slate-800">{item.titulo || item.tipo_nome || 'Documento sem título'}</span>
                            <span className="mt-1 block truncate text-[10px] text-slate-400">{item.codigo} · {item.setor || 'Sem setor'}</span>
                          </span>
                          <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${corConfianca(confidence)}`}>
                            {confidence === null ? '—' : `${confidence}%`}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2 text-[10px] text-slate-500">
                    <span>{documentosFiltrados.length ? `Página ${paginaAtual} de ${totalPaginas}` : 'Página 0 de 0'}</span>
                    <div className="flex gap-1">
                      <button type="button" aria-label="Página anterior" disabled={paginaAtual <= 1} onClick={() => { setPagina(p => p - 1); setDocumentoId(''); }} className="rounded border border-slate-200 p-1 disabled:opacity-40">
                        <ChevronLeft className="h-3 w-3" />
                      </button>
                      <button type="button" aria-label="Próxima página" disabled={paginaAtual >= totalPaginas} onClick={() => { setPagina(p => p + 1); setDocumentoId(''); }} className="rounded border border-slate-200 p-1 disabled:opacity-40">
                        <ChevronRight className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                </section>

                <section className="flex min-h-[440px] flex-col bg-slate-100">
                  <div className="flex h-10 items-center justify-between border-b border-slate-200 bg-white px-4 text-xs text-slate-500">
                    <span>{documento?.codigo || 'Pré-visualização do documento'}</span>
                    <span>{percentual === null ? '—' : `${percentual}% de confiança`}</span>
                  </div>
                  <div className="flex flex-1 items-center justify-center p-4">
                    {pdfUrl?.documentoId === documento?.id ? (
                      <iframe title={`Pré-visualização de ${documento?.titulo || documento?.tipo_nome || 'documento'}`} src={pdfUrl.url} className="h-[520px] w-full max-w-3xl rounded bg-white shadow-lg" />
                    ) : (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        {documento ? <><LoaderCircle className="h-4 w-4 animate-spin" /> Carregando documento...</> : 'Selecione um documento para visualizar.'}
                      </div>
                    )}
                  </div>
                </section>

                <aside className="flex flex-col border-t border-slate-100 lg:border-l lg:border-t-0">
                  <div className="flex-1 space-y-5 p-4">
                    <div>
                      <p className="text-xs font-medium text-slate-500">Análise do documento</p>
                      <p className={`mt-1 text-sm font-bold ${percentual !== null && percentual < 70 ? 'text-amber-700' : 'text-slate-800'}`}>
                        {percentual === null ? 'Confiança não informada' : `${percentual}% de confiança`}
                      </p>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div className={`h-full ${percentual !== null && percentual < 70 ? 'bg-amber-400' : 'bg-indigo-500'}`} style={{ width: `${percentual ?? 0}%` }} />
                      </div>
                    </div>

                    {documento && (
                      <>
                        <label className="block text-xs font-medium text-slate-600">
                          Tipo do documento
                          <select
                            aria-label="Tipo do documento"
                            disabled={!podeRevisar}
                            value={tipo}
                            onChange={(event) => setTipoSelecionado({ documentoId: documento.id, valor: event.target.value })}
                            className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-normal"
                          >
                            {!tipos.some((item) => item.codigo === tipo) && <option value={tipo}>{documento.tipo_nome || tipo}</option>}
                            {tipos.map((item) => <option key={item.codigo} value={item.codigo}>{item.nome}</option>)}
                          </select>
                        </label>

                        <div className="space-y-2 border-t border-slate-100 pt-4 text-xs">
                          <p className="font-semibold text-slate-700">Informações detectadas</p>
                          <p className="text-slate-500">Setor: {documento.setor || 'Não classificado'}</p>
                          <p className="text-slate-500">Páginas: {documento.pagina_inicio + 1}–{documento.pagina_fim + 1}</p>
                          <p className="text-slate-500">Prioridade: {documento.prioridade || 'Não informada'}</p>
                          {documento.motivos?.length > 0 && (
                            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-800">
                              <span className="mb-1 flex items-center gap-1 font-semibold"><Clock3 className="h-3 w-3" /> Motivo da revisão</span>
                              {documento.motivos.join('; ')}
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex gap-2 border-t border-slate-100 p-3">
                    <button
                      type="button"
                      disabled={!documento || salvando}
                      onClick={() => {
                        const next = documentosFiltrados[documentosFiltrados.findIndex((item) => item.id === documento?.id) + 1];
                        if (next) setDocumentoId(next.id);
                        else if (paginaAtual < totalPaginas) {
                          setPagina(paginaAtual + 1);
                          setDocumentoId('');
                        }
                      }}
                      className={`${buttonBase} flex-1 border-slate-200 text-slate-600 hover:bg-slate-50`}
                    >
                      Pular
                    </button>
                    <button
                      type="button"
                      disabled={!documento || salvando || !podeRevisar}
                      onClick={() => revisar(tipo === documento?.tipo ? 'aprovar' : 'alterar_tipo', tipo === documento?.tipo ? {} : { tipo })}
                      className={`${buttonBase} flex-[2] border-indigo-950 bg-indigo-950 text-white hover:bg-indigo-900`}
                    >
                      {salvando ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                      {salvando ? 'Salvando...' : 'Confirmar e continuar'}
                    </button>
                  </div>
                  {documento && !podeRevisar && (
                    <p className="px-3 pb-3 text-[11px] text-amber-700">
                      Seu perfil permite consultar a fila, mas para revisar é necessário acesso de revisor ou administrador.
                    </p>
                  )}
                </aside>
              </div>
            )}
          </section>
          {documentosFiltrados.length > 0 && (
            <p className="text-xs text-slate-400">Exibindo {iniciar}–{fim} de {documentosFiltrados.length} documentos pendentes.</p>
          )}
        </main>
      </div>
    </div>
  );
}
