#!/usr/bin/env python3
"""actor_model - Erlang-style actor system with mailboxes, supervision, and linking.

Usage: python actor_model.py [--demo]
"""
from collections import deque
import random

class Message:
    def __init__(self, sender, tag, data=None):
        self.sender = sender; self.tag = tag; self.data = data
    def __repr__(self): return f"Msg({self.tag}, {self.data})"

class Actor:
    _counter = 0
    def __init__(self, name, behavior):
        Actor._counter += 1
        self.pid = Actor._counter
        self.name = name
        self.mailbox = deque()
        self.behavior = behavior
        self.alive = True
        self.links = set()
        self.monitor = None

    def __repr__(self): return f"<{self.name}:{self.pid}>"

class Supervisor:
    def __init__(self, strategy="one_for_one"):
        self.strategy = strategy
        self.children = {}  # pid -> (name, behavior)
        self.restarts = {}

    def add_child(self, actor):
        self.children[actor.pid] = (actor.name, actor.behavior)
        self.restarts[actor.pid] = 0

class ActorSystem:
    def __init__(self):
        self.actors = {}
        self.supervisors = {}
        self.log = []
        self.dead_letters = []

    def spawn(self, name, behavior):
        actor = Actor(name, behavior)
        self.actors[actor.pid] = actor
        self._log(f"Spawned {actor}")
        return actor

    def send(self, target, msg):
        if isinstance(target, Actor): target = target.pid
        actor = self.actors.get(target)
        if actor and actor.alive:
            actor.mailbox.append(msg)
        else:
            self.dead_letters.append((target, msg))

    def link(self, a, b):
        a.links.add(b.pid); b.links.add(a.pid)

    def kill(self, actor, reason="killed"):
        if not actor.alive: return
        actor.alive = False
        self._log(f"{actor} died: {reason}")
        # Notify linked actors
        for linked_pid in actor.links:
            linked = self.actors.get(linked_pid)
            if linked and linked.alive:
                self.send(linked, Message(actor, "EXIT", reason))
        # Check supervisors
        for sup_pid, sup in self.supervisors.items():
            if actor.pid in sup.children:
                self._restart(sup, actor)

    def _restart(self, sup, dead_actor):
        name, behavior = sup.children[dead_actor.pid]
        sup.restarts[dead_actor.pid] = sup.restarts.get(dead_actor.pid, 0) + 1
        if sup.restarts[dead_actor.pid] > 5:
            self._log(f"Max restarts for {dead_actor}, giving up")
            return
        new_actor = self.spawn(name, behavior)
        sup.children[new_actor.pid] = sup.children.pop(dead_actor.pid)
        sup.restarts[new_actor.pid] = sup.restarts.pop(dead_actor.pid)
        self._log(f"Supervisor restarted {dead_actor} as {new_actor}")

    def tick(self, max_messages=100):
        """Process up to max_messages across all actors."""
        processed = 0
        for actor in list(self.actors.values()):
            if not actor.alive or not actor.mailbox: continue
            msg = actor.mailbox.popleft()
            try:
                result = actor.behavior(self, actor, msg)
                if result == "stop":
                    self.kill(actor, "normal")
            except Exception as e:
                self._log(f"{actor} crashed: {e}")
                self.kill(actor, str(e))
            processed += 1
            if processed >= max_messages: break
        return processed

    def run(self, ticks=100):
        total = 0
        for _ in range(ticks):
            n = self.tick()
            total += n
            if n == 0: break
        return total

    def _log(self, msg):
        self.log.append(msg)

def main():
    print("=== Actor Model (Erlang-style) ===\n")
    sys = ActorSystem()

    # Counter actor
    counters = {}
    def counter_behavior(sys, self, msg):
        if self.pid not in counters: counters[self.pid] = 0
        if msg.tag == "inc":
            counters[self.pid] += msg.data or 1
        elif msg.tag == "get":
            sys.send(msg.sender, Message(self, "count", counters[self.pid]))
        elif msg.tag == "crash":
            raise RuntimeError("intentional crash")

    # Ping-pong actors
    pong_count = [0]
    def ping(sys, self, msg):
        if msg.tag == "start":
            sys.send(msg.data, Message(self, "ping", 10))
        elif msg.tag == "pong":
            if msg.data > 0:
                sys.send(msg.sender, Message(self, "ping", msg.data - 1))
            else:
                print(f"  Ping-pong complete! {pong_count[0]} exchanges")

    def pong(sys, self, msg):
        if msg.tag == "ping":
            pong_count[0] += 1
            sys.send(msg.sender, Message(self, "pong", msg.data - 1))

    # Create actors
    c1 = sys.spawn("counter", counter_behavior)
    p1 = sys.spawn("ping", ping)
    p2 = sys.spawn("pong", pong)

    # Supervision
    sup = Supervisor("one_for_one")
    sup.add_child(c1)
    sys.supervisors[0] = sup

    # Send messages
    sys.send(c1, Message(None, "inc", 5))
    sys.send(c1, Message(None, "inc", 3))
    sys.send(c1, Message(p1, "get"))
    sys.send(p1, Message(None, "start", p2))

    total = sys.run()
    print(f"Processed {total} messages")

    # Crash and restart
    print(f"\nCrashing counter:")
    sys.send(c1, Message(None, "crash"))
    sys.run()

    print(f"\nSystem log:")
    for entry in sys.log:
        print(f"  {entry}")
    print(f"\nDead letters: {len(sys.dead_letters)}")
    print(f"Active actors: {sum(1 for a in sys.actors.values() if a.alive)}")

if __name__ == "__main__":
    main()
