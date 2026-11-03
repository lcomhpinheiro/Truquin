"""Cliente assíncrono Qt e hospedagem LAN opcional."""
import json
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkInterface, QHostAddress
import server


class LocalHost:
    def __init__(self):
        try:
            self.httpd = ThreadingHTTPServer(('0.0.0.0', 8766), server.Handler)
        except OSError:
            self.httpd = ThreadingHTTPServer(('0.0.0.0', 0), server.Handler)
        self.port = self.httpd.server_port
        self.stop = threading.Event()
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self.tick, daemon=True).start()

    def tick(self):
        while not self.stop.wait(.2):
            with server.LOCK:
                for room in list(server.ROOMS.values()):
                    room.tick(time.time())

    def addresses(self):
        addresses = [a.toString() for a in QNetworkInterface.allAddresses()
                     if a.protocol() == QHostAddress.NetworkLayerProtocol.IPv4Protocol and not a.isLoopback()]
        return [f'http://{a}:{self.port}' for a in addresses] or [f'http://localhost:{self.port}']

    def close(self):
        self.stop.set()
        self.httpd.shutdown()
        self.httpd.server_close()
        with server.LOCK:
            server.ROOMS.clear()


def normalize_address(address):
    address = address.strip()
    if '://' not in address:
        address = 'http://' + address
    parsed = urlsplit(address)
    if parsed.scheme != 'http' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Use o endereço local do anfitrião, por exemplo 192.168.1.10:8766.')
    port = parsed.port or 8766
    if not 1 <= port <= 65535:
        raise ValueError('Porta inválida.')
    host = f'[{parsed.hostname}]' if ':' in parsed.hostname else parsed.hostname
    return f'http://{host}:{port}'


class LanClient(QObject):
    changed = Signal(dict)
    failed = Signal(str)
    joined = Signal()

    def __init__(self, base, parent=None):
        super().__init__(parent)
        self.base = normalize_address(base)
        self.session = None
        self.manager = QNetworkAccessManager(self)
        self.timer = QTimer(self)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.poll)
        self.polling = False
        self.active = True
        self.last_error = ''
        self.replies = set()

    def request(self, path, data, callback):
        if not self.active:
            return
        request = QNetworkRequest(QUrl(self.base + '/api/' + path))
        request.setTransferTimeout(4000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        if data is None:
            reply = self.manager.get(request)
        else:
            request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json')
            reply = self.manager.post(request, json.dumps(data).encode())
        self.replies.add(reply)

        def finished():
            self.replies.discard(reply)
            self.polling = False
            if self.active:
                try:
                    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                    payload = json.loads(bytes(reply.readAll()).decode())
                    if status != 200:
                        raise ValueError(payload.get('error', 'Falha ao conectar à mesa.'))
                    self.last_error = ''
                    callback(payload)
                except (ValueError, TypeError):
                    message = 'error' in locals().get('payload', {}) and payload['error'] or 'Sem conexão com a mesa. Confira o endereço e a rede local.'
                    if message != self.last_error:
                        self.failed.emit(message)
                        self.last_error = message
            reply.deleteLater()
        reply.finished.connect(finished)

    def connect_room(self, name, code=None, capacity=4):
        def connected(data):
            self.session = data
            self.joined.emit()
            self.timer.start()
            self.poll()
        payload = {'name': name, 'room': code} if code else {'name': name, 'capacity': capacity, 'room_name': 'Resenha na rede'}
        self.request('join' if code else 'create', payload, connected)

    def poll(self):
        if not self.session or self.polling or not self.active:
            return
        self.polling = True
        from urllib.parse import urlencode
        self.request('state?' + urlencode(self.session), None, self.changed.emit)

    def action(self, action, **data):
        if self.session:
            self.request('action', {**self.session, 'action': action, **data}, self.changed.emit)

    def leave(self):
        self.timer.stop()
        if self.session:
            self.request('action', {**self.session, 'action': 'leave'}, lambda _: self.close())
        else:
            self.close()

    def close(self):
        self.active = False
        self.timer.stop()
        for reply in list(self.replies):
            reply.abort()
