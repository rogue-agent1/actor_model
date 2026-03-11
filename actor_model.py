#!/usr/bin/env python3
"""actor_model — Actor model message passing system. Zero deps."""
from threading import Thread, Lock
from collections import deque
import time

class Message:
    def __init__(self, sender, content):
        self.sender, self.content = sender, content

class Actor:
    def __init__(self, name, system):
        self.name = name
        self.system = system
        self.mailbox = deque()
        self.lock = Lock()
        self.running = True

    def send(self, target_name, content):
        self.system.send(target_name, Message(self.name, content))

    def receive(self, message):
        raise NotImplementedError

    def _process(self):
        while self.running:
            msg = None
            with self.lock:
                if self.mailbox:
                    msg = self.mailbox.popleft()
            if msg:
                self.receive(msg)
            else:
                time.sleep(0.001)

class ActorSystem:
    def __init__(self):
        self.actors = {}
        self.threads = []

    def register(self, actor):
        self.actors[actor.name] = actor
        t = Thread(target=actor._process, daemon=True)
        self.threads.append(t)
        t.start()

    def send(self, target, message):
        if target in self.actors:
            with self.actors[target].lock:
                self.actors[target].mailbox.append(message)

    def stop(self):
        for a in self.actors.values():
            a.running = False

# Demo actors
class PingActor(Actor):
    def __init__(self, system, count):
        super().__init__("ping", system)
        self.count = count
        self.log = []
    def receive(self, msg):
        self.log.append(f"ping got: {msg.content}")
        if self.count > 0:
            self.count -= 1
            self.send("pong", f"ping! ({self.count} left)")

class PongActor(Actor):
    def __init__(self, system):
        super().__init__("pong", system)
        self.log = []
    def receive(self, msg):
        self.log.append(f"pong got: {msg.content}")
        self.send("ping", "pong!")

class CounterActor(Actor):
    def __init__(self, system):
        super().__init__("counter", system)
        self.value = 0
    def receive(self, msg):
        if msg.content == "inc": self.value += 1
        elif msg.content == "dec": self.value -= 1
        elif msg.content == "get":
            self.send(msg.sender, f"count={self.value}")

def main():
    sys = ActorSystem()
    ping = PingActor(sys, 3)
    pong = PongActor(sys)
    sys.register(ping)
    sys.register(pong)
    sys.send("ping", Message("main", "start!"))
    time.sleep(0.1)
    sys.stop()
    print("Actor Model:\n")
    for entry in ping.log: print(f"  {entry}")
    for entry in pong.log: print(f"  {entry}")

if __name__ == "__main__":
    main()
