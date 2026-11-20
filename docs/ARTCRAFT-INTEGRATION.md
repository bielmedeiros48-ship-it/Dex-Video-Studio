# Integração ArtCraft

## Componentes detectados

- ArtCraft Launcher: catálogo e inicialização dos aplicativos Craft.
- FilmCraft: editor de vídeo com CLI local e automação MCP.
- PhotoCraft: editor de imagem com CLI local, servidor headless e MCP.

## Decisão da Dex

O motor da Dex não depende do Launcher. FilmCraft e PhotoCraft entram como
adaptadores opcionais e substituíveis:

1. FFmpeg e DaVinci continuam sendo o caminho principal e de contingência.
2. `craft-doctor` detecta versões e caminhos sem iniciar servidores.
3. `craft-probe` inspeciona vídeo ou imagem com argumentos fixos e validados.
4. Credenciais do ambiente não são encaminhadas aos processos Craft.
5. Nenhum servidor TCP permanece aberto por padrão.

## MCP

PhotoCraft pode ser iniciado futuramente com raízes explícitas de leitura e
escrita por projeto. FilmCraft MCP não oferece esse confinamento; por isso, a
Dex não o registra automaticamente. Para edição automática, será preferido um
arquivo de comandos JSONL revisável executado pelo `filmcraft-cli run`.

## Autoria e licenças

ArtCraft, FilmCraft e PhotoCraft são projetos de terceiros sob as licenças que
acompanham cada distribuição. A Dex pode adaptar e integrar código conforme as
licenças, mas deve preservar avisos, atribuição e histórico de origem. O projeto
Dex não apresenta trabalho de terceiros como autoria própria.
