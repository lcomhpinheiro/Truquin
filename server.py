#!/usr/bin/env python3
"""Truco da Mesa — servidor autoritativo, sem dependências externas."""
import argparse
import json
import mimetypes
import random
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent / 'static'
RANKS = ['4', '5', '6', '7', 'Q', 'J', 'K', 'A', '2', '3']
SUITS = ['Diamonds', 'Spades', 'Hearts', 'Clubs']
STAKES = [1, 3, 6, 9, 12]
ROOMS = {}
LOCK = threading.RLock()
RNG = random.SystemRandom()


def card(rank, suit):
    return {'rank': rank, 'suit': suit, 'id': f'{rank}-{suit}'}


def strength(c, vira):
    if c.get('covered'):
        return -1
    if c['rank'] == RANKS[(RANKS.index(vira['rank']) + 1) % 10]:
        return 20 + SUITS.index(c['suit'])
    return RANKS.index(c['rank'])


def hand_winner(results):
    """None = seguir; -1 = mão empatada; 0/1 = dupla vencedora."""
    if len(results) < 2:
        return None
    a, b = results[:2]
    if a == b and a is not None:
        return a
    if a is None and b is not None:
        return b
    if b is None and a is not None:
        return a
    if len(results) < 3:
        return None
    if results[2] is not None:
        return results[2]
    return a if a is not None else -1


class GameError(Exception):
    pass


class Room:
    def __init__(self, name, capacity, owner):
        self.code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(5))
        self.name = name
        self.capacity = capacity
        self.players = [owner]
        self.host = owner['token']
        self.phase = 'lobby'
        self.score = [0, 0]
        self.hands = []
        self.vira = None
        self.table = []
        self.last_table = []
        self.results = []
        self.log = []
        self.hand_no = 0
        self.dealer = capacity - 1
        self.turn = 0
        self.stake = 1
        self.raise_team = None
        self.pending = None
        self.eleven = None
        self.iron = False
        self.winner = None
        self.deadline = 0
        self.updated = time.time()
        self.bot_at = time.time() + 1
        self.cut_enabled = False
        self.prepared_deck = []
        self.cutter = 0
        self.cut_position = None
        self.trick_winner = None

    def say(self, message):
        self.log.append(message)
        self.log = self.log[-35:]
        self.updated = time.time()

    def index(self, token):
        for i, p in enumerate(self.players):
            if secrets.compare_digest(p['token'], token):
                return i
        raise GameError('Sua sessão não pertence a esta mesa.')

    def team_name(self, team):
        return 'Azul' if team == 0 else 'Coral'

    def cut(self, seat, position):
        if self.phase != 'cut' or seat != self.cutter:
            raise GameError('Aguarde sua vez de cortar.')
        if type(position) is not int or not 1 <= position <= 39:
            raise GameError('O corte deve ficar entre 1 e 39 cartas.')
        self.prepared_deck = self.prepared_deck[position:] + self.prepared_deck[:position]
        self.cut_position = position
        self.phase = 'cutting'
        self.deadline = time.time() + 1.2
        self.say(f'{self.players[seat]["name"]} cortou o baralho em {position} cartas.')

    def deal(self, prepared=None):
        self.trick_winner = None
        if self.cut_enabled and prepared is None:
            self.prepared_deck = [card(r, s) for r in RANKS for s in SUITS]
            RNG.shuffle(self.prepared_deck)
            self.phase = 'shuffling'
            self.deadline = time.time() + 2
            self.cutter = (self.dealer + 1) % self.capacity
            self.cut_position = None
            self.hands = [[] for _ in self.players]
            self.table = []
            self.results = []
            self.vira = None
            self.pending = None
            self.eleven = None
            self.iron = False
            self.stake = 1
            return
        deck = [card(r, s) for r in RANKS for s in SUITS]
        if prepared is None:
            RNG.shuffle(deck)
        else:
            deck = list(prepared)
            self.prepared_deck = []
        self.hands = [[deck.pop() for _ in range(3)] for _ in self.players]
        self.vira = deck.pop()
        self.table = []
        self.last_table = []
        self.results = []
        self.stake = 1
        self.pending = None
        self.raise_team = None
        self.eleven = None
        self.iron = self.score == [11, 11]
        self.turn = (self.dealer + 1) % self.capacity
        self.hand_no += 1
        self.phase = 'playing'
        self.say(f'Mão {self.hand_no}. {self.players[self.turn]["name"]} começa.')
        if 11 in self.score and not self.iron:
            self.eleven = self.score.index(11)
            self.phase = 'eleven'
            self.say(f'Mão de onze: equipe {self.team_name(self.eleven)} decide se joga.')
        if self.iron:
            self.say('Mão de ferro! Cartas às cegas, sem aumentos.')
        self.bot_at = time.time() + 1.2

    def award(self, team, points, reason):
        if team is not None:
            self.score[team] += points
            self.say(f'{reason} Equipe {self.team_name(team)} +{points}.')
        else:
            self.say(reason)
        self.pending = None
        if max(self.score) >= 12:
            self.winner = self.score.index(max(self.score))
            self.phase = 'finished'
            self.say(f'Equipe {self.team_name(self.winner)} venceu a partida!')
        else:
            self.phase = 'hand_end'
            self.deadline = time.time() + 4

    def can_raise(self, seat):
        return (self.phase == 'playing' and seat == self.turn and not self.pending
                and self.eleven is None and not self.iron and self.stake < 12
                and self.raise_team in (None, seat % 2))

    def respond(self, seat, answer):
        if self.phase == 'eleven':
            if seat % 2 != self.eleven:
                raise GameError('A decisão é da equipe com onze pontos.')
            if answer == 'accept':
                self.stake = 3
                self.phase = 'playing'
                self.say('Mão de onze aceita. Valendo 3 pontos!')
            elif answer == 'run':
                self.award(1 - self.eleven, 1, 'A equipe com onze correu.')
            else:
                raise GameError('Não se pode aumentar a mão de onze.')
            return
        p = self.pending
        if self.phase != 'playing' or not p or seat % 2 == p['team']:
            raise GameError('Não há pedido para sua equipe responder.')
        if answer == 'run':
            self.award(p['team'], self.stake, 'Pedido recusado.')
        elif answer == 'accept':
            self.stake = p['value']
            self.raise_team = seat % 2
            self.pending = None
            self.say(f'{self.players[seat]["name"]} aceitou. Vale {self.stake}!')
        elif answer == 'raise' and p['value'] < 12:
            self.stake = p['value']
            value = STAKES[STAKES.index(self.stake) + 1]
            self.pending = {'team': seat % 2, 'value': value, 'seat': seat}
            self.say(f'{self.players[seat]["name"]} aumentou para {value}!')
        else:
            raise GameError('Resposta inválida.')
        self.bot_at = time.time() + 1.2

    def play(self, seat, card_id, covered=False):
        if self.phase != 'playing' or self.pending or self.turn != seat:
            raise GameError('Aguarde sua vez ou a resposta ao pedido.')
        c = next((c for c in self.hands[seat] if c['id'] == card_id), None)
        if c is None:
            raise GameError('Essa carta não está na sua mão.')
        if covered and not self.results:
            raise GameError('Não é permitido cobrir na primeira vaza.')
        self.hands[seat].remove(c)
        self.trick_winner = None
        self.table.append({'seat': seat, 'card': dict(c, covered=bool(covered))})
        self.turn = (seat + 1) % self.capacity
        if len(self.table) == self.capacity:
            values = [strength(p['card'], self.vira) for p in self.table]
            best = max(values)
            winners = [p['seat'] for p, v in zip(self.table, values) if v == best]
            teams = {s % 2 for s in winners}
            result = next(iter(teams)) if len(teams) == 1 else None
            self.results.append(result)
            # Em empate, abre quem primeiro jogou uma das cartas empatadas.
            self.turn = winners[0]
            self.trick_winner = None if result is None else winners[0]
            self.say(f'Vaza {len(self.results)}: ' + ('empatou.' if result is None else f'equipe {self.team_name(result)} levou.'))
            winner = hand_winner(self.results)
            if winner is not None:
                self.award(None if winner == -1 else winner, self.stake,
                           'Três empates: ninguém pontua.' if winner == -1 else 'Fim da mão.')
            else:
                self.phase = 'trick_end'
                self.deadline = time.time() + 2.3
        self.bot_at = time.time() + 1.1

    def leave(self, seat):
        departing = self.players[seat]
        if self.phase == 'lobby':
            self.players.pop(seat)
        else:
            self.players[seat] = player(departing['name'] + ' (bot)', bot=True)
        humans = [p for p in self.players if not p['bot']]
        if humans and departing['token'] == self.host:
            self.host = humans[0]['token']
        self.say(f'{departing["name"]} saiu da mesa.' + (' Um bot assumiu o lugar.' if self.phase != 'lobby' else ''))
        return bool(humans)

    def action(self, seat, action, data):
        if action in ('start', 'bots', 'rematch') and self.players[seat]['token'] != self.host:
            raise GameError('Somente quem criou a mesa pode fazer isso.')
        if action == 'bots' and self.phase == 'lobby':
            while len(self.players) < self.capacity:
                n = len(self.players)
                self.players.append(player(['Bento', 'Lola', 'Tião', 'Nina'][n], bot=True))
            self.say('Bots chegaram à mesa.')
        elif action == 'start' and self.phase == 'lobby':
            if len(self.players) != self.capacity:
                raise GameError('Espere os jogadores ou complete com bots.')
            self.deal()
        elif action == 'rematch' and self.phase == 'finished':
            self.score = [0, 0]
            self.winner = None
            self.hand_no = 0
            self.dealer = (self.dealer + 1) % self.capacity
            self.deal()
        elif action == 'cut':
            self.cut(seat, data.get('position'))
        elif action == 'play':
            self.play(seat, data.get('card'), data.get('covered', False))
        elif action == 'raise':
            if not self.can_raise(seat):
                raise GameError('Você não pode aumentar agora.')
            value = STAKES[STAKES.index(self.stake) + 1]
            self.pending = {'team': seat % 2, 'value': value, 'seat': seat}
            self.say(f'{self.players[seat]["name"]} pediu {"TRUCO" if value == 3 else value}!')
        elif action == 'respond':
            self.respond(seat, data.get('answer'))
        else:
            raise GameError('Ação indisponível neste momento.')
        self.updated = time.time()

    def tick(self, now):
        if self.phase == 'shuffling' and now >= self.deadline:
            self.phase = 'cut'
            self.deadline = now + 10
        elif self.phase == 'cut' and (now >= self.deadline or self.players[self.cutter]['bot']):
            self.cut(self.cutter, RNG.randint(8, 32))
        elif self.phase == 'cutting' and now >= self.deadline:
            self.deal(self.prepared_deck)
        if self.phase == 'trick_end' and now >= self.deadline:
            self.last_table = self.table
            self.table = []
            self.phase = 'playing'
            self.bot_at = now + 0.8
        elif self.phase == 'hand_end' and now >= self.deadline:
            self.dealer = (self.dealer + 1) % self.capacity
            self.deal()
        if now < self.bot_at:
            return
        self.bot_at = now + 1.3
        if self.phase == 'eleven':
            seat = next((i for i, p in enumerate(self.players) if i % 2 == self.eleven and p['bot']), None)
            if any(not p['bot'] and i % 2 == self.eleven for i, p in enumerate(self.players)):
                seat = None
            if seat is not None:
                self.respond(seat, 'accept')
        elif self.phase == 'playing' and self.pending:
            seat = next((i for i, p in enumerate(self.players) if i % 2 != self.pending['team'] and p['bot']), None)
            if any(not p['bot'] and i % 2 != self.pending['team'] for i, p in enumerate(self.players)):
                seat = None
            if seat is not None:
                power = max(strength(c, self.vira) for c in self.hands[seat]) if self.hands[seat] else 0
                self.respond(seat, 'accept' if power >= 7 or RNG.random() < 0.6 else 'run')
        elif self.phase == 'playing' and self.players[self.turn]['bot']:
            if self.can_raise(self.turn) and any(strength(c, self.vira) >= 9 for c in self.hands[self.turn]) and RNG.random() < 0.18:
                self.action(self.turn, 'raise', {})
                return
            hand = self.hands[self.turn]
            c = RNG.choice(hand) if self.iron else min(hand, key=lambda c: strength(c, self.vira))
            # Procura a menor carta capaz de bater a mesa.
            if self.table and not self.iron:
                top = max(strength(p['card'], self.vira) for p in self.table)
                winning = [c for c in hand if strength(c, self.vira) > top]
                if winning:
                    c = min(winning, key=lambda c: strength(c, self.vira))
            self.play(self.turn, c['id'])

    def view(self, seat):
        # O cliente recebe apenas a própria mão e, na mão de onze, a do parceiro.
        own = [None if self.iron else c for c in self.hands[seat]] if self.hands else []
        hand = [{'id': f'blind-{i}', 'blind': True} if c is None else c for i, c in enumerate(own)]
        partner = []
        if self.eleven == seat % 2 and self.capacity == 4 and self.hands:
            partner = self.hands[(seat + 2) % 4]
        public_table = []
        for p in self.table:
            public_table.append({'seat': p['seat'], 'card': {'covered': True} if p['card'].get('covered') else p['card']})
        return {'code': self.code, 'name': self.name, 'capacity': self.capacity,
                'seat': seat, 'host': self.players[seat]['token'] == self.host,
                'players': [{'name': p['name'], 'bot': p['bot'], 'online': p['bot'] or time.time() - p['seen'] < 12,
                             'count': len(self.hands[i]) if self.hands else 0} for i, p in enumerate(self.players)],
                'phase': self.phase, 'score': self.score, 'hand': hand, 'partner': partner,
                'vira': self.vira, 'table': public_table, 'results': self.results,
                'turn': self.turn, 'stake': self.stake, 'pending': self.pending,
                'eleven': self.eleven, 'iron': self.iron, 'winner': self.winner,
                'can_raise': self.can_raise(seat), 'log': self.log[-12:], 'hand_no': self.hand_no,
                'cut_enabled': self.cut_enabled, 'cutter': self.cutter, 'cut_position': self.cut_position,
                'trick_winner': self.trick_winner,
                'next_in': max(0, round(self.deadline - time.time())) if self.phase in ('trick_end', 'hand_end', 'shuffling', 'cut', 'cutting') else 0}


def player(name, bot=False):
    return {'name': name, 'token': secrets.token_urlsafe(24), 'bot': bot, 'seen': time.time()}


def clean_name(value, default):
    return ''.join(c for c in str(value) if c.isprintable()).strip()[:28] or default


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith('GET /api/'):
            return
        super().log_message(fmt, *args)

    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        try:
            if url.path == '/api/rooms':
                with LOCK:
                    rooms = [{'code': r.code, 'name': r.name, 'capacity': r.capacity, 'players': len(r.players)}
                             for r in ROOMS.values() if r.phase == 'lobby' and len(r.players) < r.capacity]
                return self.reply({'rooms': rooms})
            if url.path == '/api/state':
                q = parse_qs(url.query)
                with LOCK:
                    r = ROOMS.get(q.get('room', [''])[0].upper())
                    if not r:
                        raise GameError('Mesa não encontrada. Crie ou entre em outra mesa.')
                    seat = r.index(q.get('token', [''])[0])
                    r.players[seat]['seen'] = time.time()
                    return self.reply(r.view(seat))
            path = (ROOT / (url.path.lstrip('/') or 'index.html')).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                self.send_error(404)
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)
        except GameError as e:
            self.reply({'error': str(e)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            # Same-origin requests only; cookies are not used.
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                return self.reply({'error': 'Origem não permitida.'}, 403)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                return self.reply({'error': 'Requisição inválida.'}, 400)
            d = json.loads(self.rfile.read(size))
            if not isinstance(d, dict):
                raise ValueError()
            with LOCK:
                if self.path == '/api/create':
                    if len(ROOMS) >= 200:
                        raise GameError('Limite de mesas atingido.')
                    capacity = d.get('capacity', 4)
                    if capacity not in (2, 4):
                        raise GameError('Escolha 2 ou 4 jogadores.')
                    p = player(clean_name(d.get('name', ''), 'Visitante'))
                    r = Room(clean_name(d.get('room_name', ''), 'Mesa de amigos'), capacity, p)
                    while r.code in ROOMS:
                        r.code = secrets.token_hex(3).upper()
                    r.cut_enabled = d.get('cut_enabled') is True
                    ROOMS[r.code] = r
                    r.say(f'{p["name"]} abriu a mesa.')
                    return self.reply({'room': r.code, 'token': p['token']})
                r = ROOMS.get(str(d.get('room', '')).upper())
                if not r:
                    raise GameError('Mesa não encontrada.')
                if self.path == '/api/join':
                    if r.phase != 'lobby' or len(r.players) >= r.capacity:
                        raise GameError('Esta mesa já está cheia ou em partida.')
                    p = player(clean_name(d.get('name', ''), 'Visitante'))
                    r.players.append(p)
                    r.say(f'{p["name"]} entrou na mesa.')
                    return self.reply({'room': r.code, 'token': p['token']})
                if self.path != '/api/action':
                    return self.reply({'error': 'Rota desconhecida.'}, 404)
                seat = r.index(str(d.get('token', '')))
                r.players[seat]['seen'] = time.time()
                if d.get('action') == 'leave':
                    if not r.leave(seat):
                        del ROOMS[r.code]
                    return self.reply({'ok': True})
                # Blind card positions are mapped exclusively on the server.
                if r.iron and d.get('action') == 'play':
                    idx = str(d.get('card', '')).removeprefix('blind-')
                    if not idx.isdigit() or int(idx) >= len(r.hands[seat]):
                        raise GameError('Carta inválida.')
                    d['card'] = r.hands[seat][int(idx)]['id']
                r.action(seat, d.get('action'), d)
                return self.reply(r.view(seat))
        except GameError as e:
            self.reply({'error': str(e)}, 400)
        except (ValueError, TypeError, KeyError):
            self.reply({'error': 'Dados inválidos.'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass


def ticker():
    while True:
        time.sleep(0.2)
        with LOCK:
            for code, r in list(ROOMS.items()):
                if time.time() - max(p['seen'] for p in r.players if not p['bot']) > 86400:
                    del ROOMS[code]
                    continue
                # A mesa aguarda reconexão; não joga pelas pessoas ausentes.
                r.tick(time.time())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    threading.Thread(target=ticker, daemon=True).start()
    print(f'\n  TRUCO DA MESA\n  Neste computador: http://localhost:{args.port}\n', flush=True)
    try:
        addresses = sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
        # UDP connect only selects the local route; no packet is sent.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            addresses = sorted(set(addresses + [sock.getsockname()[0]]))
        for ip in addresses:
            if not ip.startswith('127.'):
                print(f'  Na mesma rede: http://{ip}:{args.port}', flush=True)
    except OSError:
        pass
    print('\n  Ctrl+C para encerrar.\n', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServidor encerrado.')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
