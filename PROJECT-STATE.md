# Estado compartilhado do Projeto Dex — vídeo

Este arquivo é o ponto de entrada sanitizado para outra IA continuar o projeto.
Ele não contém mídia, voz, credenciais, memória pessoal ou caminhos da máquina.

## Objetivo imediato

Produzir localmente um episódio de notícias mundiais da semana: pesquisa com fontes,
seleção de cinco pautas, roteiro revisável, narração em português brasileiro,
storyboard, montagem, legendas, tratamento de áudio, revisão visual e timeline
editável. Nenhuma publicação é automática.

## Arquitetura

- Dex é o orquestrador do usuário; Ollama é o runtime local atualmente usado.
- `ollama-video:latest` planeja e classifica; ferramentas determinísticas executam mídia.
- FFmpeg, Whisper, Auto-Editor e VoiceStudio fazem processamento local.
- Dados pessoais e projetos vivem fora do Git nas pastas ignoradas.
- Integrações externas rodam com ambiente limitado e não recebem tokens ambientes.

## Capacidades verificadas

- remoção de silêncios e geração de FCPXML editável;
- transcrição, seleção e renderização de melhores momentos;
- Shorts verticais com acompanhamento suave do assunto e legendas em área segura;
- tratamento de áudio, controle de qualidade e revisão visual por folha de contato;
- pesquisa, ranking preliminar, rascunho com fontes e storyboard;
- narração local com referência autorizada e idioma `pt-BR`.

## Gates obrigatórios

`fontes verificadas → roteiro aprovado → voz aprovada → storyboard aprovado → edição revisada → exportação aprovada → publicação confirmada`

## Situação atual

- O repositório deve permanecer privado durante o desenvolvimento.
- A voz dots.tts está em avaliação; a transcrição da referência passou a ser enviada ao motor.
- A estética final ainda exige revisão humana da folha de contato e do áudio.
- PeakCut e OpenMontage permanecem isolados e desativados; consulte `INTEGRACOES-EXTERNAS.md`.

## Dependência offline real

O motor e os modelos locais continuam funcionando sem internet e mesmo se os
repositórios originais desaparecerem. Hoje, porém, a inferência ainda depende do
executável instalado do Ollama. Para independência também do runtime, o próximo
passo arquitetural é adicionar um adaptador local compatível com a API do Ollama
usando llama.cpp e manter, em backup privado, modelos, versões e hashes. Não
afirme que o Dex já substitui o executável do Ollama.

## Antes de continuar

1. Execute `powershell -NoProfile -File scripts/check_repository_safety.ps1`.
2. Execute `python -m unittest discover -s tests -v` no ambiente do projeto.
3. Leia `PROCEDIMENTO-PRODUCAO.md`, `GUIA-QUALIDADE.md` e `PUBLICO-E-PRIVADO.md`.
4. Não envie projetos, vozes, vídeos, modelos, logs ou credenciais ao GitHub.
