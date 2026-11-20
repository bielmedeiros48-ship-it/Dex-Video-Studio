# Integrações externas

O motor não carrega todo repositório encontrado na internet. Cada integração é
avaliada por utilidade, licença, custo, privacidade, suporte a Windows e português.
A decisão legível por máquina fica em `config/integrations/repositories.json`.

## Selecionadas

- **OpenMontage:** código-fonte mantido separadamente. Os padrões de revisão visual,
  FFmpeg e Remotion inspiram o comando local `review-video`; nenhuma API paga é
  necessária para essa revisão. A licença AGPL é preservada e seu código não é
  incorporado silenciosamente ao motor.
- **PeakCut:** candidato a sidecar de clips. Ele já aceita Ollama em
  `127.0.0.1:11434`, mas não será ativado até usar o Whisper local em pt-BR. Isso
  evita baixar um segundo reconhecedor inadequado e evita duplicar o pipeline.

## Não selecionadas

- **Battery Hub:** útil apenas para bateria de periféricos HID, fora do fluxo de vídeo.
- **Gists de boringmarketer:** úteis como referência de copy, mas sem licença clara
  não devem ser copiados para um projeto público.

Downloads de modelos, criação de contas, uso de chaves e publicação permanecem
ações separadas. Nenhum repositório externo recebe acesso amplo ao computador.
