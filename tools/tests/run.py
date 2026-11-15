#!/usr/bin/env python3
"""Runs FreeRock's Lua tests without the game.

    cd app && uv run --no-sync python ../tools/tests/run.py [name-filter] [--globals]

Every test runs in its own Lua 5.1 state: the stand-in client (wowmock.lua) is loaded, then one
scenario from tests.lua, which loads the addon's files in .toc order. The shared test vectors
(protocol/vectors.json) are handed to Lua as the table VECTORS. Exit status is non-zero if any
test fails.
"""
import json
import os
import sys

from lupa import lua51

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def to_lua(lua, value):
    """A Python list or dict as a Lua table, all the way down (lists start at 1)."""
    if isinstance(value, dict):
        table = lua.table()
        for key, item in value.items():
            table[key] = to_lua(lua, item)
        return table
    if isinstance(value, (list, tuple)):
        table = lua.table()
        for index, item in enumerate(value, start=1):
            table[index] = to_lua(lua, item)
        return table
    return value


def load_vectors():
    vectors = json.loads(read(os.path.join("protocol", "vectors.json")))
    for case in vectors["frames"]:
        case["frame"]["text_bytes"] = list(bytes.fromhex(case["frame"]["text_bytes"]))
        case["payload"] = list(bytes.fromhex(case["payload"]))
    for case in vectors["names"]:
        # Lua strings are bytes: hand the name over as its UTF-8 bytes.
        case["text"] = case["text"].encode("utf-8")
        case["sent"] = list(bytes.fromhex(case["sent"]))
    return vectors


def new_state(vectors):
    lua = lua51.LuaRuntime(unpack_returned_tuples=True, encoding=None)
    g = lua.globals()
    g[b"ReadFile"] = lambda path: read(path.decode("utf-8")).encode("utf-8")
    g[b"VECTORS"] = to_lua(lua, bytes_keys(vectors))
    load = lua.eval(b"function(src, name) return assert(loadstring(src, name))() end")
    for name in ("wowmock.lua", "tests.lua"):
        load(read(os.path.join("tools", "tests", name)).encode("utf-8"), b"@tools/tests/" + name.encode())
    return lua


def bytes_keys(value):
    """With encoding=None Lua sees Python bytes as strings, so every str becomes bytes."""
    if isinstance(value, dict):
        return {bytes_keys(key): bytes_keys(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [bytes_keys(item) for item in value]
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def text(value):
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def main():
    args = [a for a in sys.argv[1:] if a != "--globals"]
    wanted = args[0] if args else ""
    vectors = load_vectors()
    reads, writes = set(), set()
    names = [text(t[b"name"]) for t in new_state(vectors).globals()[b"TESTS"].values()]
    failed = 0
    ran = 0
    for index, name in enumerate(names, start=1):
        if wanted not in name:
            continue
        ran += 1
        lua = new_state(vectors)
        run = lua.eval(b"""function(index)
            local ok, err = xpcall(TESTS[index].fn, function(e) return debug.traceback(tostring(e), 2) end)
            return ok, err
        end""")
        ok, err = run(index)
        reads.update(text(k) for k in lua.globals()[b"GLOBAL_READS"].keys())
        writes.update(text(k) for k in lua.globals()[b"GLOBAL_WRITES"].keys())
        if ok:
            print("ok    " + name)
        else:
            failed += 1
            print("FAIL  " + name)
            print("      " + text(err).replace("\n", "\n      "))
    print("\n%d run, %d failed" % (ran, failed))
    if "--globals" in sys.argv:
        print("\nGlobals the addon read while the tests ran:\n  " + " ".join(sorted(reads)))
        print("\nGlobals it wrote:\n  " + " ".join(sorted(writes)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
