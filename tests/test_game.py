import itertools
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server


def room(n=4):
    r = server.Room('Teste', n, server.player('Ana'))
    r.players += [server.player(f'Pessoa {i}') for i in range(1, n)]
    r.deal()
    return r


class RulesTests(unittest.TestCase):
    def test_all_rank_and_suit_orders_and_wraparound(self):
        for i, rank in enumerate(server.RANKS):
            vira = server.card(rank, 'Clubs')
            manilha = server.RANKS[(i + 1) % 10]
            powers = [server.strength(server.card(manilha, s), vira) for s in server.SUITS]
            self.assertEqual(powers, [20, 21, 22, 23])
            for ordinary in server.RANKS:
                if ordinary != manilha:
                    self.assertLess(server.strength(server.card(ordinary, 'Clubs'), vira), min(powers))

    def test_all_legal_trick_outcomes(self):
        for a, b in itertools.product([None, 0, 1], repeat=2):
            expected = b if a is None else a if b is None or a == b else None
            self.assertEqual(server.hand_winner([a, b]), expected)
            if expected is None:
                for c in [None, 0, 1]:
                    final = c if c is not None else a if a is not None else -1
                    self.assertEqual(server.hand_winner([a, b, c]), final)

    def test_deal_has_no_duplicates(self):
        r = room()
        cards = [c['id'] for h in r.hands for c in h] + [r.vira['id']]
        self.assertEqual(len(set(cards)), 13)

    def test_turn_and_card_validation(self):
        r = room()
        with self.assertRaises(server.GameError):
            r.play(1, r.hands[1][0]['id'])
        with self.assertRaises(server.GameError):
            r.play(0, r.hands[1][0]['id'])
        with self.assertRaises(server.GameError):
            r.play(0, r.hands[0][0]['id'], True)
        r.play(0, r.hands[0][0]['id'])
        self.assertEqual(r.turn, 1)
        self.assertEqual(len(r.hands[0]), 2)

    def test_raises_counterraises_and_refusal(self):
        r = room()
        r.action(0, 'raise', {})
        with self.assertRaises(server.GameError):
            r.respond(2, 'accept')
        with self.assertRaises(server.GameError):
            r.play(0, r.hands[0][0]['id'])
        r.respond(1, 'raise')
        self.assertEqual(r.stake, 3)
        self.assertEqual(r.pending, {'team': 1, 'value': 6, 'seat': 1})
        r.respond(0, 'raise')
        self.assertEqual(r.stake, 6)
        r.respond(1, 'raise')
        self.assertEqual(r.stake, 9)
        r.respond(0, 'run')
        self.assertEqual(r.score, [0, 9])

    def test_accepted_raise_right_alternates(self):
        r = room(2)
        r.action(0, 'raise', {})
        r.respond(1, 'accept')
        self.assertFalse(r.can_raise(0))
        r.play(0, r.hands[0][0]['id'])
        self.assertTrue(r.can_raise(1))
        r.action(1, 'raise', {})
        r.respond(0, 'run')
        self.assertEqual(r.score, [0, 3])

    def test_eleven_accept_refuse_and_partner_visibility(self):
        r = room()
        r.score = [11, 7]
        r.deal()
        self.assertEqual(r.phase, 'eleven')
        self.assertEqual(r.view(0)['partner'], r.hands[2])
        self.assertEqual(r.view(1)['partner'], [])
        with self.assertRaises(server.GameError):
            r.respond(1, 'accept')
        r.respond(2, 'accept')
        self.assertEqual(r.stake, 3)
        self.assertFalse(r.can_raise(r.turn))
        r.deal()
        r.respond(0, 'run')
        self.assertEqual(r.score, [11, 8])

    def test_iron_hides_identities(self):
        r = room()
        r.score = [11, 11]
        r.deal()
        for i in range(4):
            state = r.view(i)
            self.assertTrue(state['iron'])
            self.assertEqual(state['partner'], [])
            self.assertEqual(state['hand'], [{'id':f'blind-{n}', 'blind':True} for n in range(3)])
            self.assertFalse(r.can_raise(i))

    def test_covered_cards_are_private(self):
        r = room(2)
        r.results = [None]
        r.play(0, r.hands[0][0]['id'], True)
        self.assertEqual(r.view(1)['table'][0]['card'], {'covered': True})
        self.assertEqual(server.strength({'covered': True}, r.vira), -1)

    def test_same_team_top_cards_win_trick(self):
        r = room()
        r.vira = server.card('4','Clubs')
        r.hands = [[server.card(rank, suit)] for rank,suit in [('3','Hearts'),('4','Clubs'),('3','Spades'),('4','Hearts')]]
        for i in range(4):
            r.play(i, r.hands[i][0]['id'])
        self.assertEqual(r.results, [0])
        self.assertEqual(r.turn, 0)

    def test_leaving_transfers_host_and_bots_take_over(self):
        r = room()
        old_host = r.host
        self.assertTrue(r.leave(0))
        self.assertTrue(r.players[0]['bot'])
        self.assertNotEqual(r.host, old_host)
        with self.assertRaises(server.GameError):
            r.index(old_host)
        r.phase = 'lobby'
        old_length = len(r.players)
        r.leave(1)
        self.assertEqual(len(r.players), old_length - 1)

    def test_complete_random_matches_and_room_isolation(self):
        for n in (2, 4):
            r = room(n)
            other = room(n)
            turns = 0
            while r.phase != 'finished' and turns < 1500:
                turns += 1
                if r.phase == 'eleven':
                    r.respond(r.eleven, 'accept')
                elif r.phase in ('trick_end', 'hand_end'):
                    r.tick(time.time() + 100)
                elif r.phase == 'playing':
                    r.play(r.turn, r.hands[r.turn][0]['id'])
            self.assertEqual(r.phase, 'finished')
            self.assertGreaterEqual(max(r.score), 12)
            self.assertEqual(other.score, [0, 0])
            self.assertEqual(other.hand_no, 1)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
        cls.url = f'http://127.0.0.1:{cls.httpd.server_port}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self,path,data=None):
        req = urllib.request.Request(self.url+path, data=json.dumps(data).encode() if data else None,
                                     headers={'Content-Type':'application/json'} if data else {})
        with urllib.request.urlopen(req) as res:
            return json.load(res)

    def test_four_clients_join_start_play_and_private_state(self):
        a=self.request('/api/create',{'name':'Um','capacity':4,'room_name':'Quatro'})
        clients=[a]+[self.request('/api/join',{'name':f'P{i}','room':a['room']}) for i in range(3)]
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/join',{'name':'Quinto','room':a['room']})
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/action',{**clients[1],'action':'start'})
        self.request('/api/action',{**a,'action':'start'})
        states=[self.request(f'/api/state?room={c["room"]}&token={c["token"]}') for c in clients]
        for i,s in enumerate(states):
            self.assertEqual(s['seat'],i)
            self.assertNotIn('token',json.dumps(s))
            self.assertEqual(len(s['hand']),3)
            other_ids={card['id'] for j,t in enumerate(states) if j!=i for card in t['hand']}
            self.assertFalse(any(cid in json.dumps(s) for cid in other_ids))
        for i in range(4):
            self.request('/api/action',{**clients[i],'action':'play','card':states[i]['hand'][0]['id']})
        last=self.request(f'/api/state?room={a["room"]}&token={a["token"]}')
        self.assertEqual(last['phase'],'trick_end')
        self.assertEqual(len(last['table']),4)
        # Reloading with the same token retains the seat.
        self.assertEqual(last['seat'],0)
        with self.assertRaises(urllib.error.HTTPError):
            self.request(f'/api/state?room={a["room"]}&token=wrong')

    def test_iron_opaque_identifiers_play_through_api(self):
        a=self.request('/api/create',{'name':'Ferro','capacity':2})
        b=self.request('/api/join',{'name':'Outro','room':a['room']})
        with server.LOCK:
            r=server.ROOMS[a['room']]
            r.score=[11,11]
            r.deal()
        view=self.request('/api/action',{**a,'action':'play','card':'blind-0'})
        self.assertEqual(len(view['hand']),2)
        self.assertEqual(view['turn'],1)
        self.assertIn('rank',view['table'][0]['card'])
        self.assertNotIn('rank',view['hand'][0])

    def test_static_and_invalid_requests(self):
        for path in ['/','/app.js','/style.css','/assets/Clubs/Clubs_card_07.png']:
            with urllib.request.urlopen(self.url+path) as res:
                self.assertEqual(res.status,200)
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.url+'/../server.py')
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/create',{'name':'Oi','capacity':3})


if __name__ == '__main__':
    unittest.main()
