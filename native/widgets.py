"""Widgets Qt dessinados localmente: mesa, cartas e efeitos visuais."""
import math
import random
import time
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QVariantAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QPushButton, QSizePolicy

ASSETS = Path(__file__).resolve().parent.parent / 'static' / 'assets'
SUIT_LABEL = {'Clubs': 'paus', 'Hearts': 'copas', 'Spades': 'espadas', 'Diamonds': 'ouros'}
SUIT_SYMBOL = {'Clubs': '♣', 'Hearts': '♥', 'Spades': '♠', 'Diamonds': '♦'}
PIXMAPS = {}


def card_path(card):
    if not card or card.get('blind') or card.get('covered'):
        return ASSETS / 'Backs' / 'back_0.png'
    value = {'A': 1, 'J': 11, 'Q': 12, 'K': 13}.get(card['rank'], card['rank'])
    return ASSETS / card['suit'] / f"{card['suit']}_card_{int(value):02}.png"


def card_pixmap(card):
    path = str(card_path(card))
    if path not in PIXMAPS:
        PIXMAPS[path] = QPixmap(path)
    return PIXMAPS[path]


def card_label(card):
    if not card or card.get('blind'):
        return 'Carta às cegas'
    if card.get('covered'):
        return 'Carta coberta'
    return f"{card['rank']} de {SUIT_LABEL[card['suit']]}"


def icon():
    image = QPixmap(128, 128)
    image.fill(QColor('#203b32'))
    painter = QPainter(image)
    painter.setPen(QColor('#f8f1df'))
    painter.setFont(QFont('DejaVu Sans', 84))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, '♣')
    painter.end()
    return QIcon(image)


class CardButton(QPushButton):
    def __init__(self, card, index, size, callback, parent=None):
        super().__init__(parent)
        self.setObjectName('card')
        self.card = card
        face = card_pixmap(card).scaled(size, round(size * 34 / 27), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        card_icon = QIcon(face)
        card_icon.addPixmap(face, QIcon.Mode.Disabled)
        self.setIcon(card_icon)
        self.setIconSize(QSize(size, round(size * 34 / 27)))
        self.setFixedSize(size + 12, round(size * 34 / 27) + 12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f'{index + 1} · Jogar {card_label(card)}')
        self.setAccessibleName(f'Jogar carta {index + 1}: {card_label(card)}')
        self.clicked.connect(lambda: callback(card['id']))


class TableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = None
        self.paused = False
        self.high_contrast = False
        self.animations = True
        self.scale = 1.0
        self.progress = 1.0
        self.victory_started = 0
        self.frame = time.monotonic()
        self.setMinimumSize(520, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(300)
        self.animation.setStartValue(0.)
        self.animation.setEndValue(1.)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.animate)
        self.clock = QTimer(self)
        self.clock.setInterval(40)
        self.clock.timeout.connect(self.update)
        self.clock.start()
        rng = random.Random(23)
        self.particles = [(rng.random(), rng.random(), rng.choice(['#e8c471', '#83c8df', '#ed987b', '#d5ead4'])) for _ in range(60)]

    def animate(self, value):
        self.progress = float(value)
        self.update()

    def set_state(self, state):
        previous = self.state
        self.state = state
        if self.animations and previous and len(state['table']) > len(previous['table']):
            self.animation.stop()
            self.animation.start()
        else:
            self.progress = 1
        if state['phase'] == 'finished' and (not previous or previous['phase'] != 'finished'):
            self.victory_started = time.monotonic()
        self.update()

    def text(self, painter, rect, message, size=12, color='#eaf3d9', bold=False, family='DejaVu Sans'):
        painter.setPen(QColor(color))
        font = QFont(family)
        font.setPixelSize(max(9, round(size * self.scale)))
        font.setBold(bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, message)

    def draw_card(self, painter, c, x, y, width, height, shadow=True):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if shadow:
            painter.fillRect(QRectF(x + 4, y + 5, width, height), QColor(0, 0, 0, 65))
        painter.drawPixmap(QRectF(x, y, width, height), card_pixmap(c), QRectF(card_pixmap(c).rect()))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor('#143a2d' if self.high_contrast else '#34765b'))
        gradient.setColorAt(1, QColor('#092b20' if self.high_contrast else '#1c4d39'))
        p.setPen(QPen(QColor('#162f24'), 7))
        p.setBrush(gradient)
        p.drawRoundedRect(QRectF(4, 4, w - 8, h - 8), 22, 22)
        p.setPen(QPen(QColor('#87a57555'), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(27, 23, w - 54, h - 46), 90, 90)
        if not self.state:
            self.text(p, QRectF(0, 0, w, h), '♣  TRUCO DA MESA', 28, '#dceacd', True)
            return
        s = self.state
        cx, cy = w / 2, h / 2
        compact = h < 350
        for i in range(s['capacity']):
            relative = (i - s['seat']) % s['capacity']
            if s['capacity'] == 2:
                pos = 'bottom' if relative == 0 else 'top'
            else:
                pos = ['bottom', 'left', 'top', 'right'][relative]
            x, y = {'bottom': (cx, h - 52), 'top': (cx, 46), 'left': (78, cy), 'right': (w - 78, cy)}[pos]
            player = s['players'][i] if i < len(s['players']) else None
            active = player and s['phase'] == 'playing' and not s['pending'] and s['turn'] == i
            team_color = '#9ad9f0' if i % 2 == 0 else '#ffb29c'
            if active:
                pulse = (math.sin(time.monotonic() * 3) + 1) / 2 if self.animations else .5
                p.setBrush(QColor(235, 203, 111, int(35 + pulse * 45)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(x - 70, y - 37, 140, 72), 10, 10)
            p.setBrush(QColor('#163e2d'))
            p.setPen(QPen(QColor('#f5d277' if active else team_color), 2))
            p.drawRoundedRect(QRectF(x - 19, y - 32, 38, 32), 4, 4)
            self.text(p, QRectF(x - 19, y - 32, 38, 32), player['name'][0].upper() if player else '+', 19, '#f5d277' if active else team_color, True)
            name = (player['name'][:17] + (' · você' if i == s['seat'] else '')) if player else 'Lugar livre'
            self.text(p, QRectF(x - 90, y + 3, 180, 22), name, 12, '#ffffff', True)
            note = 'SUA VEZ' if active else ('BOT' if player and player['bot'] else 'DESCONECTADO' if player and not player['online'] else 'SUA DUPLA' if i % 2 == s['seat'] % 2 else 'ADVERSÁRIO')
            self.text(p, QRectF(x - 90, y + 24, 180, 18), note, 9, '#ffe393' if active else team_color)
            if player and pos in ('left', 'right') and not compact:
                for n in range(player['count']):
                    self.draw_card(p, None, x - 17 + n * 10, y + 46, 21.6, 27.2, False)
        card_w = min(81 * self.scale, (w - 320) / 4.6, (h - 190) * .8)
        card_w = max(40.5, card_w)
        card_h = card_w * 34 / 27
        if not s['table']:
            self.text(p, QRectF(cx - 120, cy - 34, 240, 60), '♣', 49, '#b4d5a43c')
        total = len(s['table']) * (card_w + 13) - 13
        for index, play in enumerate(s['table']):
            x = cx - total / 2 + index * (card_w + 13)
            y = cy - card_h / 2 - 5
            if index == len(s['table']) - 1:
                y -= (1 - self.progress) * 48
                p.setOpacity(.35 + self.progress * .65)
            self.draw_card(p, play['card'], x, y, card_w, card_h)
            self.text(p, QRectF(x - 8, y + card_h + 8, card_w + 16, 20), s['players'][play['seat']]['name'][:12], 10, '#ffffff')
            p.setOpacity(1)
        dots_y = min(cy + card_h / 2 + 44, h - 105)
        for i in range(3):
            result = s['results'][i] if i < len(s['results']) else 'pending'
            color = '#86cce6' if result == 0 else '#eea28a' if result == 1 else '#cad5b7' if result is None else '#1b4834'
            p.setBrush(QColor(color))
            p.setPen(QPen(QColor('#adc69a'), 1))
            x = cx - 42 + i * 30
            p.drawRoundedRect(QRectF(x, dots_y, 24, 22), 3, 3)
            self.text(p, QRectF(x, dots_y, 24, 22), '=' if result is None else str(i + 1) if result == 'pending' else '✓' if result == s['seat'] % 2 else '×', 12, '#dce8ca' if result == 'pending' else '#152d22', True)
        if s['vira']:
            vira_w = 40.5 if compact else 54
            vira_h = vira_w * 34 / 27
            x, y = 28, h - vira_h - 33
            self.text(p, QRectF(x - 6, y - 23, vira_w + 12, 20), 'VIRA', 10, '#f9eac4', True)
            self.draw_card(p, s['vira'], x, y, vira_w, vira_h)
            from server import RANKS
            manilha = RANKS[(RANKS.index(s['vira']['rank']) + 1) % 10]
            self.text(p, QRectF(x - 8, y + vira_h + 8, 120, 20), f'MANILHA: {manilha}', 11, '#fff5ca', True)
        self.text(p, QRectF(w - 175, h - 45, 150, 26), f'VALE {s["stake"]} ' + ('PONTO' if s['stake'] == 1 else 'PONTOS'), 12, '#ffedbd', True)
        overlay_title = overlay_sub = None
        if self.paused:
            overlay_title, overlay_sub = 'PAUSADO', 'Pressione P ou clique em Continuar'
        elif s['pending']:
            value = s['pending']['value']
            overlay_title = 'TRUCO!' if value == 3 else f'VALE {value}!'
            overlay_sub = 'O desafio está na mesa. Aceita ou corre?'
        elif s['phase'] == 'eleven':
            overlay_title, overlay_sub = 'MÃO DE ONZE', 'Jogar por 3 ou correr?'
        elif s['phase'] == 'finished':
            overlay_title = 'VITÓRIA!' if s['winner'] == s['seat'] % 2 else 'FIM DE PARTIDA'
            overlay_sub = f'Azul {s["score"][0]} × {s["score"][1]} Coral'
        if overlay_title:
            p.setBrush(QColor('#112f24'))
            p.setPen(QPen(QColor('#f0ce77'), 2))
            bw = min(370, w - 245)
            p.drawRoundedRect(QRectF(cx - bw / 2, cy - 52, bw, 104), 9, 9)
            self.text(p, QRectF(cx - bw / 2, cy - 43, bw, 52), overlay_title, 28, '#ffdf8a', True)
            self.text(p, QRectF(cx - bw / 2 + 8, cy + 14, bw - 16, 30), overlay_sub, 11, '#ffffff')
        elapsed = time.monotonic() - self.victory_started
        if self.animations and s['phase'] == 'finished' and 0 < elapsed < 3.5:
            for index, (px, py, color) in enumerate(self.particles):
                x = px * w + math.sin(elapsed * 2 + index) * 20
                y = ((py - .4 + elapsed * .34) * h) % h
                p.fillRect(QRectF(x, y, 6, 11), QColor(color))
        p.end()
