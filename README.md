# Truco da Mesa

Truco paulista em HTML/CSS/JavaScript, com servidor Python autoritativo para jogar em vários navegadores ao mesmo tempo. Sem pacotes Python, banco de dados ou serviços externos. Cartas pixel art incluídas no projeto.

## Executar

Requer Python 3.10 ou superior. Na pasta do projeto:

```bash
python3 server.py
```

Abra **http://localhost:8765** no computador que executa o servidor. Para usar outra porta:

```bash
python3 server.py --port 8080
```

O servidor mostra também o endereço da rede local. No celular e nos outros computadores **na mesma rede Wi-Fi/LAN**, abra `http://IP-DO-COMPUTADOR:8765`. Crie uma mesa e compartilhe o convite a partir desse endereço (um convite com `localhost` só funciona no computador do servidor). Se necessário, permita TCP 8765 no firewall do computador. Não alteramos firewall nem roteador automaticamente.

Para jogar de fora da rede local, é necessário um endereço acessível pela internet: por exemplo, VPN entre os participantes ou túnel HTTPS apontando para a porta 8765. O servidor local sozinho não publica o jogo na internet. Esta aplicação é voltada a partidas entre amigos, sem contas ou proteção para hospedagem pública aberta.

## Jogar

- Digite um apelido e crie uma mesa para 4 pessoas (duplas) ou 2 (duelo).
- Convide os amigos pelo link/código. Em duplas, assentos 1/3 são Azul e 2/4 são Coral.
- O anfitrião pode completar lugares vazios com bots e iniciar a partida.
- Clique em uma carta na sua vez. Peça truco, responda a pedidos ou jogue coberta usando os controles.
- A mesa avança automaticamente após as vazas/mãos. O anfitrião pode iniciar revanche ao fim da partida.
- É possível manter várias mesas simultâneas e independentes.

A sessão fica no `sessionStorage` de cada aba. Atualizar a página reconecta ao mesmo assento. Para simular vários jogadores no mesmo computador, use abas abertas manualmente ou perfis/navegadores diferentes (abas duplicadas podem copiar a sessão). Fechar a aba perde a credencial do assento; não há transferência de assento. A mesa não tem tempo limite de jogada e espera quem desconecta. O botão “Sair da mesa” libera o assento antes do início; durante a partida, um bot assume o lugar. Se o anfitrião sair, o próximo humano se torna anfitrião. Mesas sem humanos são removidas. Partidas são mantidas em memória e reiniciar o servidor apaga tudo. Mesas sem presença humana por 24 horas são removidas.

## Regras adotadas

Perfil casual paulista, documentado também em **Como jogar** na interface:

- Baralho de 40 cartas; ordem crescente `4 5 6 7 Q J K A 2 3`.
- Três cartas por jogador; manilha é o valor seguinte à vira, com retorno de 3 para 4.
- Manilhas: ouros < espadas < copas < paus; nas cartas comuns só importa o valor.
- Duas vazas vencem a mão. Primeira empatada: próxima vaza com vencedor decide. Segunda/terceira empatada: vence quem ganhou a primeira. Três empates: sem pontos. Cartas superiores da mesma equipe não empatam entre si.
- O primeiro jogador roda a cada mão. Vencedor abre a próxima vaza; em empate abre o primeiro a jogar uma carta que empatou no topo. Sentido horário.
- Mão vale 1; pedidos seguem 3, 6, 9, 12, na própria vez e antes de jogar. A equipe que aceitou recebe o direito ao próximo pedido. Recusar entrega o valor anterior; contra-aumento aceita o pedido anterior. Qualquer integrante da equipe pode responder; vale a primeira resposta válida recebida pelo servidor.
- Com 11 pontos, a equipe vê as cartas do parceiro e decide entre jogar por 3 ou correr e entregar 1. Não há aumentos. Em 11 × 11: mão de ferro às cegas, sem aumentos.
- Carta coberta só a partir da segunda vaza, perde para qualquer carta aberta e permanece oculta aos demais.
- Sem regra de torneio de “carta exposta”. Existem variantes regionais; este jogo implementa especificamente as convenções acima.

## Pesquisa e créditos

- [Regras do Truco Paulista — Jogatina (PDF)](https://s3.amazonaws.com/static.jogatina.com/downloads/truco-paulista/regras-truco-paulista.pdf): baralho, sequência, manilhas e empates. O PDF possui um trecho inconsistente sobre truco valer 2; adotamos a escada paulista 1/3/6/9/12, confirmada pelas demais fontes.
- [Truco Arena — regras](https://trucoarena.com.br/regras): pontuação e negociação, mão de onze e manilhas.
- [Truco MTJ — regras](https://trucomtj.com.br/regras): mão de ferro e empates.
- [Cards! — SpicyGame](https://spicygame.itch.io/cards): assets originais PNG de pixel art, resolução 27 × 34, licença **CC0 1.0**. Cartas e versos estão em `static/assets/`, sem modificações. Texto do autor preservado em `static/assets/PACK-README.txt`.
- [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).

## Verificar

```bash
python3 -m unittest discover -s tests -v
```

As ações e as cartas são validadas no servidor. Tokens de sessão são aleatórios e não são enviados a outros jogadores. Cartas dos adversários, cartas cobertas e cartas próprias na mão de ferro são omitidas das respostas da API. A atualização usa polling HTTP com intervalo de 700 ms; o estado é protegido por lock e cada mesa tem seu próprio baralho, placar e sequência de jogadas.

O teste opcional de interface abre quatro contextos de navegador, aceita um pedido de truco, joga uma vaza, reconecta e verifica layouts desktop/celular. Requer Playwright apenas para desenvolvimento:

```bash
python3 -m venv /tmp/truco-tests
/tmp/truco-tests/bin/pip install playwright
/tmp/truco-tests/bin/playwright install chromium
# Com o servidor já em execução:
/tmp/truco-tests/bin/python tests/browser_smoke.py
# Ou use --browser /caminho/para/chromium com um navegador instalado.
```

As capturas são gravadas em `test-results/` (ignorado no Git).

## Aplicativos nativos offline

- **Android:** `dist/Truco-da-Mesa.apk`. Transfira o APK ao celular e abra para instalar. Compatível com Android 6 ou superior. Pacote assinado localmente para instalação direta; não publicado na Play Store. Não solicita permissão de internet. Duelo e duplas contra bots, salvamento automático, controles por toque, alto contraste, ajustes de tamanho, animações, som e tela cheia. O APK não oferece multiplayer LAN; esse modo está disponível no desktop e na versão web.
- **Linux x86_64:** `dist/Truco-da-Mesa`. Executável nativo Qt com Python e assets incluídos. Abra com duplo clique ou execute `./dist/Truco-da-Mesa`. F11 alterna tela cheia; P pausa; 1/2/3 jogam cartas. O modo offline não inicia servidor. O modo LAN é opcional.
- Para instalar o atalho Linux no menu: `python3 packaging/install_linux.py`.
- Para executar o código desktop: `python3 desktop.py` (requer PySide6). Para empacotar: `python packaging/build_native.py` em ambiente com PySide6 e PyInstaller.
- Android usa Java e componentes nativos, sem WebView. `android/build.sh` recompila com JDK, Android Platform 36 e Build Tools 36. Configure `TRUCO_ANDROID_SDK` para o diretório com as pastas `android-36` e `android-16` extraídas dos pacotes oficiais. Preserve `build/android/local.keystore` para que futuras versões mantenham a mesma assinatura.

O salvamento desktop fica na pasta de dados do usuário; no Android fica no armazenamento privado do aplicativo. Desinstalar o app Android remove a partida salva. As preferências de efeitos e visibilidade são locais.

### Mesa imersiva no navegador

Ao entrar em uma sala, a mesa ocupa a área inteira da janela, com placar, ações e cartas visíveis. O botão **Tela cheia** usa a API do navegador quando disponível; **Esc** retorna. Em navegadores sem essa API, a mesa continua ajustada à área disponível. O painel **Mesa** reúne convite, histórico, força das cartas e regras. O layout se adapta ao celular em retrato ou paisagem.

### Embaralhar e cortar

Novas mesas criadas pelo navegador têm uma sequência sincronizada antes de cada mão: embaralhamento, corte e distribuição. O jogador após o carteador escolhe de 1 a 39 cartas no controle de corte; a ordem do baralho é rotacionada no servidor antes de distribuir. Há corte automático após 10 segundos, inclusive quando o jogador não responde, e bots cortam automaticamente. O baralho preparado nunca é enviado aos clientes. O vira tem destaque próprio e animação de revelação. A preferência de movimento reduzido do sistema desliga as animações.
