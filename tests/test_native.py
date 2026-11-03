import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from native.session import OfflineSession
from server import GameError


class OfflineTests(unittest.TestCase):
    def test_offline_does_not_open_network_sockets(self):
        with patch('socket.socket', side_effect=AssertionError('Offline abriu um socket')):
            session = OfflineSession('Ana', 4)
            state = session.view()
            session.action('play', card=state['hand'][0]['id'])
            session.tick(time.time() + 10)
            self.assertEqual(len(session.room.hands[0]), 2)
            self.assertTrue(session.view()['players'][0]['online'])

    def test_save_load_preserves_game_and_hides_iron_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'save.json'
            session = OfflineSession('Ana', 4)
            session.room.score = [11, 11]
            session.room.deal()
            session.save(path)
            loaded = OfflineSession.load(path)
            self.assertEqual(loaded.room.hands, session.room.hands)
            self.assertEqual(loaded.room.score, [11, 11])
            self.assertTrue(all(c['blind'] for c in loaded.view()['hand']))
            loaded.action('play', card='blind-0')
            self.assertEqual(len(loaded.room.hands[0]), 2)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_pause_keeps_bots_and_saved_deadlines_still(self):
        session = OfflineSession('Ana', 2)
        session.action('play', card=session.view()['hand'][0]['id'])
        before = list(session.room.table)
        session.set_paused(True)
        session.tick(time.time() + 200)
        self.assertEqual(session.room.table, before)
        with self.assertRaises(GameError):
            session.action('raise')
        session.set_paused(False)
        session.tick(time.time() + 10)
        self.assertEqual(len(session.room.table), 2)

    def test_human_decides_eleven_instead_of_partner_bot(self):
        session = OfflineSession('Ana', 4)
        session.room.score = [11, 5]
        session.room.deal()
        session.tick(time.time() + 100)
        self.assertEqual(session.room.phase, 'eleven')
        self.assertEqual(len(session.view()['partner']), 3)
        session.action('respond', answer='accept')
        self.assertEqual(session.room.stake, 3)

    def test_bot_partner_does_not_answer_for_human(self):
        session = OfflineSession('Ana', 4)
        session.room.turn = 1
        session.room.action(1, 'raise', {})
        session.tick(time.time() + 100)
        self.assertIsNotNone(session.room.pending)
        session.action('respond', answer='accept')
        self.assertIsNone(session.room.pending)

    def test_corrupted_save_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'save.json'
            session = OfflineSession('Ana', 4)
            session.save(path)
            data = json.loads(path.read_text())
            data['room']['capacity'] = 3
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                OfflineSession.load(path)

    def test_complete_offline_match_with_bots_and_save_roundtrip(self):
        session = OfflineSession('Ana', 4)
        steps = 0
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / 'save.json'
            while session.room.phase != 'finished' and steps < 2000:
                steps += 1
                state = session.view()
                if state['phase'] == 'eleven' and state['eleven'] == 0:
                    session.action('respond', answer='accept')
                elif state['pending'] and state['pending']['team'] == 1:
                    session.action('respond', answer='accept')
                elif state['phase'] == 'playing' and not state['pending'] and state['turn'] == 0:
                    session.action('play', card=state['hand'][0]['id'])
                else:
                    session.tick(time.time() + steps * 200)
                if steps % 7 == 0:
                    session.save(save)
                    session = OfflineSession.load(save)
            self.assertEqual(session.room.phase, 'finished')
            self.assertGreaterEqual(max(session.room.score), 12)


try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, 'PySide6 é necessário apenas para a interface nativa')
class NativeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ['TRUCO_NO_AUDIO'] = '1'
        cls.app = QApplication.instance() or QApplication([])
        cls.tmp = tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        from desktop import MainWindow
        self.directory = tempfile.TemporaryDirectory()
        self.window = MainWindow(Path(self.directory.name))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.directory.cleanup()

    def test_native_click_play_pause_fullscreen_and_restore(self):
        QTest.mouseClick(self.window.duplas_button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(self.window.pages.currentWidget(), self.window.game_page)
        self.assertEqual(len(self.window.hand_buttons), 3)
        self.assertTrue(all(not item.icon().isNull() for item in self.window.hand_buttons))
        QTest.keyClick(self.window, Qt.Key.Key_1)
        self.app.processEvents()
        self.assertEqual(len(self.window.offline.room.hands[0]), 2)
        QTest.keyClick(self.window, Qt.Key.Key_P)
        self.assertIsNotNone(self.window.paused_at)
        self.assertTrue(all(not item.isEnabled() for item in self.window.hand_buttons))
        QTest.keyClick(self.window, Qt.Key.Key_P)
        self.assertIsNone(self.window.paused_at)
        QTest.keyClick(self.window, Qt.Key.Key_F11)
        self.assertTrue(self.window.isFullScreen())
        QTest.keyClick(self.window, Qt.Key.Key_F11)
        self.assertFalse(self.window.isFullScreen())
        self.window.go_home()
        self.assertTrue(self.window.save_path.exists())
        self.window.resume_saved()
        self.assertEqual(len(self.window.offline.room.hands[0]), 2)

    def test_high_contrast_large_cards_and_native_snapshot(self):
        self.window.new_offline(2)
        self.window.ui_scale = 1.5
        self.window.high_contrast = True
        self.window.effects_on = False
        self.window.apply_preferences()
        self.app.processEvents()
        self.assertTrue(self.window.board.high_contrast)
        self.assertFalse(self.window.board.animations)
        self.assertGreaterEqual(self.window.hand_buttons[0].iconSize().width(), 162)
        self.assertTrue(self.window.status.isVisible())
        for card in self.window.hand_buttons:
            self.assertTrue(self.window.game_page.rect().contains(card.mapTo(self.window.game_page, card.rect().bottomRight())))
        self.window.grab().save('/tmp/truco-native-large.png')

    def test_native_lan_four_clients_without_external_network(self):
        from native.network import LocalHost, LanClient
        host = LocalHost()
        clients = [LanClient(f'127.0.0.1:{host.port}') for _ in range(4)]
        states = [{} for _ in clients]
        errors = []
        for i, client in enumerate(clients):
            client.changed.connect(lambda state, index=i: states.__setitem__(index, state))
            client.failed.connect(errors.append)
        def wait(condition):
            deadline = time.monotonic() + 6
            while not condition() and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(10)
            self.assertTrue(condition(), errors)
        try:
            clients[0].connect_room('Anfitrião')
            wait(lambda: clients[0].session is not None)
            code = clients[0].session['room']
            for index, client in enumerate(clients[1:], 1):
                client.connect_room('Pessoa ' + str(index), code)
                wait(lambda c=client: c.session is not None)
            clients[0].action('start')
            wait(lambda: all(s.get('phase') == 'playing' for s in states))
            clients[0].action('raise')
            wait(lambda: bool(states[1].get('pending')))
            clients[1].action('respond', answer='accept')
            wait(lambda: states[0].get('stake') == 3)
            for index, client in enumerate(clients):
                wait(lambda i=index: states[i].get('turn') == i and states[i].get('phase') == 'playing')
                client.action('play', card=states[index]['hand'][0]['id'])
            wait(lambda: len(states[0].get('table', [])) == 4)
            self.assertFalse(errors)
        finally:
            for client in clients:
                client.close()
            host.close()


if __name__ == '__main__':
    unittest.main()
