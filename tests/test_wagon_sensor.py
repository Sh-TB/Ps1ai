"""Regression tests for the Issue-7 wagon sensor (synthetic tables)."""
import base64
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ps1play.agent.wagon import (WagonSensor, TABLE, STRIDE, HP_OFF)


def make_ram():
    return np.zeros(0x200000, dtype=np.uint8)


def set_entity(ram, slot, hp=0xA0, tag=b"\x11\x22\x33\x44", pos=0):
    a = TABLE + slot * STRIDE
    head = bytearray(ram[a:a + HP_OFF])
    head[pos % len(head)] = (head[pos % len(head)] or 0xAA)
    ram[a:a + len(head)] = np.frombuffer(bytes(head), dtype=np.uint8)
    ram[a + 0x04:a + 0x08] = np.frombuffer(tag, dtype=np.uint8)
    ram[a + HP_OFF] = hp & 0xFF
    ram[a + HP_OFF + 1] = (hp >> 8) & 0xFF


def clear_entity(ram, slot):
    a = TABLE + slot * STRIDE
    ram[a:a + STRIDE] = 0


def test_spawn_despawn_basic():
    ram = make_ram()
    s = WagonSensor(ram, every=10)
    evs = s.poll(0)
    assert evs == [] and s.series[-1]["occ"] == "0" * s.slots
    set_entity(ram, 3, hp=0xA0)
    evs = s.poll(10)
    assert [(e["type"], e["slot"]) for e in evs] == [("spawn", 3)]
    assert evs[0]["hp"] == 0xA0
    dump = base64.b64decode(evs[0]["dump_b64"])
    assert len(dump) == STRIDE
    clear_entity(ram, 3)
    evs = s.poll(20)
    assert [(e["type"], e["slot"]) for e in evs] == [("despawn", 3)]
    assert evs[0]["age"] == 10


def test_no_double_count_while_occupied():
    ram = make_ram()
    s = WagonSensor(ram, every=10)
    set_entity(ram, 5)
    s.poll(10)
    set_entity(ram, 5, hp=0x8F)          # HP changes but stays occupied
    evs = s.poll(20)
    assert [e["type"] for e in evs] == []
    assert len([e for e in s.spawns if e["slot"] == 5]) == 1


def test_poll_rate_limit():
    ram = make_ram()
    s = WagonSensor(ram, every=10)
    s.poll(0)                            # first poll always samples
    set_entity(ram, 2)
    assert s.poll(5) == []               # below `every` -> skipped
    evs = s.poll(10)
    assert [(e["type"], e["slot"]) for e in evs] == [("spawn", 2)]


def test_persistent_slot_threshold():
    ram = make_ram()
    s = WagonSensor(ram, every=10, persist_frames=45)
    set_entity(ram, 7)
    f = 0
    for _ in range(6):                   # spawn poll + 5 re-samples
        f += 10
        s.poll(f)
    pers = s.persistent_slots()
    assert 7 in pers and pers[7]["frames_present"] == 50
    clear_entity(ram, 7)
    s.poll(f + 10)
    assert 7 not in s.persistent_slots()


def test_slot_reuse_spawns_again():
    ram = make_ram()
    s = WagonSensor(ram, every=10)
    set_entity(ram, 1)
    s.poll(10)
    clear_entity(ram, 1)
    s.poll(20)
    set_entity(ram, 1, hp=0x50)          # recycled slot = new entity
    evs = s.poll(30)
    assert [(e["type"], e["slot"]) for e in evs] == [("spawn", 1)]
    assert len(s.spawns) == 2


def test_summary_shape():
    ram = make_ram()
    s = WagonSensor(ram, every=10)
    set_entity(ram, 9)
    s.poll(10)
    summ = s.summary()
    assert summ["schema"] == "ps1play-wagon/1"
    assert summ["spawn_events"] == 1
    assert summ["slots_polled"] == s.slots
    assert summ["polls"] == 1
