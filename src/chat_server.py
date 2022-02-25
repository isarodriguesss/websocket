"""
Chat Server

Alunos: Isadora Rodrigues e Yago
===========
Essa é uma simples ideia de aplicação usando WebSockets para rodar um chat server primitivo.
"""

import os
import logging
import redis
import gevent
from flask import Flask, render_template
from flask_sockets import Sockets

REDIS_URL = os.environ['REDIS_URL']
REDIS_CHAN = 'chat'

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ

sockets = Sockets(app)
redis = redis.from_url(REDIS_URL)



class ChatBackend(object):
    """Interface para registrar e atualizar clientes WebSocket."""

    def __init__(self):
        self.clients = list()
        self.pubsub = redis.pubsub()
        self.pubsub.subscribe(REDIS_CHAN)

    def __iter_data(self):
        for message in self.pubsub.listen():
            data = message.get('data')
            if message['type'] == 'message':
                app.logger.info(u'Sending message: {}'.format(data))
                yield data

    def register(self, client):
        """Registrar uma conecção WebSocket com as atualização do Redis."""
        self.clients.append(client)

    def send(self, client, data):
        """Enviar dados fornecidos para o cliente cadastrado.
        Descarta automaticamente conexões inválidas."""
        try:
            client.send(data)
        except Exception:
            self.clients.remove(client)

    def run(self):
        """Escuta novas mensagens no Redis e as envia aos clientes."""
        for data in self.__iter_data():
            for client in self.clients:
                gevent.spawn(self.send, client, data)

    def start(self):
        """Mantém a assinatura do Redis em segundo plano."""
        gevent.spawn(self.run)

chats = ChatBackend()
chats.start()


@app.route('/')
def hello():
    return render_template('index.html')

@sockets.route('/submit')
def inbox(ws):
    """Recebe mensagens de bate-papo recebidas e as insere no Redis."""
    while not ws.closed:
        # Dormir para evitar trocas de contexto *constantes*.
        gevent.sleep(0.1)
        message = ws.receive()

        if message:
            app.logger.info(u'Inserting message: {}'.format(message))
            redis.publish(REDIS_CHAN, message)

@sockets.route('/receive')
def outbox(ws):
    """Envia mensagens de bate-papo de saída, via `ChatBackend`."""
    chats.register(ws)

    while not ws.closed:
        # Troca de contexto enquanto o `ChatBackend.start` está sendo executado em segundo plano.
        gevent.sleep(0.1)