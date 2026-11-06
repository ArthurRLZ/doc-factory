# Roteiro de demo (8 min)

Antes de começar, gere o lote: `cd backend && python scripts/gerar_lote_bernhoeft.py lote_terceiros.pdf`. Para subir o sistema, use `docker compose up -d` e abra http://localhost:5173.

1. **Documentos:** envie `lote_terceiros.pdf`. As 14 páginas viram 12 documentos separados e classificados.
2. **Uso de IA:** mostre o chip "IA em X% das páginas" no lote e o cartão "Uso de IA" no Painel.
3. **Trabalhadores:** abra o dossiê do trabalhador B, que é eletricista. A função lida no ASO exige NR-10 (vencendo) e NR-35 (faltando).
4. **Fila de revisão:** mostre o cartão "Sugestão da IA" (ou "por regras") e use o botão "Aplicar sugestão".
5. **Regras:** escreva "mantenha o contrato inteiro junto", clique em Entender e depois em Salvar.
6. **Acerto:** rode `python scripts/avaliar_acerto.py lote_terceiros.pdf --sem-llm`. O resultado esperado é 100% com 0 erros silenciosos. O botão "Ver acerto" aparece no lote que tem gabarito.
7. **Alertas:** cadastre um contato WhatsApp e clique em "Ver o que seria enviado agora", depois em "Executar agora (simulado)". Rode de novo para mostrar que não repete.
8. **Fornecedores:** gere o link, abra `/portal/<token>` e envie o PDF. Os cartões mostram reprovado com a data do vencimento, aprovado, ou "vence em N dias".
9. **Resiliência:** derrube o worker no meio de um lote (`docker compose stop worker`) e suba de novo. O processamento retoma de onde parou.
