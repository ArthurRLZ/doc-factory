# API do Document Factory — guia para o front

**Base:** `http://localhost:8000` (sem `/api`). Swagger interativo: `http://localhost:8000/docs`.
No front: `frontend/src/services/api.js` → `baseURL: 'http://localhost:8000'`.

CORS já libera `http://localhost:5173` (Vite) e `http://localhost:4200`. Para outra porta, ajuste
`CORS_ORIGINS` no `.env` do backend.

## Convenções

- **Datas:** ISO (`2026-11-05`, `2026-11-05T21:40:07`). Formate no front.
- **Prioridade:** `"alta" | "media" | "baixa"` (sem acento). Rótulo: `alta → Alta`, `media → Média`, `baixa → Baixa`.
- **Listas paginadas:** `{ total, pagina, por_pagina, paginas, itens: [...] }` (página começa em 1).
- **Erros:** sempre `{ "erro": { "codigo": 404, "mensagem": "Documento não encontrado", "detalhe": null } }`.
  Mostre `erro.mensagem` para o usuário. Em 422, `erro.detalhe` é a lista `[{campo, mensagem}]`.
- **Login** (só se `AUTH_ATIVO=true` no backend): `POST /auth/login` (form `username`, `password`) →
  `{access_token, perfil}`; envie `Authorization: Bearer <token>`. Com login desligado, nada é exigido.

## Documento (formato usado em todas as telas)

```json
{
  "id": "3913a49ebc534dfba859ee635837a47a",
  "codigo": "DOC-2026-3913A4",
  "titulo": "ATESTADO DE SAÚDE OCUPACIONAL - ASO",
  "tipo": "ASO", "tipo_nome": "Atestado de Saúde Ocupacional (ASO)",
  "setor": "Segurança do Trabalho",
  "prioridade": "alta", "prioridade_motivo": "documento vencido há 31 dia(s)",
  "status_revisao": "auto_aprovado | pendente | revisado",
  "confianca": 0.95, "motivos": [],
  "validade": {
    "data": "2026-10-05", "inicio": "2025-10-05",
    "status": "vigente | vencendo | vencido | indeterminado | sem_validade",
    "dias_restantes": -31,
    "origem": "texto | modelo | regra",
    "evidencia": "Data do exame: 05/10/2025  →  regra: validade de 12 meses"
  },
  "resumo": "…", "resumo_origem": "modelo | simples", "campos": {"resultado": "APTO", "…": "…"},
  "lote_id": "…", "ordem": 0, "pagina_inicio": 0, "pagina_fim": 0, "n_paginas": 1,
  "criado_em": "2026-11-05T22:10:00"
}
```

Texto do prazo na tabela ("Vence em 2 dias", "No prazo"…), a partir de `validade`:
`vencido` → "Vencido há N dias" · `vencendo` → "Vence em N dias" (0 = "Vence hoje") · `vigente` → "No prazo" ·
`indeterminado` → "Validade não identificada" · `sem_validade` → "—".

## Tela "Visão geral" → `GET /painel` (uma chamada)

| Componente | Campo da resposta |
|---|---|
| StatCard "Documentos ativos" | `cartoes.documentos_ativos.valor` · subtexto `este_mes` |
| StatCard "Vencem esta semana" | `cartoes.vencem_semana.valor` · `vencem_hoje` · `vencidos` |
| StatCard "Aguardando revisão" | `cartoes.aguardando_revisao.valor` · `alta_prioridade` |
| StatCard "Analisados com sucesso" | `cartoes.analisados_sem_revisao.percentual` (%) |
| ChartSection (7 dias) | `volume_7_dias.dias[] = {data, rotulo ("Seg"… "Hoje"), total}` · `variacao_semana_anterior` (% ou null) |
| AttentionSection | `atencao[] = {tipo, gravidade (alta/media/ok), total, titulo, subtitulo, acao, rota}` |
| RecentDocuments | `recentes[]` (documentos; use `titulo`, `tipo_nome`, `setor`, `prioridade`, `criado_em`) |
| SectorDistribution | `por_setor[] = {setor, total, percentual}` (largura da barra = `percentual`) |
| Sidebar (badge da fila) | `fila_revisao` |

## Tela "Documentos" → `GET /documentos`

Parâmetros (todos opcionais): `setor`, `prioridade`, `tipo`, `prazo`, `q` (busca), `status_revisao`, `lote_id`,
`ordenar` (`recentes` | `prazo` | `prioridade` | `confianca`), `pagina`, `por_pagina` (máx. 200).

`prazo`: `vencido` · `vencendo` (até 30 dias) · `esta_semana` (até 7 dias) · `vigente` · `indeterminado` · `sem_validade`.

| Componente | Origem |
|---|---|
| DocumentsFilter "Setores" | `GET /setores` → `[{setor, tipos}]` |
| DocumentsFilter "Tipos" | `GET /tipos` → `[{codigo, nome, descricao, prioridade, campos, validade}]` |
| DocumentsFilter "Prioridades" / "Prazos" | valores fixos acima |
| DocumentsTable | `itens[]`: `codigo`, `titulo`, `tipo_nome`, `setor`, `validade.data` + texto do prazo, `prioridade` |
| DocumentsMetrics | de `/painel`: `cartoes.vencem_semana`, `cartoes.aguardando_revisao`, `processados_hoje` |
| Abrir PDF | `GET /documentos/{id}/pdf` (anonimizado) · `?anonimizado=false` (original, perfil revisor) |
| Detalhe | `GET /documentos/{id}` · auditoria: `GET /documentos/{id}/revisoes` |

## Tela "Fila de revisão"

- Lista: `GET /revisao/fila` (prioridade alta primeiro, depois menor confiança). Mostre `motivos`.
- Miniaturas das páginas: `GET /lotes/{lote_id}/paginas/{n}/imagem` (de `pagina_inicio` a `pagina_fim`).
- Ações: `POST /documentos/{id}/revisao` com
  `{"acao": "aprovar"}` · `{"acao": "alterar_tipo", "tipo": "ASO"}` · `{"acao": "alterar_prioridade", "prioridade": "alta"}` ·
  `{"acao": "dividir", "pagina_corte": 6}` · `{"acao": "juntar_proximo"}`. Devolve os documentos afetados.

## Tela "Relatórios" → `GET /relatorios?dias=30`

| Componente | Campo |
|---|---|
| ReportsMetrics | `metricas.documentos_processados {valor, variacao}` · `metricas.tempo_medio_analise_segundos` · `metricas.concluidos_sem_revisao {percentual, variacao_pontos}` · `metricas.enviados_para_revisao.valor` |
| PriorityDonutChart | `por_prioridade[] = {prioridade, total, percentual}` |
| SectorVolume | `por_setor[]` |
| StatusPrazos | `status_prazos[] = {status, rotulo ("No prazo", "Vencem em breve", "Vencidos"), total, percentual}` |
| VolumeChart | `volume_diario[] = {data, total}` |

## Envio de lote (upload)

```js
const form = new FormData();
form.append('arquivo', file);              // PDF, TIFF, PNG ou JPG (até 2 GB)
form.append('prioridade', 'alta');         // opcional: alta | media | baixa
const { data: lote } = await api.post('/lotes', form, {
  headers: { 'Content-Type': 'multipart/form-data' },
  onUploadProgress: e => setProgresso(e.loaded / e.total),
});
// acompanhe: GET /lotes/{lote.id} a cada 2 s até status === 'concluido' (campo progresso: 0 a 1)
// 409 = arquivo já enviado (erro.detalhe.lote_id traz o lote existente)
```

Outros: `GET /lotes` (lista) · `GET /lotes/{id}/documentos` · `GET /lotes/{id}/zip` (todos os PDFs + manifesto) ·
`GET /vencimentos?ate_dias=30` · `GET /busca?q=` · `GET /health`.

## Meta de automação (para o pitch e para uma tela de configuração)

- `GET /automacao` → `{limiar_atual, curva: [{limiar, automaticos, para_revisao, percentual_automatico,
  acuracia_estimada (null sem amostra), amostra, atual}], acuracia_medida: {documentos_revisados, corretos, percentual}}`.
  Gráfico sugerido: eixo X = limiar, barras = `percentual_automatico`, linha = `acuracia_estimada`.
- `GET /automacao/sugerir?meta=95` → menor limiar que atinge a acurácia-meta pelas revisões já feitas.
- `PUT /automacao/limiar` (admin) `{"limiar": 0.85, "aplicar": true}` → muda na hora e reavalia a fila.

A acurácia é **medida** pelas revisões humanas (aprovado sem mudança = acerto; tipo trocado, dividido ou
juntado = erro). Sem revisões suficientes ela vem `null` — o sistema não inventa número.

## Dossiê do trabalhador e checklist (tela sugerida: "Trabalhadores")

O trabalhador é identificado pela **impressão digital do CPF** — o CPF não é guardado; para exibir use
`cpf_mascarado` (`***.982.247-**`). Cada documento traz `trabalhador: {id, rotulo, cpf_mascarado}` ou `null`
(documentos da empresa, como certidões, não têm trabalhador).

- `GET /trabalhadores?lote_id=&situacao=` → `{total, irregulares, exigidos, itens: [{id, rotulo, cpf_mascarado,
  documentos, situacao (regular | atencao | irregular), pendencias, faltando: [tipos], vencidos, vencendo}]}`
  (irregulares primeiro).
- `GET /trabalhadores/{id}/dossie` → o resumo acima + `checklist: [{tipo, tipo_nome, status (ok | faltando |
  vencido | vencendo | indeterminado), documento_id, validade, observacao}]` + `outros_alertas` (ex.: certificado
  de NR vencendo) + `duplicados` + `itens` (documentos da pessoa).
- `/painel` traz `trabalhadores_irregulares` e um item em `atencao` com `tipo: "trabalhadores_irregulares"`.

Documentos exigidos: `DOCUMENTOS_EXIGIDOS_TRABALHADOR` em `backend/app/tipos.py` (identidade, CTPS, ASO, ficha de EPI).
