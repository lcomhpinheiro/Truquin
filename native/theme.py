STYLE = '''
QWidget { background: #f4f1e8; color: #203b32; font-family: "DejaVu Sans"; font-size: 12px; }
QMainWindow { background: #f4f1e8; }
QLabel { background: transparent; }
QLabel#brand { font-size: 18px; font-weight: bold; letter-spacing: 2px; }
QLabel#eyebrow { color: #75846b; font-family: monospace; font-size: 10px; letter-spacing: 2px; }
QLabel#title { font-family: "DejaVu Serif"; font-size: 41px; }
QLabel#subtitle { color: #75816e; font-size: 13px; }
QLabel#score { background: #203b32; color: #f4f1e8; padding: 15px 22px; font-family: monospace; font-size: 21px; }
QLabel#status { font-size: 12px; padding: 8px 0; }
QFrame#panel { border: 1px solid #d8ddce; background: #fffdf6; }
QFrame#divider { background: #d8ddce; max-height: 1px; border: none; }
QPushButton { background: #f8f6ed; border: 1px solid #c4cdb8; padding: 11px 17px; color: #203b32; font-size: 12px; }
QPushButton:hover { background: #e7ecdc; border-color: #6a8767; }
QPushButton:pressed { background: #dbe5d2; }
QPushButton:disabled { color: #a6ae9a; border-color: #dde1d4; background: #eeeede; }
QPushButton[primary="true"] { background: #245b43; color: #fffcf2; border: 1px solid #173d2c; font-weight: bold; }
QPushButton[primary="true"]:hover { background: #347455; }
QPushButton[danger="true"] { background: #d87960; color: #2b2117; border-color: #a85c48; font-weight: bold; }
QPushButton#card { background: transparent; border: 2px solid transparent; padding: 2px; }
QPushButton#card:hover:enabled { background: #e3e9d6; border-color: #879b70; }
QPushButton#card:disabled { background: transparent; }
QLineEdit, QComboBox { background: #faf8f0; border: 1px solid #cfd7c2; padding: 11px; selection-background-color: #49775b; }
QLineEdit:focus { border-color: #49775b; }
QCheckBox { background: transparent; spacing: 8px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #9dab8b; background: #faf8f0; }
QCheckBox::indicator:checked { background: #397453; }
QListWidget { background: #fffdf6; border: none; padding: 5px; font-size: 11px; }
QListWidget::item { padding: 6px 2px; }
QTextBrowser { background: #fffdf6; border: 1px solid #d8ddce; padding: 16px; }
QStatusBar { background: #e8ecdf; font-size: 11px; }
QScrollArea { border: none; }
QToolTip { background: #203b32; color: #fffdf6; padding: 6px; border: none; }
'''

RULES = '''<h1>As regras da nossa mesa</h1>
<p>Truco paulista casual: 40 cartas, 3 por pessoa e partida até 12 pontos. Duplas em assentos alternados.</p>
<h3>Cartas e manilhas</h3><p>Da menor à maior: <b>4 5 6 7 Q J K A 2 3</b>. A manilha é o valor seguinte à vira, retornando de 3 para 4. Toda manilha vence cartas comuns. Entre manilhas: <b>♦ &lt; ♠ &lt; ♥ &lt; ♣</b>.</p>
<h3>Vazas e empates</h3><p>Duas vazas vencem a mão. Se a primeira empata, a próxima com vencedor decide. Se a segunda ou terceira empata, leva quem ganhou a primeira. Três empates: sem pontos. As cartas mais altas da mesma dupla não empatam entre si. Quem venceu abre a próxima; em empate, abre quem primeiro jogou uma carta que empatou no topo.</p>
<h3>Truco!</h3><p>A mão começa em 1 e pode subir para <b>3 → 6 → 9 → 12</b>. Peça na sua vez, antes de jogar. Correr entrega o valor anterior. Contra-aumentar aceita o pedido anterior. Quem aceitou pode pedir o próximo aumento. A vez de jogar é preservada.</p>
<h3>Onze e ferro</h3><p>Com 11 pontos, veja as cartas do parceiro e decida: jogar por 3 ou correr e entregar 1. Sem aumentos. Em 11 × 11, mão de ferro: cartas às cegas, sem aumentos.</p>
<h3>Carta coberta</h3><p>A partir da segunda vaza, perde para qualquer carta aberta e fica oculta aos outros. Perfil casual, sem regra de torneio de carta exposta.</p>
<h3>Teclas</h3><p><b>1 / 2 / 3</b>: jogar carta · <b>T</b>: pedir aumento · <b>P</b>: pausar offline · <b>F11</b>: tela cheia · <b>F1</b>: regras.</p>
<h3>Offline e rede local</h3><p>Offline joga diretamente no computador, sem servidor e sem conexão. A partida é salva automaticamente. Em rede local, todos precisam estar na mesma rede Wi-Fi/LAN, que pode funcionar sem internet. O anfitrião precisa manter o aplicativo aberto.</p>
<h3>Créditos</h3><p>Cartas pixel art: <b>Cards! · SpicyGame</b>, licença CC0 1.0, arquivos incluídos no aplicativo. Referências das regras: Jogatina, Truco Arena e Truco MTJ. Este texto e todos os assets estão disponíveis offline.</p>'''
