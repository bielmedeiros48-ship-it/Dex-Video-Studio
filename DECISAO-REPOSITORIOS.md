# Decisão sobre repositórios e serviços

Verificação feita em 18 de novembro de 2026.

Regra de arquitetura: o vídeo continua sendo produzido por componentes locais que não
dependem de conta nem de um servidor do fornecedor. Ollama é o servidor de modelo local;
FFmpeg, OpenCV, Whisper, VoiceStudio, Auto-Editor e HyperFrames executam as ferramentas.
Se um site externo cair, pesquisa e mídia novas ficam indisponíveis, mas projetos já
baixados, roteiros, voz, cortes, legendas e renders locais continuam funcionando.

## Adotados como referência

### MoneyPrinterTurbo

Reutilizar a sequência `roteiro → termos visuais → voz → legenda → materiais →
composição`. Aceita Ollama local e mídia local, Pexels e Pixabay. Não instalar o
sistema completo enquanto nosso fluxo já usa FFmpeg, VoiceStudio e Whisper: primeiro
comparar um vídeo produzido pelos dois caminhos.

Fonte: https://github.com/harry0703/MoneyPrinterTurbo

### AIEV

Reutilizar manifesto central por cenas, render de rascunho, aprovação humana,
verificação de frames, fila com concorrência 1 e QC bloqueando o final. Não adotar
a dependência obrigatória do Claude Agent SDK nem os efeitos sonoros incluídos, cuja
própria documentação informa licença desconhecida.

Fonte: https://github.com/notivn/AIEV

### HyperFrames e Remotion

HyperFrames fica responsável por elementos animados; Remotion, se instalado, apenas
pela montagem programática. FCPXML continua disponível para DaVinci Resolve. A licença
do Remotion é gratuita para indivíduos e empresas com até três funcionários; deve ser
reavaliada se o projeto crescer.

Fontes: https://github.com/heygen-com/hyperframes e
https://github.com/remotion-dev/remotion/blob/main/LICENSE.md

### MakeMyClip Editor 0.5.2

Adotado como camada determinística de timeline: histórico, desfazer/refazer, remoção
de retakes e silêncios, verificação de cortes, legendas e FCPXML para o Resolve. É
MIT, local, sem conta, sem telemetria e aceita qualquer agente via CLI/MCP. A versão
foi fixada em 0.5.2. A instalação ignorou scripts de dependências e usa o FFmpeg já
instalado por `MAKEMYCLIP_FFMPEG_PATH`, evitando baixar outro binário.

Fonte: https://github.com/MakeMyClip/editor

### whisper.cpp b5454

Adotado apenas para compatibilidade com a timeline do MakeMyClip. O executável veio
do release oficial do ggml-org e reutiliza o modelo local `large-v3-turbo-q5_0`.
O filtro Whisper do FFmpeg continua sendo o transcritor principal do orquestrador.

Fonte: https://github.com/ggml-org/whisper.cpp/releases/tag/b5454

### OpenCV somente para reenquadramento

Adotado `opencv-python-headless 4.12.0.88` em ambiente isolado. Ele detecta rostos e,
quando não encontra um rosto (por exemplo em anime ou ação), usa o centro do movimento.
O resultado é uma sequência de comandos para o filtro `crop` do FFmpeg; nenhum quadro ou
biometria é enviado para fora da máquina. A abordagem foi escolhida também porque o
`claude-video-effects` usa OpenCV YuNet para rastreamento facial, mas não foi necessário
instalar o pacote completo de 51 efeitos.

Fontes: https://github.com/Vibha-Ramprakash/claude-video-effects e
https://github.com/opencv/opencv

## Candidatos úteis, sem instalação agora

| Projeto | Decisão | Motivo |
|---|---|---|
| Diffusion Studio Editor | teste futuro isolado | É o candidato mais completo para agente + timeline + CLI/MCP e inspeção de mídia. Sobrepõe a montagem atual; só migrar após comparar um projeto real. |
| LosslessCut | opcional manual | Excelente para desbaste sem recodificação, mas o núcleo FFmpeg já faz os cortes automáticos. |
| OpenFilm | estudar arquitetura | Agente de vídeo interessante, porém outro orquestrador inteiro. Não substitui uma ferramenta específica do fluxo atual. |
| FilmCraft, Shotcut e libopenshot | não integrar | São editores/motores alternativos; aumentariam manutenção sem corrigir rastreamento, roteiro ou efeitos. |
| VFX-JS | reservar para templates web | Útil para shaders WebGL no HyperFrames, não para o corte principal. |
| Remotion | opcional com licença reavaliável | Bom para motion graphics por código, mas HyperFrames já cobre o template editorial atual. |
| DCC-MCP Blender | fase 3D | Pode criar personagem e animações, mas permite execução de scripts no Blender e não deve entrar antes do pipeline 2D estar estável. |
| Crayotter | não adotar como núcleo | A interface é local, mas os modelos padrão exigem endpoint, chave e saldo do provedor. Serve como referência de rastreabilidade. |
| Graphify | não usar como memória editorial | Ele transforma código/documentação em grafo; não é banco de preferências de edição. JSON versionado por projeto é menor e suficiente agora. |
| Concat | manter em observação | É local e tem MCP/JSON-RPC, mas é beta, AGPL e duplica editor, voz, legenda e timeline já instalados. |

O catálogo do guia de conhecimento é uma lista de descoberta, não uma lista de instalação.
Entre as centenas de itens, os mais alinhados foram: HyperFrames (já adotado), Diffusion
Studio (teste futuro), `auto-subs` (somente se a integração direta com Resolve se tornar
prioritária), `youtube-shorts-pipeline` (referência de ordem notícias → roteiro → visuais →
voz → legenda → envio) e PySceneDetect (candidato para segmentar vídeos longos). Não se
instala um segundo programa quando FFmpeg/Whisper/VoiceStudio já entregam a mesma etapa.

## Não adotados agora

- AIEV completo: exige Node 22, Claude, Remotion, HyperFrames e mais uma interface,
  duplicando a base existente.
- Clipped AI Studio: sobrepõe o pipeline inteiro e depende de vários serviços online
  “keyless”; isso reduz previsibilidade, privacidade e controle de custos.
- Coverr para canal monetizado: manter suspenso até esclarecer os termos comerciais e
  a obrigação de atribuição da API.
- Geradores de vídeo em nuvem: opcionais somente para cenas que não podem ser obtidas
  ou produzidas localmente, com confirmação do custo antes de cada lote.
- Concat: editor local promissor com MCP e muitos efeitos, mas ainda beta e sobrepõe
  DaVinci, MakeMyClip e VoiceStudio. Reavaliar quando houver necessidade concreta.
- ClipForge/ViralClips: boas referências para face tracking, fallback de ranking e
  legendas por palavra. Não instalar o pipeline completo agora porque duplicaria o
  fluxo recém-validado; os recursos úteis serão avaliados isoladamente.
- HeyGen comercial e APIs de geração: a organização no GitHub não torna o serviço de
  avatar gratuito ou offline. Somente HyperFrames, que já foi validado localmente, entra
  no núcleo.

## Contas e chaves

- Ollama, Agent Reach, VoiceStudio, Whisper local, FFmpeg, Auto-Editor e MakeMyClip:
  nenhuma conta.
- Pixabay: opção preferencial para banco de mídia; a API gratuita informa limite padrão
  de 100 requisições por 60 segundos e exige chave.
- Pexels: a API é gratuita, mas o suporte oficial informou pausa na emissão de novas
  chaves em 17 de novembro de 2026. Não criar uma conta contando com chave imediata.
- Gemini/Claude: opcionais como revisores ou geradores especiais, não como cérebro do
  fluxo. Nunca colocar a chave dentro de JSON de projeto ou repositório.

Uma conta só será criada quando houver um serviço escolhido e uma finalidade concreta.
Captcha, telefone, aceite de termos e recuperação da conta permanecem com o usuário.
Credenciais devem ir para o Gerenciador de Credenciais do Windows ou arquivo `.env`
fora do repositório, nunca para um documento de texto com senhas.
