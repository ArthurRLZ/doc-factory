# Premissas, limitações, riscos e próximos passos

## Premissas
- A tabela função → NRs (`tipos.FUNCOES_NR`) é **demonstrativa**; precisa ser validada pela área de SST.
- Os alertas avisam nas faixas de 30, 15, 7 e 1 dia antes do vencimento, além dos documentos já vencidos (`ALERTAS_FAIXAS_DIAS`).
- As validades por tipo seguem regras fixas (ASO 12 meses, CRF 30 dias, CNDT 180 dias…).
- Os limiares foram calibrados no lote sintético de terceiros.
- O acerto de 100% (`scripts/avaliar_acerto.py`) foi medido em lote **sintético**.

## Limitações
- O OCR (Tesseract) piora em escaneamentos ruins.
- A separação de várias folhas numa imagem (multidoc) usa só **contornos**, então precisa de contraste entre a folha e o fundo. Arquivos acima de `MULTIDOC_MAX_MB` não passam pela detecção.
- O WhatsApp depende de uma instância da Evolution API já conectada. O formato da v2 está isolado em `alertas/canais._payload`.
- O portal do fornecedor não tem login forte: a segurança é o link secreto, o que basta para um MVP. O limite de envios por hora fica na memória, por processo da API.
- O LLM na nuvem recebe apenas texto anonimizado e imagem com tarjas. Toda resposta dele é validada (lista fechada de valores e evidência copiada do texto).

## Riscos e mitigação
- **Custo de LLM:** o modelo só é consultado quando a regra tem baixa confiança, e o contador por lote fica visível. A pré-revisão tem um teto de chamadas por lote (`PRE_REVISAO_MAX_POR_LOTE`).
- **Fraude que passa sem ser detectada:** os sinais são heurísticos. Documentos com risco "atenção" também vão para revisão humana.
- **Vazamento do link do portal:** o link expira, tem limite de usos e pode ser revogado. No banco fica só o hash do token.

## Próximos passos
- Login no portal com 2FA e assinatura de webhooks.
- Treinamento a partir das correções dos revisores (a tabela `Aprendizado` já existe).
- Integração com ERP/SAP e trilha de auditoria exportável.
- Endireitamento e binarização da imagem antes do OCR.
- Limitador de envios compartilhado entre processos (Redis).
