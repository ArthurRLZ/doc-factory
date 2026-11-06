"""Estados do sistema num lugar só — nada de texto solto espalhado pelo código.

StrEnum: cada valor É o próprio texto ("pendente" == StatusPagina.PENDENTE), então banco, API e front
continuam iguais; o ganho é que um erro de digitação vira erro na hora, e não um bug silencioso.
"""
from enum import StrEnum


class StatusLote(StrEnum):
    RECEBIDO = "recebido"
    PROCESSANDO = "processando"      # páginas na fila / sendo processadas
    SEGMENTANDO = "segmentando"      # todas as páginas prontas; um worker está montando os documentos
    CONCLUIDO = "concluido"
    ERRO = "erro"


class StatusPagina(StrEnum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    OK = "ok"
    ERRO = "erro"                    # falhou, mas ainda vai tentar de novo
    FALHOU = "falhou"                # desistiu depois de MAX_TENTATIVAS


class StatusRevisao(StrEnum):
    AUTO_APROVADO = "auto_aprovado"
    PENDENTE = "pendente"            # na fila de revisão humana
    REVISADO = "revisado"


PAGINAS_EM_ABERTO = (StatusPagina.PENDENTE, StatusPagina.PROCESSANDO, StatusPagina.ERRO)
