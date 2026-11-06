// Busca dados da API com os três estados que toda tela precisa: carregando, erro e dados.
// `intervalo` (ms) refaz a busca periodicamente (lote processando, portal); `recarregar()` força uma nova busca.
import { useCallback, useEffect, useState } from 'react';
import { mensagemDeErro } from '../utils/formatar';

export default function useApi(buscarDados, deps = [], { intervalo } = {}) {
  const [estado, setEstado] = useState({ dados: null, erro: null, carregando: true });
  const [versao, setVersao] = useState(0);
  const recarregar = useCallback(() => setVersao(v => v + 1), []);

  useEffect(() => {
    let vivo = true;
    async function buscar() {
      try {
        const dados = await buscarDados();
        if (vivo) setEstado({ dados, erro: null, carregando: false });
      } catch (e) {
        if (vivo) setEstado(s => ({ dados: s.dados, erro: mensagemDeErro(e), carregando: false }));
      }
    }
    const primeira = setTimeout(buscar, 0);
    const timer = intervalo ? setInterval(buscar, intervalo) : null;
    return () => { vivo = false; clearTimeout(primeira); if (timer) clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao, intervalo]);

  return { ...estado, recarregar };
}
