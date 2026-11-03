#!/usr/bin/env python3
"""Truco da Mesa: aplicativo Qt nativo, offline por padrão."""
import argparse
import json
import math
import os
import struct
import sys
import time
import wave
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QFont, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget)

from server import GameError, RANKS, STAKES
from native.session import OfflineSession
from native.theme import STYLE, RULES
from native.widgets import CardButton, TableWidget, card_label, card_pixmap, icon


ROOT = Path(__file__).resolve().parent


def label(text='', name=None, wrap=False):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    if name:
        item.setObjectName(name)
    return item


def button(text, callback, primary=False, danger=False, name=None):
    item = QPushButton(text)
    item.setMinimumHeight(42)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.setProperty('primary', primary)
    item.setProperty('danger', danger)
    if name:
        item.setObjectName(name)
    item.clicked.connect(callback)
    return item


def panel():
    frame = QFrame()
    frame.setObjectName('panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(13)
    return frame, layout


class Sounds:
    """Pequenos efeitos sintetizados localmente; nenhum arquivo é baixado."""
    def __init__(self, parent, directory, enabled=True):
        self.enabled = enabled
        self.effects = {}
        if os.environ.get('TRUCO_NO_AUDIO'):
            return
        try:
            from PySide6.QtMultimedia import QSoundEffect
            directory.mkdir(parents=True, exist_ok=True)
            sounds = {'play': ([520, 680], .045), 'raise': ([330, 440, 660], .095),
                      'win': ([392, 494, 587, 784], .13), 'trick': ([440, 554], .065)}
            for name, (notes, duration) in sounds.items():
                path = directory / (name + '.wav')
                if not path.exists():
                    samples = bytearray()
                    for freq in notes:
                        count = int(22050 * duration)
                        for i in range(count):
                            envelope = min(1, i / 100) * (1 - i / count) ** 1.5
                            value = int(7500 * envelope * math.sin(2 * math.pi * freq * i / 22050))
                            samples.extend(struct.pack('<h', value))
                    with wave.open(str(path), 'wb') as out:
                        out.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
                        out.writeframes(samples)
                effect = QSoundEffect(parent)
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(.25)
                self.effects[name] = effect
        except (ImportError, OSError):
            self.effects = {}

    def play(self, name):
        if self.enabled and name in self.effects:
            self.effects[name].play()


class MainWindow(QMainWindow):
    def __init__(self, data_dir=None):
        super().__init__()
        self.setWindowTitle('Truco da Mesa — Offline')
        self.setWindowIcon(icon())
        self.setMinimumSize(1024, 760)
        self.resize(1280, 940)
        self.settings = QSettings('TrucoDaMesa', 'Desktop')
        self.data_dir = Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.save_path = self.data_dir / 'partida-offline.json'
        self.offline = None
        self.client = None
        self.local_host = None
        self.state = None
        self.paused_at = None
        self.last_signature = ''
        self.last_hand_signature = ''
        self.last_save = ''
        self.network_busy = False
        self._closing = False
        self.ui_scale = float(self.settings.value('ui_scale', 1.0))
        self.high_contrast = self.settings.value('high_contrast', False, type=bool)
        self.effects_on = self.settings.value('animations', True, type=bool)
        self.sound_on = self.settings.value('sound', True, type=bool)
        self.sounds = Sounds(self, self.data_dir / 'sounds', self.sound_on)
        self.build_ui()
        self.apply_preferences()
        self.timer = QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        shortcuts = [('F11', self.toggle_fullscreen), ('F1', self.show_rules), ('P', self.toggle_pause), ('T', lambda: self.act('raise'))]
        for sequence, callback in shortcuts:
            QShortcut(QKeySequence(sequence), self, activated=callback)
        for i in range(3):
            QShortcut(QKeySequence(str(i + 1)), self, activated=lambda index=i: self.play_index(index))
        self.refresh_continue()
        self.statusBar().showMessage('Pronto para jogar offline. Nenhuma conexão com a internet é necessária.')

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 18, 28, 12)
        outer.setSpacing(14)
        header = QHBoxLayout()
        brand = label('♣  TRUCO DA MESA', 'brand')
        header.addWidget(brand)
        header.addStretch()
        self.mode_badge = label('● OFFLINE', 'eyebrow')
        header.addWidget(self.mode_badge)
        header.addSpacing(18)
        header.addWidget(button('Visibilidade && efeitos', self.show_preferences, name='preferences'))
        self.fullscreen_button = button('Tela cheia  ⛶', self.toggle_fullscreen, name='fullscreen')
        self.fullscreen_button.setToolTip('Entrar ou sair da tela cheia · F11')
        header.addWidget(self.fullscreen_button)
        header.addWidget(button('Regras  F1', self.show_rules))
        outer.addLayout(header)
        divider = QFrame()
        divider.setObjectName('divider')
        outer.addWidget(divider)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self.build_home()
        self.build_game()

    def build_home(self):
        home = QWidget()
        self.pages.addWidget(home)
        grid = QGridLayout(home)
        grid.setContentsMargins(15, 25, 15, 10)
        grid.setHorizontalSpacing(45)
        left = QVBoxLayout()
        left.addWidget(label('SUA MESA. SEU TEMPO.', 'eyebrow'))
        title = label('A resenha agora\né offline.', 'title')
        title.setMinimumHeight(140)
        left.addWidget(title)
        left.addWidget(label('Abra o aplicativo, escolha sua dupla e jogue.\nSem navegador. Sem cadastro. Sem internet.', 'subtitle', True))
        self.home_cards = QLabel()
        self.home_cards.setMinimumHeight(180)
        self.home_cards.setAlignment(Qt.AlignmentFlag.AlignCenter)
        from PySide6.QtGui import QPainter
        image = QPixmap(460, 210)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        for x, angle, c in [(85, -17, {'rank':'3','suit':'Hearts'}), (196, 0, {'rank':'A','suit':'Spades'}), (307, 17, {'rank':'7','suit':'Clubs'})]:
            painter.save()
            painter.translate(x, 100)
            painter.rotate(angle)
            painter.drawPixmap(-54, -68, 108, 136, card_pixmap(c))
            painter.restore()
        painter.end()
        self.home_cards.setPixmap(image)
        left.addWidget(self.home_cards, 1)
        left.addWidget(label('CARTAS GRANDES  ·  BOTS  ·  SALVAMENTO AUTOMÁTICO', 'eyebrow'))
        grid.addLayout(left, 0, 0)
        frame, controls = panel()
        controls.addWidget(label('PUXE UMA CADEIRA', 'eyebrow'))
        controls.addWidget(label('A próxima mão é sua.', 'subtitle'))
        controls.addWidget(label('SEU APELIDO', 'eyebrow'))
        self.nickname = QLineEdit(str(self.settings.value('nickname', 'Você')))
        self.nickname.setObjectName('nickname')
        self.nickname.setMaxLength(24)
        self.nickname.setPlaceholderText('Como vamos te chamar?')
        controls.addWidget(self.nickname)
        self.duplas_button = button('Jogar em duplas  ·  2 × 2', lambda: self.new_offline(4), primary=True, name='offline-duplas')
        controls.addWidget(self.duplas_button)
        controls.addWidget(button('Jogar um duelo  ·  1 × 1', lambda: self.new_offline(2), name='offline-duelo'))
        self.continue_button = button('Continuar partida salva  →', self.resume_saved, name='continue')
        controls.addWidget(self.continue_button)
        self.save_note = label('', 'subtitle', True)
        controls.addWidget(self.save_note)
        controls.addSpacing(14)
        controls.addWidget(label('COM AMIGOS, SEM INTERNET', 'eyebrow'))
        controls.addWidget(label('Use a mesma rede Wi-Fi ou um roteador local. Cada pessoa joga no seu aparelho.', 'subtitle', True))
        controls.addWidget(button('Jogar na rede local  →', self.show_lan, name='lan'))
        grid.addWidget(frame, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        hint = label('F11: tela cheia    ·    1 / 2 / 3: jogar carta    ·    T: truco    ·    P: pausar', 'subtitle')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(hint, 1, 0, 1, 2)

    def build_game(self):
        self.game_page = QWidget()
        self.pages.addWidget(self.game_page)
        grid = QGridLayout(self.game_page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        top = QHBoxLayout()
        self.game_title = label('Resenha offline', 'subtitle')
        top.addWidget(self.game_title, 1)
        self.pause_button = button('Pausar  P', self.toggle_pause, name='pause')
        top.addWidget(self.pause_button)
        top.addWidget(button('Voltar ao início', self.go_home, name='home'))
        grid.addLayout(top, 0, 0, 1, 2)
        self.score = label('', 'score')
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score.setAccessibleName('Placar das equipes')
        grid.addWidget(self.score, 1, 0)
        self.board = TableWidget()
        self.board.setObjectName('board')
        self.board.setAccessibleName('Mesa de truco, cartas e participantes')
        grid.addWidget(self.board, 2, 0)
        self.status = label('', 'status', True)
        self.status.setMinimumHeight(36)
        self.status.setAccessibleName('Estado da partida')
        grid.addWidget(self.status, 3, 0)
        self.actions_widget = QWidget()
        actions = QHBoxLayout(self.actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        self.covered = QCheckBox('Jogar coberta')
        self.covered.setToolTip('Disponível a partir da segunda vaza. A carta fica oculta e perde para cartas abertas.')
        actions.addWidget(self.covered)
        actions.addStretch()
        self.fill_button = button('Completar com bots', lambda: self.act('bots'), name='fill-bots')
        self.start_button = button('Começar partida →', lambda: self.act('start'), primary=True, name='start')
        self.raise_button = button('TRUCO!  T', lambda: self.act('raise'), danger=True, name='raise')
        self.run_button = button('Correr', lambda: self.act('respond', answer='run'), name='run')
        self.accept_button = button('Aceitar', lambda: self.act('respond', answer='accept'), primary=True, name='accept')
        self.reraise_button = button('Aumentar', lambda: self.act('respond', answer='raise'), danger=True, name='reraise')
        self.rematch_button = button('Jogar novamente  ↻', lambda: self.act('rematch'), primary=True, name='rematch')
        for item in [self.fill_button, self.start_button, self.raise_button, self.run_button, self.accept_button, self.reraise_button, self.rematch_button]:
            actions.addWidget(item)
        grid.addWidget(self.actions_widget, 4, 0)
        self.hand_widget = QWidget()
        self.hand_layout = QHBoxLayout(self.hand_widget)
        self.hand_layout.setContentsMargins(0, 5, 0, 5)
        self.hand_layout.setSpacing(20)
        self.hand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.hand_widget, 5, 0)
        self.hand_buttons = []
        self.hand_hint = label('Sua mão · só você pode ver estas cartas.', 'eyebrow')
        self.hand_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.hand_hint, 6, 0)
        self.side_panel, side = panel()
        self.side_panel.setFixedWidth(256)
        self.room_info = label('OFFLINE · SALVO NO COMPUTADOR', 'eyebrow', True)
        side.addWidget(self.room_info)
        side.addWidget(label('Força das cartas', 'subtitle'))
        order = label('4  5  6  7  Q  J  K  A  2  3')
        order.setStyleSheet('font-family: monospace; font-size: 14px; font-weight: bold;')
        side.addWidget(order)
        side.addWidget(label('MENOR  ─────────→  MAIOR', 'eyebrow'))
        side.addWidget(label('Manilhas: ♦ < ♠ < ♥ < ♣', 'subtitle', True))
        self.manilha_info = label('', 'subtitle', True)
        side.addWidget(self.manilha_info)
        side.addSpacing(12)
        side.addWidget(label('CARTAS DO PARCEIRO', 'eyebrow'))
        self.partner_widget = QWidget()
        self.partner_layout = QHBoxLayout(self.partner_widget)
        self.partner_layout.setContentsMargins(0, 0, 0, 0)
        self.partner_layout.setSpacing(5)
        side.addWidget(self.partner_widget)
        self.partner_hint = label('Disponíveis na mão de onze.', 'subtitle', True)
        side.addWidget(self.partner_hint)
        side.addSpacing(10)
        side.addWidget(label('ACONTECEU NA MESA', 'eyebrow'))
        self.history_list = QListWidget()
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_list.setWordWrap(True)
        side.addWidget(self.history_list, 1)
        grid.addWidget(self.side_panel, 1, 1, 6, 1)
        grid.setColumnStretch(0, 1)
        grid.setRowStretch(2, 1)

    def apply_preferences(self):
        base_size = round(12 * self.ui_scale)
        style = STYLE + f'\nQWidget {{ font-size: {base_size}px; }} QLabel#subtitle {{ font-size: {round(13*self.ui_scale)}px; }} QLabel#status {{ font-size: {round(14*self.ui_scale)}px; font-weight: bold; }} QPushButton {{ font-size: {base_size}px; }} QListWidget {{ font-size: {base_size}px; }}'
        if self.high_contrast:
            style += '\nQWidget {color:#0c2419;} QLabel#subtitle,QLabel#eyebrow {color:#354b2c;} QLineEdit,QComboBox {border:2px solid #466343;} QPushButton {border-width:2px;} QLabel#status {background:#e5ecd7;padding:9px;} QListWidget {color:#10281d;}'
        self.setStyleSheet(style)
        self.side_panel.setFixedWidth(300 if self.ui_scale > 1.0 else 256)
        self.board.high_contrast = self.high_contrast
        self.board.animations = self.effects_on
        self.board.scale = self.ui_scale
        self.board.clock.setInterval(40 if self.effects_on else 1000)
        self.sounds.enabled = self.sound_on
        self.last_hand_signature = ''
        self.last_signature = ''
        if self.state:
            self.render(self.state)

    def remember_name(self):
        name = self.nickname.text().strip() or 'Você'
        self.settings.setValue('nickname', name)
        return name

    def new_offline(self, capacity):
        if self.save_path.exists() and self.continue_button.isEnabled():
            answer = QMessageBox.question(self, 'Nova partida', 'Uma nova partida substituirá a partida salva. Começar?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.disconnect_lan()
        self.offline = OfflineSession(self.remember_name(), capacity)
        self.paused_at = None
        self.enter_game()
        self.render(self.offline.view())
        self.save_offline()

    def enter_game(self):
        self.last_signature = ''
        self.last_hand_signature = ''
        self.pages.setCurrentWidget(self.game_page)
        self.pause_button.setVisible(self.offline is not None)
        self.pause_button.setText('Pausar  P')
        self.mode_badge.setText('● OFFLINE' if self.offline else '● REDE LOCAL')
        self.setWindowTitle('Truco da Mesa — ' + ('Offline' if self.offline else 'Rede local'))

    def refresh_continue(self):
        exists = self.save_path.is_file()
        self.continue_button.setEnabled(exists)
        self.save_note.setText('Uma partida foi salva. Continue de onde parou.' if exists else 'Sua partida será salva automaticamente neste computador.')

    def resume_saved(self):
        try:
            self.disconnect_lan()
            self.offline = OfflineSession.load(self.save_path)
            self.paused_at = None
            self.enter_game()
            self.render(self.offline.view())
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            self.notify('Não foi possível abrir a partida salva. Você pode começar uma nova. ' + str(error))
            self.continue_button.setEnabled(False)

    def save_offline(self):
        if not self.offline:
            return
        try:
            self.offline.save(self.save_path)
            self.refresh_continue()
        except OSError as error:
            self.statusBar().showMessage(f'Não foi possível salvar: {error}')

    def tick(self):
        if self.offline and self.pages.currentWidget() == self.game_page and self.paused_at is None:
            try:
                previous = json.dumps({k: v for k, v in self.offline.view().items() if k != 'next_in'}, sort_keys=True)
                state = self.offline.tick()
                self.render(state)
                if json.dumps({k: v for k, v in state.items() if k != 'next_in'}, sort_keys=True) != previous:
                    self.save_offline()
            except (GameError, ValueError, IndexError) as error:
                self.notify(str(error))
                self.pause_game(True)

    def act(self, action, **data):
        if self.paused_at is not None or self.pages.currentWidget() != self.game_page:
            return
        if not self.state:
            return
        if action == 'raise' and not self.state['can_raise']:
            return
        try:
            if self.offline:
                self.render(self.offline.action(action, **data))
                self.save_offline()
            elif self.client:
                self.client.action(action, **data)
        except GameError as error:
            self.notify(str(error))

    def play_card(self, identity):
        self.act('play', card=identity, covered=self.covered.isChecked())

    def play_index(self, index):
        if index < len(self.hand_buttons) and self.hand_buttons[index].isEnabled():
            self.hand_buttons[index].click()

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def render(self, state):
        signature = json.dumps(state, sort_keys=True) + str(self.paused_at is not None)
        if signature == self.last_signature:
            return
        previous = self.state
        self.state = state
        self.last_signature = signature
        s = state
        if previous:
            if s['phase'] == 'finished' and previous['phase'] != 'finished':
                self.sounds.play('win')
            elif s['pending'] and s['pending'] != previous['pending']:
                self.sounds.play('raise')
            elif len(s['results']) > len(previous['results']):
                self.sounds.play('trick')
            elif len(s['table']) > len(previous['table']):
                self.sounds.play('play')
        self.board.paused = self.paused_at is not None
        self.board.set_state(s)
        self.game_title.setText(('Partida offline' if self.offline else 'Mesa ' + s['code']) + ('  ·  Duplas 2 × 2' if s['capacity'] == 4 else '  ·  Duelo 1 × 1'))
        own_team = s['seat'] % 2
        self.score.setText(f'AZUL  {s["score"][0]:02}    ×    {s["score"][1]:02}  CORAL      ·      ' + (f'MÃO {s["hand_no"]:02}' if s['hand_no'] else 'AGUARDANDO'))
        self.score.setToolTip('Sua equipe: ' + ('Azul' if own_team == 0 else 'Coral') + '. Vence quem chega a 12 pontos.')
        your_turn = s['phase'] == 'playing' and not s['pending'] and s['turn'] == s['seat'] and self.paused_at is None
        respond = (s['eleven'] == own_team if s['phase'] == 'eleven' else bool(s['pending']) and s['pending']['team'] != own_team) and self.paused_at is None
        if self.paused_at is not None:
            text = 'PARTIDA PAUSADA · Suas cartas e o placar estão salvos. Pressione P para continuar.'
        elif s['phase'] == 'lobby':
            text = f'Mesa aberta: {len(s["players"])} de {s["capacity"]} lugares. Convide a turma ou complete com bots.'
        elif s['phase'] == 'eleven':
            text = 'MÃO DE ONZE · Confira as cartas do parceiro e decida: jogar por 3 ou correr.' if respond else 'A equipe com onze está decidindo se joga.'
        elif s['pending']:
            text = f'DESAFIO: {s["pending"]["value"]} PONTOS! ' + ('Sua equipe aceita, corre ou aumenta?' if respond else 'Aguardando a resposta dos adversários…')
        elif s['phase'] == 'playing':
            text = ('SUA VEZ · Escolha uma carta (1 / 2 / 3).' if not s['iron'] else 'MÃO DE FERRO · Escolha uma carta às cegas.') if your_turn else f'É a vez de {s["players"][s["turn"]]["name"]}.'
        elif s['phase'] in ('trick_end', 'hand_end'):
            text = s['log'][-1] + f' Próxima jogada em {s["next_in"]}s…'
        else:
            text = ('VITÓRIA! Sua equipe levou a partida.' if s['winner'] == own_team else 'Fim de partida. Dessa vez os adversários levaram.')
        self.status.setText(text)
        self.fill_button.setVisible(s['phase'] == 'lobby' and s['host'] and len(s['players']) < s['capacity'])
        self.start_button.setVisible(s['phase'] == 'lobby' and s['host'])
        self.start_button.setEnabled(len(s['players']) == s['capacity'])
        self.raise_button.setVisible(s['can_raise'] and self.paused_at is None)
        if s['stake'] < 12:
            value = STAKES[STAKES.index(s['stake']) + 1]
            self.raise_button.setText('TRUCO!  T' if value == 3 else f'PEDIR {value}!  T')
        self.accept_button.setVisible(respond)
        self.accept_button.setText('Jogar por 3' if s['phase'] == 'eleven' else 'Aceitar')
        self.run_button.setVisible(respond)
        self.reraise_button.setVisible(respond and s['phase'] != 'eleven' and s['pending']['value'] < 12)
        if s['pending'] and s['pending']['value'] < 12:
            self.reraise_button.setText('Pedir ' + str(STAKES[STAKES.index(s['pending']['value']) + 1]))
        self.rematch_button.setVisible(s['phase'] == 'finished' and s['host'])
        self.covered.setVisible(your_turn)
        self.covered.setEnabled(bool(s['results']))
        if not s['results']:
            self.covered.setChecked(False)
        hand_signature = json.dumps(s['hand'], sort_keys=True) + str(your_turn) + str(self.ui_scale)
        if hand_signature != self.last_hand_signature:
            self.last_hand_signature = hand_signature
            self.clear_layout(self.hand_layout)
            self.hand_buttons = []
            size = round(108 * self.ui_scale / 27) * 27
            for index, c in enumerate(s['hand']):
                item = CardButton(c, index, size, self.play_card)
                item.setEnabled(your_turn)
                self.hand_layout.addWidget(item)
                self.hand_buttons.append(item)
        self.hand_hint.setText('CARTAS ÀS CEGAS · MÃO DE FERRO' if s['iron'] else 'SUA MÃO · 1 / 2 / 3 PARA JOGAR' if your_turn else 'SUA MÃO · SÓ VOCÊ PODE VER ESTAS CARTAS')
        self.clear_layout(self.partner_layout)
        for c in s['partner']:
            item = QLabel()
            item.setPixmap(card_pixmap(c).scaled(54, 68, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
            item.setAccessibleName(card_label(c))
            self.partner_layout.addWidget(item)
        self.partner_hint.setVisible(not s['partner'])
        if s['vira']:
            rank = RANKS[(RANKS.index(s['vira']['rank']) + 1) % len(RANKS)]
            self.manilha_info.setText(f'Manilhas desta mão: {rank}\nSuperam todas as cartas comuns.')
        self.history_list.clear()
        self.history_list.addItems(list(reversed(s['log'][-12:])))
        if self.offline:
            self.room_info.setText('OFFLINE · SALVAMENTO AUTOMÁTICO')
            self.statusBar().showMessage('Sem internet · Sua equipe: ' + ('Azul' if own_team == 0 else 'Coral') + ' · F11: tela cheia · F1: regras')
        elif self.client:
            address = self.local_host.addresses()[0] if self.local_host else self.client.base
            self.room_info.setText(f'CONVITE PARA A TURMA\n\n{address}\n\nCÓDIGO: {s["code"]}')
            self.statusBar().showMessage(f'Rede local · {address} · Código {s["code"]} · O anfitrião precisa manter o aplicativo aberto.')

    def pause_game(self, pause):
        if not self.offline:
            return
        if pause and self.paused_at is None:
            self.paused_at = time.time()
            self.offline.set_paused(True)
            self.save_offline()
        elif not pause and self.paused_at is not None:
            self.offline.set_paused(False)
            self.paused_at = None
        self.pause_button.setText('Continuar  P' if self.paused_at is not None else 'Pausar  P')
        self.last_signature = ''
        self.render(self.offline.view())

    def toggle_pause(self):
        if self.pages.currentWidget() == self.game_page and self.offline:
            self.pause_game(self.paused_at is None)

    def go_home(self):
        if self.offline:
            self.pause_game(True)
            self.save_offline()
            self.offline = None
        elif self.client:
            if self.local_host:
                answer = QMessageBox.question(self, 'Encerrar mesa local', 'Você é o anfitrião. Voltar ao início desconectará os jogadores desta mesa. Encerrar?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            self.disconnect_lan()
        self.state = None
        self.pages.setCurrentIndex(0)
        self.mode_badge.setText('● OFFLINE')
        self.setWindowTitle('Truco da Mesa — Offline')
        self.refresh_continue()
        self.statusBar().showMessage('Partida offline salva automaticamente. Você pode continuar depois.')

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self.fullscreen_button.setText('Sair da tela cheia  ⛶' if self.isFullScreen() else 'Tela cheia  ⛶')

    def modal(self, dialog):
        already_paused = self.paused_at is not None
        self.pause_game(True)
        dialog.exec()
        if not already_paused:
            self.pause_game(False)

    def show_rules(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Regras, atalhos e créditos — disponível offline')
        dialog.resize(740, 650)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(RULES)
        layout.addWidget(browser)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        self.modal(dialog)

    def show_preferences(self):
        dialog = QDialog(self)
        dialog.setObjectName('preferences-dialog')
        dialog.setWindowTitle('Visibilidade & efeitos')
        dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(18)
        layout.addWidget(label('DEIXE A MESA DO SEU JEITO', 'eyebrow'))
        layout.addWidget(label('Tamanho dos textos e cartas'))
        scale = QComboBox()
        scale.setObjectName('visibility-scale')
        for name, value in [('Grande · 100%', 1.0), ('Maior · 125%', 1.25), ('Extra grande · 150%', 1.5)]:
            scale.addItem(name, value)
        scale.setCurrentIndex(max(0, scale.findData(self.ui_scale)))
        layout.addWidget(scale)
        contrast = QCheckBox('Alto contraste · textos e mesa mais definidos')
        contrast.setObjectName('high-contrast')
        contrast.setChecked(self.high_contrast)
        layout.addWidget(contrast)
        motion = QCheckBox('Animações · jogadas, indicador de vez e vitória')
        motion.setChecked(self.effects_on)
        layout.addWidget(motion)
        sound = QCheckBox('Efeitos sonoros · cartas, truco e vitória')
        sound.setChecked(self.sound_on)
        layout.addWidget(sound)
        fullscreen = QCheckBox('Tela cheia (também disponível com F11)')
        fullscreen.setChecked(self.isFullScreen())
        layout.addWidget(fullscreen)
        layout.addWidget(label('As preferências são salvas neste computador.\nA partida offline fica pausada enquanto este painel estiver aberto.', 'subtitle', True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Aplicar')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancelar')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        self.modal(dialog)
        if dialog.result() == QDialog.DialogCode.Accepted:
            self.ui_scale = scale.currentData()
            self.high_contrast = contrast.isChecked()
            self.effects_on = motion.isChecked()
            self.sound_on = sound.isChecked()
            for key, value in [('ui_scale', self.ui_scale), ('high_contrast', self.high_contrast), ('animations', self.effects_on), ('sound', self.sound_on)]:
                self.settings.setValue(key, value)
            if fullscreen.isChecked() != self.isFullScreen():
                self.toggle_fullscreen()
            self.apply_preferences()

    def notify(self, message):
        self.statusBar().showMessage(message, 8000)

    def show_lan(self):
        from native.network import LanClient, LocalHost, normalize_address
        dialog = QDialog(self)
        dialog.setWindowTitle('Jogar com amigos na rede local')
        dialog.resize(510, 440)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(26, 25, 26, 25)
        layout.setSpacing(15)
        layout.addWidget(label('MESMA REDE. A MESMA RESENHA.', 'eyebrow'))
        layout.addWidget(label('Todos precisam estar na mesma rede Wi-Fi/LAN. Não é necessário ter acesso à internet.', 'subtitle', True))
        mode = QComboBox()
        mode.addItem('Duplas · 4 jogadores', 4)
        mode.addItem('Duelo · 2 jogadores', 2)
        layout.addWidget(mode)
        hosting = button('Abrir uma mesa neste computador', lambda: dialog.done(2), primary=True)
        layout.addWidget(hosting)
        layout.addSpacing(8)
        layout.addWidget(label('OU ENTRE NA MESA DE UM AMIGO', 'eyebrow'))
        address = QLineEdit()
        address.setPlaceholderText('IP do anfitrião:porta · ex.: 192.168.1.10:8766')
        address.setText(str(self.settings.value('lan-address', '')))
        layout.addWidget(address)
        code = QLineEdit()
        code.setMaxLength(8)
        code.setPlaceholderText('Código da mesa')
        layout.addWidget(code)
        join = button('Entrar na mesa', lambda: dialog.done(3))
        layout.addWidget(join)
        self.modal(dialog)
        result = dialog.result()
        if result not in (2, 3):
            return
        self.disconnect_lan()
        self.offline = None
        try:
            if result == 2:
                self.local_host = LocalHost()
                base = f'http://127.0.0.1:{self.local_host.port}'
            else:
                base = normalize_address(address.text())
                if not code.text().strip():
                    raise ValueError('Digite o código da mesa.')
                self.settings.setValue('lan-address', address.text())
            self.client = LanClient(base, self)
            self.client.changed.connect(self.lan_update)
            self.client.failed.connect(self.notify)
            self.client.joined.connect(self.enter_game)
            self.client.connect_room(self.remember_name(), code.text().strip().upper() if result == 3 else None, mode.currentData())
            self.statusBar().showMessage('Conectando à mesa na rede local…')
        except (OSError, ValueError) as error:
            self.disconnect_lan()
            self.notify(str(error))

    def lan_update(self, state):
        if self.client:
            self.render(state)

    def disconnect_lan(self):
        if self.client:
            self.client.changed.disconnect()
            self.client.failed.disconnect()
            self.client.joined.disconnect()
            self.client.leave()
            self.client = None
        if self.local_host:
            self.local_host.close()
            self.local_host = None

    def closeEvent(self, event):
        if self.local_host and not self._closing:
            answer = QMessageBox.question(self, 'Encerrar aplicativo', 'Encerrar também desconectará os amigos desta mesa local. Fechar?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closing = True
        self.timer.stop()
        self.save_offline()
        self.disconnect_lan()
        self.settings.sync()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fullscreen', action='store_true', help='Abrir em tela cheia')
    parser.add_argument('--data-dir', type=Path, help='Diretório alternativo de dados/salvamento')
    parser.add_argument('--smoke-test', action='store_true', help='Validar assets e iniciar/encerrar sem interação')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Truco da Mesa')
    app.setOrganizationName('TrucoDaMesa')
    app.setApplicationVersion('1.0.0')
    app.setWindowIcon(icon())
    window = MainWindow(args.data_dir)
    if args.smoke_test:
        assert not card_pixmap({'rank':'A','suit':'Spades'}).isNull(), 'Assets ausentes no executável'
        window.offline = OfflineSession('Teste', 4)
        window.enter_game()
        window.render(window.offline.view())
        window.show()
        def complete():
            assert len(window.hand_buttons) == 3
            window.offline = None
            window.close()
            print('Native smoke test OK', flush=True)
        QTimer.singleShot(300, complete)
    elif args.fullscreen:
        window.toggle_fullscreen()
    else:
        window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
