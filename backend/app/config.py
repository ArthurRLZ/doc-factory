"""Configuração central — tudo vem de variáveis de ambiente / arquivo .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Infra ---------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./data/docfactory.db"   # prod: postgresql+psycopg://...
    STORAGE_BACKEND: str = "local"                    # local | s3 (MinIO/S3/GCS-interop)
    DATA_DIR: str = "./data"                          # raiz do storage local + cache
    S3_ENDPOINT: str | None = None                    # ex.: http://minio:9000
    S3_BUCKET: str = "docfactory"
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None

    # --- Ambiente -----------------------------------------------------------
    # producao = a API se recusa a subir sem login, sem segredos ou com CORS aberto
    AMBIENTE: str = "desenvolvimento"   # desenvolvimento | producao

    # --- Segurança -------------------------------------------------------
    CADASTRO_ABERTO: bool = True        # /auth/registrar: qualquer pessoa cria conta de analista (desligue em produção)
    LOGIN_MAX_TENTATIVAS: int = 5       # erros seguidos de senha antes de bloquear o login
    LOGIN_BLOQUEIO_MIN: int = 5         # minutos de bloqueio
    MAX_MEGAPIXELS_PAGINA: float = 60.0 # página maior que isso é renderizada com DPI menor (protege a memória)
    API_KEY: str | None = None          # se definido, exige header X-API-Key
    CORS_ORIGINS: str = "*"             # separar por vírgula
    # login com perfis (analista < revisor < admin). Desligado = API aberta (demo).
    AUTH_ATIVO: bool = False
    JWT_SEGREDO: str | None = None      # sem valor: gera um aleatório a cada start (tokens caem no restart)
    JWT_EXPIRA_MIN: int = 480
    ADMIN_USUARIO: str = "admin"        # criado no primeiro start se não houver usuários
    ADMIN_SENHA: str | None = None      # sem valor: nenhum admin é criado automaticamente
    MAX_UPLOAD_MB: int = 2048
    EXTENSOES_PERMITIDAS: str = ".pdf,.tif,.tiff,.png,.jpg,.jpeg"

    # --- Pipeline: rasterização + OCR -----------------------------------
    DPI_OCR: int = 300                  # 300 dpi = sweet spot do Tesseract
    DPI_THUMB: int = 40
    OCR_LANG: str = "por"
    OCR_PSM: int = 3                    # 3 = segmentação automática de página
    OCR_TIMEOUT_S: int = 90             # página que trava o Tesseract vira 'erro' e é retentada
    TEXTO_NATIVO_MIN_CHARS: int = 50    # PDF digital com texto → pula OCR

    # --- Anonimização ------------------------------------------------------
    ANONIMIZAR_NOMES: bool = True       # nomes de pessoas → [NOME] (rótulos do documento + reconhecedor spaCy)
    ANONIMIZAR_ENDERECOS: bool = True   # logradouro + número → [ENDERECO], CEP → [CEP] (cidades ficam)
    NER_MODELO: str = "pt_core_news_md" # modelo spaCy em português; ausente = só as regras por rótulo
    CPF_SEGREDO: str | None = None      # segredo da impressão digital do CPF (dossiê); defina em produção

    # --- Classificação / revisão ----------------------------------------
    LIMIAR_REVISAO: float = 0.80       # abaixo disso → fila de revisão humana
    LIMIAR_LLM: float = 0.75            # regra abaixo disso → consulta o modelo
    LLM_SEMPRE: bool = False            # True = modelo em toda página (2ª opinião)
    BRANCO_COMO_SEPARADOR: bool = True  # página em branco fecha o documento atual

    # --- Modelo (qualquer API compatível com OpenAI) -----------------------
    LLM_PROVIDER: str = "nenhum"        # nenhum | openai | gemini | deepseek | ollama | custom
    LLM_MODEL: str = ""
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = None     # sobrescreve a URL padrão do provedor
    LLM_MULTIMODAL: bool = True         # envia a imagem (mascarada) junto do texto
    LLM_TIMEOUT: int = 60
    LLM_CUSTO_POR_CHAMADA_BRL: float = 0.0  # custo médio por chamada de IA, só para estimativa na tela (0 = não mostrar R$)
    FRAUDE_ATENCAO_REVISAO: bool = True
    FUNCAO_EXIGENCIAS_ATIVO: bool = True    # a função lida no ASO/CTPS acrescenta as NRs exigidas ao checklist     # documento com risco "atencao" também vai para a fila de revisão

    # --- Validade -----------------------------------------------------------
    VALIDADE_ALERTA_DIAS: int = 30      # vence em até N dias → status "vencendo" (e prioridade alta)
    FUSO_HORAS: int = -3                # fuso para "hoje" / "esta semana" nos painéis (Brasília = -3)

    # --- Resumo -------------------------------------------------------------
    RESUMO_ATIVO: bool = True           # gera resumo de cada documento (modelo, ou simples sem modelo)
    RESUMO_CHARS_POR_PARTE: int = 6000  # documento maior que isso é resumido em partes e depois consolidado

    # --- Worker -----------------------------------------------------------
    MAX_TENTATIVAS: int = 3
    WORKER_POLL_S: float = 1.0
    WORKER_STALE_MIN: int = 2           # página "processando" há mais que isso = worker morreu
    WORKER_INLINE: bool = False         # True = roda o worker numa thread dentro da API (dev/demo)

    @property
    def extensoes(self) -> set[str]:
        return {e.strip().lower() for e in self.EXTENSOES_PERMITIDAS.split(",")}


settings = Settings()
