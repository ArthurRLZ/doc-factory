# Privacidade e armazenamento

O relatório e os PDFs com tarjas são auxílios à revisão. O OCR e os padrões de detecção podem falhar;
confira as páginas antes de compartilhar. Um risco baixo não garante ausência de dados pessoais. Erros
como `529.982.24?-25`, nomes em minúsculas e endereços com número mal lido podem passar pela detecção.
Evite usar documentos reais até que o ambiente e o processo de revisão estejam adequados ao caso.

## Onde os dados ficam

No Compose, PostgreSQL usa o volume `pgdata` e os arquivos ficam no volume `dados`, em `/data/storage/lotes/<id>/`.
Fora do Docker, o diretório raiz é `DATA_DIR`. Os volumes padrão e os volumes da configuração isolada são distintos.

- `original.pdf`, `.tif`, `.png` ou `.jpg`: arquivo enviado, sem anonimização.
- Quando uma imagem com várias folhas é dividida, `original_enviado` preserva o arquivo recebido e
  `original.pdf` contém as páginas normalizadas. Ambos podem conter dados pessoais sem tarjas.
- `paginas/*.png` e `*.thumb.jpg`: imagens originais renderizadas, sem tarjas.
- `paginas/*.palavras.json`: palavras e coordenadas extraídas, incluindo texto não mascarado.
- `documentos/*.pdf`: PDF pesquisável original; `*.anon.pdf`: versão com tarjas aplicadas aos dados detectados.
- As versões históricas podem preservar PDFs anteriores; o banco também guarda nomes de lotes, revisões,
  metadados e outros campos. O texto é mascarado por heurísticas, portanto não se deve presumir que o banco
  esteja livre de dados pessoais.
- O upload pode passar pelo diretório temporário do sistema ou do contêiner; armazenamento compatível com S3
  também usa cache local. Backups podem incluir banco e arquivos originais; o backup local existente não é criptografado.

Autenticação e separação de perfis reduzem acesso pela API. Elas não criptografam volumes, backups, temporários
ou dados no disco; quem tem acesso ao host, Docker, volumes ou cópias pode acessar os arquivos. Analistas não
recebem imagens originais pela API; revisores e administradores podem acessá-las.

## Instância local isolada com autenticação

`docker-compose.seguro.yml` cria uma instância separada, com cadastro público desligado, acesso à interface
restrito a `127.0.0.1`, banco e API sem portas publicadas, portal público e LLM desativados. A configuração exige credenciais
próprias de PostgreSQL, JWT, CPF e administrador, compartilhadas pela API e pelo worker.

Na raiz do repositório:

```powershell
python backend/scripts/gerar_credenciais_local.py
docker compose --env-file "$env:USERPROFILE/.docfactory/credenciais.env" -f docker-compose.seguro.yml up --build -d
```

O gerador não sobrescreve um arquivo existente. O arquivo `.docfactory/credenciais.env` fica no perfil do usuário,
fora do repositório; nele estão o usuário
administrador e a senha. Restrinja seu acesso pelas permissões do sistema, guarde uma cópia protegida e não
compartilhe o arquivo. No Windows, o modo de criação do Python não substitui a configuração das ACLs do Windows.
Para parar sem apagar os volumes: `docker compose --env-file "$env:USERPROFILE/.docfactory/credenciais.env" -f docker-compose.seguro.yml stop`.

Esta configuração é um ponto de partida local, não uma implantação pronta para dados reais. Antes do uso real:

1. Restrinja o acesso físico e às contas do host e do Docker; use criptografia de disco/volumes e backups protegidos.
2. Configure HTTPS e controle de acesso apropriado antes de expor qualquer serviço fora do computador local.
3. Defina prazo de retenção, descarte e restauração testada, incluindo banco, arquivos, versões e cópias.
4. Crie contas individuais apenas com o perfil necessário e revise quem pode acessar originais.
5. Confirme a revisão dos PDFs e a finalidade e base adequada para o tratamento com o responsável pela organização.
6. Teste os limites com documentos representativos e não envie dados a um modelo externo sem autorização e avaliação.

Não troque `CPF_SEGREDO` de uma instalação que já contém dados sem planejar a migração: ele influencia a
identificação de trabalhadores e uma troca pode impedir a associação com registros anteriores. Alterar
`POSTGRES_PASSWORD` no arquivo não altera automaticamente a senha de um banco cujo volume já foi inicializado.
