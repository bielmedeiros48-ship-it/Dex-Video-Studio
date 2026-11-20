# Procedimento de produção de vídeo

Esta é a ordem oficial do Dex Video Studio. Ela combina o pipeline simples do
MoneyPrinterTurbo com os gates de rascunho, verificação e controle de qualidade do
AIEV. O Ollama organiza e decide; ferramentas determinísticas executam mídia.

## Papéis

- **Orquestrador:** `ollama-video:latest`. Mantém estado, escolhe a próxima etapa e
  nunca declara sucesso sem receber o resultado de uma ferramenta.
- **Pesquisa:** Agent Reach e fontes primárias. Resultado de busca é candidato, não fato.
- **Roteiro:** Ollama local. Um modelo online pode ser usado como revisor opcional,
  nunca como única fonte.
- **Voz:** VoiceStudio local.
- **Transcrição e tempo:** Whisper `large-v3-turbo` local pelo filtro do FFmpeg.
- **Cortes:** Auto-Editor e FFmpeg.
- **Reenquadramento vertical:** OpenCV local localiza rosto ou centro de movimento e
  envia uma câmera virtual ao FFmpeg em 30 passos por segundo, com zona morta,
  aceleração e velocidade limitadas. O resultado sempre exige inspeção visual, em
  especial em lutas com vários personagens.
- **Animação:** HyperFrames para cenas e elementos gráficos.
- **Montagem:** FFmpeg/HyperFrames e FCPXML para continuar no DaVinci. Remotion fica
  opcional para composições futuras que realmente precisem de React.
- **Controle de qualidade:** FFmpeg/ffprobe e revisão humana.

## Ciclo editorial semanal

1. Criar uma semana editorial e um conjunto vazio de candidatos.
2. Pesquisar pelo menos 20 pautas por dia até reunir 45 candidatas úteis. Não completar
   45 com assuntos fracos apenas para atingir o número.
3. Normalizar título, URL, fonte, data de publicação e data do acontecimento.
4. Remover duplicatas que descrevem o mesmo evento.
5. Exigir duas fontes independentes para fatos relevantes; priorizar fonte primária.
6. Recalcular diariamente: impacto 25%, velocidade de repercussão 20%, confiabilidade
   20%, relevância para o público 15%, duração do interesse 10% e material visual 10%.
7. Selecionar normalmente cinco pautas. Usar seis a dez somente quando houver várias
   pautas realmente próximas no topo e ainda for possível terminar em até 15 minutos.
8. Pautas não escolhidas continuam no conjunto semanal e podem subir ou cair no dia seguinte.

## Produção de um episódio

1. **Brief:** canal, público, formato, duração, tom, data limite e identidade visual.
2. **Dossiê:** fatos confirmados, URLs, datas, citações curtas permitidas e direitos de mídia.
3. **Roteiro:** gancho, contexto, blocos de notícia, ligação entre blocos, síntese e encerramento.
4. **Revisão editorial:** marcar alegações com uma fonte só, conflitos e informação desatualizada.
5. **Narração:** gerar por blocos; medir a duração real com ffprobe.
6. **Transcrição:** palavras e timestamps da narração final. Esta passa a ser o relógio mestre.
7. **Storyboard:** cada bloco recebe narração, imagem principal, B-roll, texto na tela,
   animação, transição, efeito sonoro e URLs de origem.
8. **Direitos:** baixar apenas mídia própria, licenciada ou autorizada; registrar licença e URL.
9. **Montagem bruta:** voz primeiro, depois imagens alinhadas aos timestamps. Nenhum efeito ainda.
10. **Ritmo:** em notícia, trocar enquadramento ou elemento visual normalmente a cada 4–8 segundos,
    sem cortar tão rápido que prejudique a compreensão.
11. **Gráficos:** títulos, datas, mapas, números, nomes e o personagem do canal.
12. **Legendas:** derivadas da transcrição final, em grupos de até seis palavras, sem
    caixa preta e dentro da área segura (1080×1920: 510 px acima da borda inferior e
    margem lateral reservada para os controles da plataforma).
13. **Transições:** motivadas pela mudança de assunto; evitar efeito aleatório em cada corte.
14. **Som:** voz, efeitos cerca de 10 dB abaixo da voz e música com redução automática sob fala.
15. **Imagem:** correção de exposição/balanço e grade coerente entre fontes diferentes.
16. **Rascunho:** render rápido, nunca diretamente o arquivo final.
17. **QC:** resolução/fps, -14 LUFS como alvo de internet, pico verdadeiro abaixo de -0,5 dBTP,
    quadros pretos no meio, congelamentos, silêncio final, sincronização e áreas seguras.
18. **Aprovação:** o usuário assiste e pede correções. Silêncio não significa aprovação.
19. **Final:** render de qualidade, thumbnail, título, descrição, capítulos, hashtags e fontes.
20. **Publicação:** somente após confirmação explícita de conta, vídeo, horário e metadados.

## Estrutura narrativa sugerida

- Gancho: 5–15 segundos.
- Promessa e contexto: 20–40 segundos.
- Cinco pautas: aproximadamente 60–120 segundos cada, conforme importância.
- Ligações entre pautas: 3–8 segundos.
- Síntese e encerramento: 20–45 segundos.
- Episódio normal: 8–12 minutos. Episódio especial: até 15 minutos.

## Gates obrigatórios

`fontes verificadas → roteiro aprovado → voz aprovada → storyboard aprovado →
rascunho aprovado → QC aprovado → publicação aprovada`

Falhar em um gate volta somente à etapa responsável. Uma alteração em uma cena não
autoriza renderizar novamente o vídeo inteiro se a cena puder ser renderizada isoladamente.

## O que foi reutilizado

- MoneyPrinterTurbo: roteiro → termos visuais → voz → legenda → materiais → composição.
- AIEV: manifesto central por cenas, rascunho antes do final, verificação de frames,
  fila de render e QC bloqueando o arquivo final.
- Não são reutilizados: credenciais, publicação automática, mídia com licença desconhecida
  ou dependência obrigatória de Claude/Gemini.

