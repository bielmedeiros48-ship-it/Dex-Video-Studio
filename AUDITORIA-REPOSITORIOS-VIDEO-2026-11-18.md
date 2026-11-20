# Auditoria de repositórios de vídeo - 18/11/2026

Objetivo: selecionar componentes para o Ollama Video Studio que sejam gratuitos,
locais, reversíveis e úteis no computador atual. Estrela não é critério de segurança.
Foram verificados README, atividade, licença declarada e sobreposição com o pipeline.

## Decisão dos links enviados

| Repositório | Offline | Decisão | Papel ou motivo |
|---|---:|---|---|
| heygen-com/hyperframes | sim | **mantido** | Motion graphics HTML já instalados e renderizados localmente. Apache-2.0. Não confundir com a API comercial da HeyGen. |
| mifi/lossless-cut | sim | opcional | Excelente ferramenta manual para desbaste sem recodificar. Não é necessária no caminho automático, que já usa FFmpeg. GPL-2.0. |
| jub0t/Concat | sim | observar | Editor beta com MCP/JSON-RPC, legenda e voz locais. Duplica DaVinci, MakeMyClip e VoiceStudio; AGPL exige cuidado se o produto for distribuído. |
| storytold/filmcraft | sim | não integrar | Outro editor não linear completo em Rust. Não oferece ganho específico para rastreamento ou roteiro. Apache-2.0. |
| mltframework/shotcut | sim | não integrar | Editor maduro para uso manual, mas sem vantagem sobre DaVinci no fluxo do usuário. GPL-3.0. |
| openfilm/openfilm | parcial | referência | Boa arquitetura de agente de vídeo e edição revisável, mas é outro orquestrador inteiro. MIT. |
| OpenShot/libopenshot | sim | não integrar | Biblioteca de edição C++/Python robusta, porém exigiria um segundo motor e build pesado; FFmpeg cobre o núcleo. LGPL-3.0. |
| fand/vfx-js | sim | reservar | Shaders WebGL úteis em templates HyperFrames específicos. Não participa dos cortes. MIT. |
| Vibha-Ramprakash/claude-video-effects | sim | **reuso seletivo** | A ideia OpenCV YuNet + fallback foi aplicada ao reenquadramento; o pacote completo de efeitos não foi instalado. README atribui componentes MIT/Apache e fontes livres. |
| diffusionstudio/editor | sim | teste futuro | Melhor candidato a editor principal para agentes: CLI/MCP, filmstrip, waveform, transcrição, inspeção e timeline. Só migrar após teste comparativo para não duplicar a base. MPL-2.0. |
| idwts/Crayotter | não no padrão | não adotar | A interface roda local, mas os modelos padrão exigem endpoint, chave e saldo. Útil apenas como referência de logs e retomada. |
| remotion-dev/remotion | sim | opcional | Forte para animação programática, mas HyperFrames já cobre o template atual. Licença especial precisa ser reavaliada se houver crescimento comercial. |
| dcc-mcp/dcc-mcp-blender | sim | fase 3D | Pode automatizar personagem, rig, material e render, mas permite scripts dentro do Blender. Adiar até o fluxo 2D estar estável. MIT. |
| Graphify-Labs/graphify | sim | não usar como memória | Serve para grafo de código, documentação, SQL e PDFs. Não é memória editorial nem banco de projetos; JSON versionado é suficiente. Apache-2.0. |

O link `chatgpt.com/c/...` é uma conversa privada e não constitui documentação
verificável do projeto. As decisões acima usam apenas os repositórios oficiais.

## Seleção dentro do Guia do Conhecimento

O guia é um catálogo muito amplo e mistura projetos maduros, experimentos, serviços
online e descrições ainda não auditadas. Instalar tudo reduziria a confiabilidade.

### Aproveitar agora

- **HyperFrames**: já validado para cartelas, dados, zooms e gráficos de notícia.
- **PySceneDetect**: próximo candidato leve para separar cenas de vídeos longos antes
  da análise; não é necessário para corrigir o Short atual.
- **auto-subs**: avaliar somente quando a criação direta de legendas dentro do DaVinci
  se tornar prioridade.
- **youtube-shorts-pipeline**: usar apenas a ordem conceitual notícias → roteiro →
  visuais → voz → legenda → revisão; não instalar o pipeline inteiro.
- **VideoHighlighter/Clipify/yt-short-clipper**: referências para ação, rosto e
  reenquadramento; o componente necessário já foi implementado localmente.

### Não instalar agora

- Geradores grandes de vídeo, avatares e áudio (Hunyuan, modelos de difusão, MMAudio,
  Stable Audio): podem ultrapassar a RTX 4050 de 6 GB ou exigir downloads enormes.
- Editores completos alternativos (OpenChatCut, CartCut, Concat, FilmCraft, Shotcut):
  sobrepõem ferramentas já validadas.
- Pontes de Premiere/After Effects/CapCut: não correspondem ao editor principal atual.
- Serviços “keyless”, APIs não oficiais ou automação de login: risco de estabilidade,
  termos de uso, bloqueio e vazamento de sessão.

## Contribuições do catálogo em PDF

O catálogo anexado organiza corretamente o projeto em compreensão, edição, criação,
conhecimento e validação. Adoções resultantes:

1. preservar artefatos reversíveis e registrar parâmetros;
2. usar detecção de cena antes de análise longa;
3. manter voz/transcrição como relógio mestre do vídeo dark;
4. salvar feedback como regra contextual, nunca aplicar uma correção estética a todos
   os vídeos automaticamente;
5. deixar Blender, VFX generativo e áudio gerativo para fases posteriores;
6. não adotar Chroma, Mem0 ou Letta antes de JSON deixar de atender ao volume real.

## Núcleo aprovado

Ollama local + FFmpeg/ffprobe + OpenCV YuNet + Whisper local + VoiceStudio local +
Auto-Editor + MakeMyClip + HyperFrames + JSON/FCPXML. Pesquisa online é uma ferramenta
opcional: sem internet, materiais já baixados continuam pesquisáveis e editáveis, mas
notícias novas e bancos externos naturalmente não podem ser consultados.

Fontes oficiais:

- https://github.com/heygen-com/hyperframes
- https://github.com/mifi/lossless-cut
- https://github.com/jub0t/Concat
- https://github.com/storytold/filmcraft
- https://github.com/mltframework/shotcut
- https://github.com/openfilm/openfilm
- https://github.com/OpenShot/libopenshot
- https://github.com/fand/vfx-js
- https://github.com/Vibha-Ramprakash/claude-video-effects
- https://github.com/diffusionstudio/editor
- https://github.com/idwts/Crayotter
- https://github.com/remotion-dev/remotion
- https://github.com/dcc-mcp/dcc-mcp-blender
- https://github.com/Graphify-Labs/graphify
- https://github.com/arthurspk/guiadoconhecimento/blob/main/ia/profissoes/editor-de-video.md
