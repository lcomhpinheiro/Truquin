"""Partidas offline: sem sockets, servidor HTTP ou acesso à internet."""
import json
import os
import time
from pathlib import Path

from server import Room, GameError, RANKS, SUITS, player


class OfflineSession:
    def __init__(self, name='Você', capacity=4):
        self.room = Room('Resenha offline', capacity, player(name[:24] or 'Você'))
        self.room.action(0, 'bots', {})
        self.room.action(0, 'start', {})
        self.paused = False
        self.paused_at = None

    def view(self):
        self.room.players[0]['seen'] = time.time()
        return self.room.view(0)

    def action(self, action, **data):
        if self.paused:
            raise GameError('Continue a partida para jogar.')
        if action == 'play' and self.room.iron:
            index = str(data.get('card', '')).removeprefix('blind-')
            if not index.isdigit() or int(index) >= len(self.room.hands[0]):
                raise GameError('Carta inválida.')
            data['card'] = self.room.hands[0][int(index)]['id']
        self.room.action(0, action, data)
        return self.view()

    def tick(self, now=None):
        if not self.paused:
            self.room.tick(time.time() if now is None else now)
        return self.view()

    def set_paused(self, paused):
        if paused and not self.paused:
            self.paused_at = time.time()
            self.paused = True
        elif not paused and self.paused:
            duration = time.time() - self.paused_at
            self.room.deadline += duration
            self.room.bot_at += duration
            self.paused = False
            self.paused_at = None

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = dict(self.room.__dict__)
        snapshot['deadline'] = max(0, self.room.deadline - (self.paused_at or time.time()))
        snapshot['bot_at'] = max(0, self.room.bot_at - (self.paused_at or time.time()))
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'version': 1, 'room': snapshot}, ensure_ascii=False), encoding='utf-8')
        os.chmod(temporary, 0o600)
        temporary.replace(path)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 100_000:
            raise ValueError('Arquivo de partida inválido.')
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        if snapshot.get('version') != 1:
            raise ValueError('Versão de partida incompatível.')
        data = snapshot['room']
        n = data['capacity']
        if n not in (2, 4) or len(data['players']) != n or len(data['hands']) != n:
            raise ValueError('Jogadores inválidos.')
        if data['players'][0]['bot'] or not all(p['bot'] for p in data['players'][1:]):
            raise ValueError('Esta não é uma partida offline.')
        if not all(isinstance(p['name'], str) and isinstance(p['token'], str) for p in data['players']):
            raise ValueError('Jogadores inválidos.')
        if data['phase'] not in ('playing', 'trick_end', 'hand_end', 'eleven', 'finished'):
            raise ValueError('Estado de partida inválido.')
        if not isinstance(data['turn'], int) or not 0 <= data['turn'] < n:
            raise ValueError('Turno inválido.')
        if len(data['score']) != 2 or any(type(s) is not int or not 0 <= s <= 23 for s in data['score']):
            raise ValueError('Placar inválido.')
        if data['stake'] not in (1, 3, 6, 9, 12):
            raise ValueError('Valor da mão inválido.')
        if len(data['results']) > 3 or any(v not in (None, 0, 1) for v in data['results']):
            raise ValueError('Vazas inválidas.')
        cards = [c for h in data['hands'] for c in h] + [data['vira']]
        if any(len(h) > 3 for h in data['hands']) or len(data['table']) > n:
            raise ValueError('Cartas inválidas.')
        if any(type(p['seat']) is not int or not 0 <= p['seat'] < n for p in data['table']):
            raise ValueError('Mesa inválida.')
        cards += [p['card'] for p in data['table']]
        for c in cards:
            if c['rank'] not in RANKS or c['suit'] not in SUITS or c['id'] != f"{c['rank']}-{c['suit']}":
                raise ValueError('Carta inválida.')
        if len({c['id'] for c in cards}) != len(cards):
            raise ValueError('Cartas duplicadas.')
        if data['eleven'] not in (None, 0, 1) or data['raise_team'] not in (None, 0, 1):
            raise ValueError('Equipe inválida.')
        if data['pending'] is not None and (data['pending']['team'] not in (0, 1) or data['pending']['value'] not in (3, 6, 9, 12)):
            raise ValueError('Pedido inválido.')
        if not isinstance(data['log'], list) or not all(isinstance(line, str) for line in data['log']):
            raise ValueError('Histórico inválido.')
        room = Room(data['name'], n, data['players'][0])
        for key in room.__dict__:
            if key in data:
                setattr(room, key, data[key])
        room.deadline = time.time() + min(4, max(0, float(data['deadline'])))
        room.bot_at = time.time() + min(2, max(0, float(data['bot_at'])))
        session = cls.__new__(cls)
        session.room = room
        session.paused = False
        session.paused_at = None
        session.view()
        return session
