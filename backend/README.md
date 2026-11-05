# Document Factory — backend

Hack Garanhuns Tech 2026 · Desafio 3. Recebe lotes digitalizados grandes (PDF/TIFF), separa cada
documento, classifica o tipo, gera PDF pesquisável e anonimizado e manda as dúvidas para revisão humana.

**Stack:** FastAPI · PyMuPDF · Tesseract (`por`) · SQLAlchemy (SQLite no dev, PostgreSQL em produção) ·
storage local ou MinIO/S3 · modelo plugável (qualquer API compatível com OpenAI).

## Rodar em 1 minuto (sem Docker)

```bash
sudo apt install tesseract-ocr tesseract-ocr-por        # Windows: instalador UB-Mannheim + por.traineddata
pip install -r requirements.txt
cp .env.example .env                                    # WORKER_INLINE=true → API + worker num processo só
uvicorn app.main:app --reload                           # http://localhost:8000/docs
python scripts/gerar_lote_teste.py lote_teste.pdf       # lote falso de 11 páginas / 6 documentos
curl -F arquivo=@lote_teste.pdf http://localhost:8000/lotes
pytest -q                                               # 7 testes, inclui ponta a ponta
```

## Rodar a stack completa

```bash
docker compose up --build --scale worker=3              # Postgres + MinIO (console :9001) + API + 3 workers
```

## Estrutura

```
app/
  main.py              FastAPI, CORS, API key, /health, /metricas
  config.py            todas as configurações (env/.env)
  db.py · models.py    Lote, Pagina, Documento, Revisao (+ índice GIN full-text pt no Postgres)
  storage.py           LocalStorage | S3Storage (MinIO) — banco guarda só a chave
  tipos.py             ← TAXONOMIA: troquem pelos 5 tipos reais do desafio
  worker.py            fila por página, retomada após falha, SKIP LOCKED
  api/lotes.py         upload em streaming, progresso, páginas, miniaturas, reprocessar
  api/documentos.py    documentos, PDF, fila de revisão, dividir/juntar, busca
  llm/                 interface + cliente OpenAI-compatível (OpenAI, Gemini, DeepSeek, Ollama…)
  pipeline/
    rasterizar.py      1. PyMuPDF → PNG 300 dpi por página (ou texto nativo se o PDF for digital)
    ocr.py             2. Tesseract image_to_data → texto + caixa + confiança por palavra
    anonimizar.py         CPF/CNPJ/RG/e-mail/telefone → texto, imagem e PDF
    classificar.py     3. regras (palavras + título no topo) + modelo → tipo + confiança
    segmentar.py       4. sinais de início/fim → documentos (função pura, testável)
    montar.py          5. PyMuPDF → PDF pesquisável (texto invisível) + PDF com redaction real
    orquestrador.py       liga tudo, grava banco/storage
scripts/gerar_lote_teste.py
tests/test_pipeline.py
```

## Endpoints

| Método | Rota | Para quê |
|---|---|---|
| POST | `/lotes` | upload (multipart `arquivo`); 409 se o mesmo arquivo (SHA-256) já foi enviado |
| GET | `/lotes`, `/lotes/{id}` | lista / progresso (`paginas_processadas`, `progresso`) |
| GET | `/lotes/{id}/paginas` | status, tipo, confiança e sinais de cada página |
| GET | `/lotes/{id}/paginas/{n}/imagem?thumb=true` | miniatura para a tela de revisão |
| GET | `/lotes/{id}/documentos` | documentos detectados |
| POST | `/lotes/{id}/reprocessar[?tudo=true]` | recoloca páginas com falha na fila |
| GET | `/documentos/{id}/pdf[?anonimizado=false]` | PDF pesquisável (anonimizado por padrão) |
| GET | `/revisao/fila[?lote_id=]` | pendentes, menor confiança primeiro |
| POST | `/documentos/{id}/revisao` | `aprovar` · `alterar_tipo` · `dividir` (`pagina_corte`) · `juntar_proximo` |
| GET | `/busca?q=&tipo=` | full-text em português (stemming: "contrato" acha "contratada") |
| GET | `/tipos`, `/metricas` | taxonomia; taxa de automação, confiança média, docs por tipo |

## Como a decisão é tomada

**Tipo da página.** As regras pontuam cada tipo: +1 por palavra-chave e +3 por título no topo da
página. Se a confiança fica abaixo de `LIMIAR_LLM`, o modelo é consultado recebendo o texto mascarado e a
imagem com tarja. Quando as duas concordam, a confiança sobe. Quando discordam, a confiança cai e o
documento vai para revisão.

**Corte entre documentos**, do sinal mais forte para o mais fraco:

1. "Página 2 de 3": é continuação.
2. "Página 1 de N": é início.
3. Título no topo da página.
4. O modelo diz que é início.
5. O tipo mudou.
6. Página em branco: funciona como separador.

**Confiança do documento.** É a menor entre a confiança do tipo, a de cada corte e a qualidade do OCR.
O documento vai para a fila de revisão se:

- a confiança ficar abaixo de `LIMIAR_REVISAO`;
- o tipo for desconhecido;
- regras e modelo discordarem;
- a contagem "1 de N" não bater com o número de páginas.

## Roteiro de demo (pitch)

1. Subir o lote e mostrar a barra de progresso.
2. **Matar o worker** (`kill -9`) no meio do lote, religar com `python -m app.worker --recuperar-agora`
   e mostrar que ele continua de onde parou.
3. Mostrar os documentos separados por cor e tipo, e a fila de revisão com o motivo de cada pendência.
4. Corrigir um corte com "dividir" e mostrar que o PDF é regenerado e a correção fica na trilha de auditoria.
5. Abrir o PDF anonimizado: o CPF some do texto **e** da imagem.
6. Buscar uma palavra no OCR.
7. Abrir `/metricas` e mostrar a taxa de automação.

## Limitações e próximos passos

- A taxonomia e os limiares estão calibrados num lote sintético. Recalibrem com os dados de teste
  e meçam acurácia de corte e de tipo.
- A anonimização é feita por regex. Próximo passo: Presidio + spaCy pt para nomes e endereços.
- Pré-processamento mínimo. Próximo passo: deskew e binarização adaptativa para scans ruins.
- Autenticação por chave única. Em produção: OAuth2/JWT com perfis (analista, revisor, admin).
- Correções humanas ficam em `revisoes` e podem virar dataset para um classificador treinado
  (LayoutLMv3/Donut), reduzindo custo de modelo.
- **Licença:** o PyMuPDF é AGPL. Para uso comercial, usar a licença paga ou trocar por pypdfium2 + OCRmyPDF.
