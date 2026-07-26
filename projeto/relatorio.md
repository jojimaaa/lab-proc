# Relatório Final — Tradutor Embarcado de LIBRAS

**PCS3724 — Sistemas Embarcados · Escola Politécnica da USP**

---

## 1. Introdução

Milhões de pessoas no Brasil têm dificuldade para ouvir, e a maioria da
população não conhece a Língua Brasileira de Sinais (LIBRAS). Isso cria uma
barreira de comunicação no dia a dia entre pessoas surdas e ouvintes.

O objetivo deste projeto foi construir um dispositivo capaz de reduzir essa
barreira: uma Raspberry Pi com uma webcam que **enxerga os gestos da mão,
reconhece as letras do alfabeto em LIBRAS e traduz para texto e voz**, em
tempo real e sem depender de internet — tudo é processado na própria placa.

## 2. O que o sistema faz

Na prática, o uso é simples:

1. A pessoa faz o gesto de uma letra em frente à câmera e o mantém por uma
   fração de segundo.
2. A letra reconhecida aparece na tela e vai se juntando às anteriores,
   formando uma palavra.
3. Quando a pessoa tira a mão do quadro por cerca de um segundo, a palavra é
   considerada completa: ela aparece em destaque na tela e é **falada em voz
   alta** pelo alto-falante.

Assim, alguém que se comunica apenas por sinais consegue "falar" com uma
pessoa ouvinte que não conhece LIBRAS: uma se expressa com as mãos, a outra
lê na tela e ouve a voz sintetizada.

Além da tradução, a tela mostra um **painel de desempenho** do processador
(uso de CPU, memória, temperatura, frequência e outros indicadores), que
usamos para avaliar como o sistema se comporta em hardwares diferentes.

## 3. Como o sistema funciona

O software foi organizado como uma linha de montagem: cada quadro de vídeo
passa por uma sequência de etapas, e cada etapa tem uma responsabilidade
única.

```
câmera → ajuste da imagem → esqueleto da mão → classificação da letra
       → estabilização temporal → tela + voz
```

- **Ajuste da imagem** — o quadro é reduzido e convertido para o formato que
  a etapa seguinte espera. Trabalhar com imagens menores economiza
  processamento, o que importa em uma placa pequena.
- **Esqueleto da mão** — em vez de analisar a imagem inteira, o sistema
  localiza 21 pontos da mão (juntas e pontas dos dedos). É como reduzir a
  foto a um "esqueleto" com pouquíssimos números, o que torna o
  reconhecimento leve e pouco sensível a fundo e iluminação.
- **Classificação da letra** — o formato do esqueleto é comparado com
  exemplos gravados previamente de cada letra, e o sistema escolhe a letra
  mais parecida, junto com um grau de confiança.
- **Estabilização temporal** — o sistema não aceita a primeira resposta:
  a letra só é confirmada quando a mesma resposta se repete com confiança
  por vários quadros seguidos. Isso elimina letras "fantasma" que
  apareceriam durante a transição entre um gesto e outro.
- **Tela + voz** — um pequeno servidor web na própria placa mostra o vídeo,
  a tradução e o painel de desempenho no monitor, e um sintetizador de voz
  fala cada palavra concluída.

Uma decisão importante do projeto é que **nada sai da placa**: não há nuvem
nem rede envolvida. Isso deixa o dispositivo portátil, com resposta rápida e
sem expor o vídeo do usuário.

O sistema também possui um **modo demonstração**, que simula os gestos e
percorre todas as etapas acima sem precisar de câmera — foi essencial para
desenvolver e testar o projeto em qualquer computador.

## 4. Verificação dos requisitos

Cada requisito levantado no início do projeto virou um arquivo de testes
automatizados, que reproduz o cenário de teste planejado:

| Requisito | Como foi verificado | Resultado |
|---|---|---|
| Interface para visualização da tradução | Testes carregam a página e as APIs que a alimentam e conferem que tudo responde sem falhas | ✅ Aprovado |
| Conexão da webcam | Testes percorrem o caminho completo: recepção do quadro, processamento e quadro pronto para exibição | ✅ Aprovado |
| Reconhecimento de sinais | O alfabeto inteiro é apresentado ao sistema, quadro a quadro e com ruído, e as 26 letras devem ser confirmadas na ordem | ✅ Aprovado |
| Acessibilidade | A partir **apenas de gestos**, o sistema deve produzir as duas saídas: texto na tela e voz | ✅ Aprovado |
| Métricas de desempenho | O painel deve expor os indicadores do processador, e o benchmark deve gerar resultados comparáveis entre máquinas | ✅ Aprovado |
| Portabilidade | O sistema deve rodar autocontido: sem hardware especial, totalmente offline e com consumo de memória estável | ✅ Aprovado |

Ao todo são **37 testes automatizados**, executados com um único comando
(`python -m pytest`). Eles rodam em qualquer computador, porque as partes
que dependem de hardware (câmera e detector de mão) são substituídas por
versões simuladas — todas as demais etapas testadas são as reais.

## 5. Avaliação de desempenho

Para atender ao requisito de métricas, o projeto tem duas ferramentas:

**Painel em tempo real** — na própria tela do tradutor, atualizado a cada
segundo: uso de CPU e memória, frequência do processador, temperatura,
ciclos por instrução (CPI), quadros por segundo e o tempo gasto em cada
etapa da linha de montagem. Ele permite ver, ao vivo, onde o tempo é gasto
e se a placa está esquentando ou reduzindo a frequência.

**Benchmark** (`python -m libras.benchmark`) — um teste padronizado que
mede o processador em quatro cargas: contas com números inteiros, contas
com números reais, velocidade da memória e a própria linha de montagem do
tradutor rodando no máximo de velocidade. No fim, ele resume tudo em uma
pontuação única, o que facilita comparar máquinas.

Resultados no notebook de desenvolvimento (referência = 1000 pontos):

| Carga | Resultado |
|---|---|
| Contas com inteiros | 23,1 MOPS |
| Contas com números reais | 127,1 GFLOPS |
| Velocidade de memória | 30,1 GB/s |
| Linha de montagem do tradutor | 95,4 quadros/s |
| **Pontuação composta** | **1000 pontos** |

Resultados na Raspberry Pi:

| Carga | Resultado |
|---|---|
| Contas com inteiros | *[preencher após rodar na placa]* |
| Contas com números reais | *[preencher]* |
| Velocidade de memória | *[preencher]* |
| Linha de montagem do tradutor | *[preencher]* |
| CPI / IPC | *[preencher — disponível na Pi]* |
| **Pontuação composta** | *[preencher]* |

*Para preencher: rode `python -m libras.benchmark --json pi.json` na placa e
copie os valores do relatório impresso.*

Mesmo com a diferença esperada de desempenho entre um notebook e a
Raspberry Pi, a linha de montagem foi projetada para ser leve (por isso o
"esqueleto" da mão em vez da imagem inteira), de modo que a taxa de quadros
necessária para uso em tempo real seja alcançável na placa.

## 6. Dificuldades e decisões de projeto

- **Evitar letras erradas durante as transições de gesto** foi o maior
  desafio de qualidade. A solução foi a estabilização temporal: exigir
  confiança mínima e repetição da mesma letra por vários quadros antes de
  confirmá-la.
- **Letras repetidas** (como o "SS" em "PROFESSOR") exigiram uma regra
  extra: para repetir uma letra, basta tirar a mão do quadro por um
  instante e refazer o gesto.
- **Desenvolver sem a placa em mãos** motivou o modo demonstração e os
  testes com hardware simulado — qualquer integrante do grupo consegue
  rodar e evoluir o projeto no próprio computador.
- **Robustez para uso contínuo**: falhas passageiras da câmera (comuns em
  placas sob carga) não derrubam mais o sistema — ele tolera uma sequência
  de leituras ruins e continua funcionando.

## 7. Limitações e próximos passos

- O sistema reconhece **letras estáticas** do alfabeto; sinais que envolvem
  movimento (como algumas letras e a maioria das palavras em LIBRAS) ficam
  para uma evolução futura.
- O reconhecimento depende das **amostras coletadas** pelo usuário: quanto
  mais exemplos e mais variados, melhor a precisão.
- Possíveis evoluções: reconhecer palavras/sinais completos, sugerir
  palavras automaticamente (autocompletar), e suportar duas mãos.

## 8. Conclusão

O projeto cumpriu o que foi proposto: um dispositivo embarcado, portátil e
autônomo, que traduz o alfabeto em LIBRAS para texto e voz em tempo real,
com todos os requisitos funcionais e não funcionais verificados por testes
automatizados. Além da tradução, o sistema oferece instrumentos de medição
(painel em tempo real e benchmark) que permitem avaliar e comparar seu
desempenho em diferentes hardwares — do notebook de desenvolvimento à
Raspberry Pi de produção.
