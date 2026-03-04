"""Tests for inter-daemon message bus."""

from reeree.message_bus import DaemonMessage, MessageKind, MessageBus


class TestDaemonMessage:
    def test_format_log_direct(self):
        msg = DaemonMessage(sender_id=1, recipient_id=2, kind=MessageKind.NOTE, payload="hello")
        assert msg.format_log() == "[d1→d2] note: hello"

    def test_format_log_broadcast(self):
        msg = DaemonMessage(sender_id=1, recipient_id=None, kind=MessageKind.CONFLICT, payload="file clash")
        assert msg.format_log() == "[d1→*] conflict: file clash"

    def test_format_context(self):
        msg = DaemonMessage(sender_id=3, recipient_id=1, kind=MessageKind.REQUEST, payload="what return type?")
        assert "daemon 3" in msg.format_context()
        assert "request" in msg.format_context()

    def test_message_kinds(self):
        assert MessageKind.NOTE.value == "note"
        assert MessageKind.REQUEST.value == "request"
        assert MessageKind.RESPONSE.value == "response"
        assert MessageKind.CONFLICT.value == "conflict"
        assert MessageKind.DONE.value == "done"


class TestMessageBus:
    def test_send_direct_message(self):
        bus = MessageBus()
        bus.register_daemon(1)
        bus.register_daemon(2)
        bus.send(DaemonMessage(sender_id=1, recipient_id=2, kind=MessageKind.NOTE, payload="hi"))

        # Recipient gets it
        msgs = bus.receive(2)
        assert len(msgs) == 1
        assert msgs[0].payload == "hi"

        # Mailbox is cleared after receive
        assert bus.receive(2) == []

    def test_broadcast_message(self):
        bus = MessageBus()
        bus.register_daemon(1)
        bus.register_daemon(2)
        bus.register_daemon(3)
        bus.broadcast(1, MessageKind.NOTE, "heads up")

        # All registered daemons get it
        assert len(bus.receive(2)) == 1
        assert len(bus.receive(3)) == 1

    def test_peek_doesnt_clear(self):
        bus = MessageBus()
        bus.register_daemon(1)
        bus.send(DaemonMessage(sender_id=2, recipient_id=1, kind=MessageKind.NOTE, payload="peek"))

        # Peek
        msgs = bus.peek(1)
        assert len(msgs) == 1

        # Still there
        msgs = bus.peek(1)
        assert len(msgs) == 1

        # Receive clears
        msgs = bus.receive(1)
        assert len(msgs) == 1
        assert bus.receive(1) == []

    def test_subscribe_callback(self):
        bus = MessageBus()
        received = []
        bus.subscribe(lambda msg: received.append(msg))

        bus.send(DaemonMessage(sender_id=1, recipient_id=None, kind=MessageKind.DONE, payload="done"))
        assert len(received) == 1
        assert received[0].kind == MessageKind.DONE

    def test_unsubscribe(self):
        bus = MessageBus()
        received = []
        callback = lambda msg: received.append(msg)
        bus.subscribe(callback)
        bus.unsubscribe(callback)

        bus.send(DaemonMessage(sender_id=1, recipient_id=None, kind=MessageKind.NOTE, payload="x"))
        assert len(received) == 0

    def test_broken_subscriber_doesnt_crash(self):
        bus = MessageBus()
        bus.register_daemon(1)

        def bad_callback(msg):
            raise RuntimeError("boom")

        bus.subscribe(bad_callback)

        # Should not raise
        bus.send(DaemonMessage(sender_id=1, recipient_id=None, kind=MessageKind.NOTE, payload="ok"))

    def test_history(self):
        bus = MessageBus()
        bus.send(DaemonMessage(sender_id=1, recipient_id=None, kind=MessageKind.NOTE, payload="a"))
        bus.send(DaemonMessage(sender_id=2, recipient_id=None, kind=MessageKind.NOTE, payload="b"))
        assert len(bus.history) == 2
        assert bus.history[0].payload == "a"
        assert bus.history[1].payload == "b"

    def test_pending_count(self):
        bus = MessageBus()
        bus.register_daemon(1)
        bus.register_daemon(2)
        bus.send(DaemonMessage(sender_id=3, recipient_id=1, kind=MessageKind.NOTE, payload="a"))
        bus.send(DaemonMessage(sender_id=3, recipient_id=2, kind=MessageKind.NOTE, payload="b"))
        assert bus.pending_count == 2

        bus.receive(1)
        assert bus.pending_count == 1

    def test_serialize_deserialize(self):
        bus = MessageBus()
        bus.send(DaemonMessage(sender_id=1, recipient_id=2, kind=MessageKind.NOTE, payload="hello"))
        bus.send(DaemonMessage(sender_id=2, recipient_id=None, kind=MessageKind.CONFLICT, payload="clash"))

        data = bus.to_dict()
        restored = MessageBus.from_dict(data)

        assert len(restored.history) == 2
        assert restored.history[0].payload == "hello"
        assert restored.history[0].kind == MessageKind.NOTE
        assert restored.history[1].kind == MessageKind.CONFLICT

    def test_unregister_daemon(self):
        bus = MessageBus()
        bus.register_daemon(1)
        bus.send(DaemonMessage(sender_id=2, recipient_id=1, kind=MessageKind.NOTE, payload="x"))
        bus.unregister_daemon(1)
        # Mailbox gone
        assert bus.receive(1) == []
