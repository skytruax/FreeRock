"""Written pieces on the server: the kind of place the player is told of, love and ban on a whole
piece, what the control page is told, and the feed leaving the parts of pieces alone."""
import json

import numpy as np

from freerock import atlas, forever
from freerock import state as game
from test_forever import fill, next_of, publish, running, shallow_pools, until  # noqa: F401  (small pools, as there)

RATE = forever.RATE
BAR = 2 * RATE                 # a two-second bar


def tone(hz, bars, post_s=1.0, level=0.2):
    frames = bars * BAR + int(post_s * RATE)
    wave = level * np.sin(2 * np.pi * hz * np.arange(frames) / RATE).astype(np.float32)
    return np.stack([wave, wave], axis=1)


def add_piece(bucket, title="The Long Dark", bars=6, **more):
    """A made-up piece of three parts, six bars long in stretches of four, with a second of
    what it went on to."""
    parts = {("rhythm", 1): tone(220.0, bars), ("drums", 1): tone(110.0, bars), ("bass", 1): tone(55.0, bars)}
    said = {"title": title, "bar_frames": BAR, "bars": 4, "post": RATE, "tonic": "D minor", "moods": ["haunted"]}
    said.update(more)
    return bucket.add_piece(parts, **said)


async def told_of(socket, kinds):
    """The first target that names these kinds of place. (One sent before the game had said
    where the player is names none, and may still be on its way on a busy machine.)"""
    for _ in range(12):
        target = (await next_of(socket, "target"))["target"]
        if target["kinds"] == kinds:
            return target
    raise AssertionError("the player was never told of %s" % kinds)


async def test_the_kind_of_place_goes_to_the_player_and_changes_at_a_border(tmp_path):
    client, app, conductor, _ = await running(tmp_path, with_filler=False)
    try:
        fill(conductor.buckets.get("Duskwood", "knight"), forever.FIRST[:5])
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Duskwood")
        target = await told_of(socket, ["haunted"])
        assert (target["kinds"], target["light"]) == (["haunted"], False)
        assert isinstance(target["also"], list) and target["place"] == "wander"
        # Across the border into farmland: the player is told at once, music or no music to change.
        publish(app, zone_name="Elwynn Forest")
        target = await told_of(socket, ["pastoral"])
        assert (target["kinds"], target["light"]) == (["pastoral"], True)
        # A named place inside a zone adds what its own name says: an inn is a light place even in haunted country.
        publish(app, zone_name="Duskwood", subzone_name="Scarlet Raven Tavern")
        target = await told_of(socket, ["pastoral", "haunted"])
        assert (target["kinds"], target["light"]) == (["pastoral", "haunted"], True)
        # A place nobody has listed gets its kind from the words in its name.
        publish(app, zone_name="The Deadmines")
        assert (await told_of(socket, ["infernal"]))["kinds"] == ["infernal"]
        status = await (await client.get("/api/music")).json()
        assert (status["forever"]["kinds"], status["forever"]["light"]) == (["infernal"], False)
        # The pretend game on the player page goes the same way: a walk into Westfall.
        response = await client.post("/api/pretend", json={"zone_name": "Westfall", "daytime": True})
        assert response.status == 200
        target = await told_of(socket, ["pastoral"])
        assert (target["kinds"], target["light"]) == (["pastoral"], False)
    finally:
        await client.close()


def test_every_zone_has_a_kind_and_a_place_with_no_name_has_none():
    for name in atlas.names():
        found, light = atlas.kinds_for(name)
        assert 1 <= len(found) <= 2 and isinstance(light, bool), name
    assert atlas.kinds_for(None) == ([], False) and atlas.kinds_for("") == ([], False)
    assert atlas.kinds_for("Somewhere Nobody Has Been") == ([], False)
    # The zone's own name given again as the place adds nothing.
    assert atlas.kinds_for("Duskwood", "Duskwood") == atlas.kinds_for("Duskwood")
    # A dark place in light country is not a light one; a plain one is.
    assert atlas.kinds_for("Elwynn Forest", "Fargodeep Mine")[1] is False
    assert atlas.kinds_for("Elwynn Forest", "Northshire Valley")[1] is True


async def test_love_and_ban_are_for_the_whole_piece(tmp_path):
    client, app, conductor, _ = await running(tmp_path, with_filler=False)
    try:
        bucket = conductor.buckets.get("Duskwood", "knight")
        fill(bucket, forever.FIRST[:5])
        piece = add_piece(bucket)
        other = add_piece(bucket, title="Another")
        parts = [clip.id for clip in bucket.clips if clip.piece == piece]
        assert len(parts) == 6, "three parts, each in two stretches"
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Duskwood")
        described = (await next_of(socket, "bucket"))["bucket"]
        assert set(described["pieces"]) == {piece, other}
        playing = {"rhythm": {"id": parts[0], "tier": 1}}
        await socket.send_str(json.dumps({"type": "status", "forever": True, "started": True, "context": "running",
                                          "bucket": described["key"], "heard": [parts[0]], "playing": playing,
                                          "piece": {"id": piece, "title": "The Long Dark", "story": "", "at": 3.0, "of": 12.0}}))
        await until(lambda: next(clip for clip in bucket.clips if clip.id == parts[0]).plays == 1)
        app["hub"].publish(game.CommandReceived(name="love", count=1))
        await until(lambda: bucket.pieces[piece]["loved"])
        assert all(clip.loved for clip in bucket.clips if clip.piece == piece)
        assert not bucket.pieces[other]["loved"]
        assert any("The piece The Long Dark is marked as loved." in note for note in conductor.notes)
        # A ban on the part that is playing takes every part of the piece out of play, and the page is told of them all.
        app["hub"].publish(game.CommandReceived(name="ban", count=2))
        gone = await next_of(socket, "retired")
        assert gone["key"] == described["key"] and sorted(gone["ids"]) == sorted(parts)
        assert set(bucket.live_pieces()) == {other}
        assert not [clip for clip in bucket.live() if clip.piece == piece]
        assert any("The piece The Long Dark is banned." in note for note in conductor.notes)
        # The loose phrases and the other piece are untouched.
        assert len([clip for clip in bucket.live() if not clip.piece]) == 5
    finally:
        await client.close()


async def test_the_control_page_is_told_of_pieces_apart_from_phrases(tmp_path):
    client, app, conductor, _ = await running(tmp_path, with_filler=False)
    try:
        bucket = conductor.buckets.get("Duskwood", "knight")
        fill(bucket, forever.FIRST[:5])
        piece = add_piece(bucket)
        socket = await client.ws_connect("/ws/player")
        publish(app, zone_name="Duskwood")
        described = (await next_of(socket, "bucket"))["bucket"]
        assert any("1 written pieces and 5 loose phrases" in note for note in conductor.notes)
        # The audio of a part is there to be fetched whole: its stretch and what the music went on to.
        part = next(clip for clip in described["clips"] if clip.get("piece") == piece and clip["order"] == 0)
        response = await client.get("/phrase/knight/duskwood/" + part["id"])
        assert response.status == 200 and len(await response.read()) == (part["frames"] + part["post"]) * 4
        said = {"id": piece, "title": "The Long Dark", "story": "theme", "track": "", "role": "wander", "at": 3.0, "of": 12.0}
        await socket.send_str(json.dumps({"type": "status", "forever": True, "started": True, "context": "running",
                                          "bucket": described["key"], "heard": [], "playing": {}, "piece": said, "pieces": 1}))
        await until(lambda: any(status.get("piece") for status in conductor.statuses.values()))
        status = (await (await client.get("/api/music")).json())["forever"]
        assert (status["phrases"], status["pieces"], status["parts"]) == (5, 1, 6)
        assert status["playing_piece"] == said
        assert status["pools"]["drums steady"] == 1, "a pool counts loose phrases, not the parts of pieces"
    finally:
        await client.close()


async def test_the_feed_takes_no_notice_of_the_parts_of_pieces(tmp_path):
    client, app, conductor, filler = await running(tmp_path)
    try:
        bucket = conductor.buckets.get("Duskwood", "knight")
        add_piece(bucket)
        await client.ws_connect("/ws/player")
        publish(app, zone_name="Duskwood")
        # A bucket that has a piece and no loose phrases is fed from the beginning, pool by pool.
        await until(lambda: bucket.started())
        assert [(channel, tier) for _, channel, tier, _, _ in filler.asked[:len(forever.FIRST)]] == list(forever.FIRST)
        await until(lambda: all(count == forever.MOST for count in bucket.counts().values()), timeout=20)
        assert len(bucket.live_pieces()) == 1 and len([clip for clip in bucket.live() if clip.piece]) == 6
        assert not [clip for clip in bucket.clips if clip.piece and clip.retired], "a part of a piece is never set aside as worn"
    finally:
        await client.close()


async def test_a_page_that_connects_is_told_where_the_player_is_before_it_is_given_the_music(tmp_path):
    client, app, conductor, _ = await running(tmp_path, with_filler=False)
    try:
        fill(conductor.buckets.get("Duskwood", "knight"), forever.FIRST[:5])
        first = await client.ws_connect("/ws/player")
        publish(app, zone_name="Duskwood")
        await next_of(first, "bucket")
        # A second page, opened while the game is being played: the kind of place comes before
        # the bucket, so the first piece it chooses is one for where the player is.
        second = await client.ws_connect("/ws/player")
        kinds = []
        while True:
            message = json.loads(await second.receive_str())
            kinds.append(message["type"])
            if message["type"] == "bucket":
                break
            if message["type"] == "target":
                assert message["target"]["kinds"] == ["haunted"]
        assert kinds.index("target") < kinds.index("bucket")
    finally:
        await client.close()
