"""Tests for daemon registry — lifecycle, hierarchy, tree ordering."""

import time
from reeree.daemon_registry import Daemon, DaemonKind, DaemonStatus, DaemonRegistry


class TestDaemonDataclass:
    def test_defaults(self):
        d = Daemon(id=1, kind=DaemonKind.STEP, description="test step")
        assert d.status == DaemonStatus.ACTIVE
        assert d.parent_id is None
        assert d.step_index == -1
        assert d.log == ""
        assert d.is_active

    def test_elapsed_str_seconds(self):
        d = Daemon(id=1, kind=DaemonKind.STEP, description="x",
                   start_time=time.monotonic() - 5)
        assert "5s" in d.elapsed_str or "4s" in d.elapsed_str  # timing tolerance

    def test_elapsed_str_minutes(self):
        d = Daemon(id=1, kind=DaemonKind.STEP, description="x",
                   start_time=time.monotonic() - 125)
        assert "2:0" in d.elapsed_str  # "2:05" ish

    def test_append_log(self):
        d = Daemon(id=1, kind=DaemonKind.STEP, description="x")
        d.append_log("line one")
        d.append_log("line two")
        assert "line one\nline two\n" == d.log
        assert d.last_log_time > 0


class TestDaemonRegistry:
    def test_spawn_returns_daemon(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.STEP, "do stuff")
        assert d.id == 1
        assert d.kind == DaemonKind.STEP
        assert d.description == "do stuff"
        assert d.is_active

    def test_ids_increment(self):
        reg = DaemonRegistry()
        d1 = reg.spawn(DaemonKind.STEP, "first")
        d2 = reg.spawn(DaemonKind.STEP, "second")
        assert d1.id == 1
        assert d2.id == 2

    def test_get(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.STEP, "test")
        assert reg.get(d.id) is d
        assert reg.get(999) is None

    def test_kill(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.STEP, "killme")
        assert reg.kill(d.id)
        assert d.status == DaemonStatus.FAILED
        assert d.error == "killed"

    def test_kill_nonexistent(self):
        reg = DaemonRegistry()
        assert not reg.kill(999)

    def test_kill_cascades_to_children(self):
        reg = DaemonRegistry()
        parent = reg.spawn(DaemonKind.EXECUTOR, "parent")
        child1 = reg.spawn(DaemonKind.STEP, "child1", parent_id=parent.id)
        child2 = reg.spawn(DaemonKind.STEP, "child2", parent_id=parent.id)
        done_child = reg.spawn(DaemonKind.STEP, "done", parent_id=parent.id)
        done_child.status = DaemonStatus.DONE

        reg.kill(parent.id)
        assert child1.status == DaemonStatus.FAILED
        assert child2.status == DaemonStatus.FAILED
        assert done_child.status == DaemonStatus.DONE  # already done, not touched

    def test_pause_resume(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.STEP, "pause me")
        assert reg.pause(d.id)
        assert d.status == DaemonStatus.PAUSED
        assert not d.is_active

        assert reg.resume(d.id)
        assert d.status == DaemonStatus.ACTIVE
        assert d.is_active

    def test_pause_nonactive_fails(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.STEP, "done")
        d.status = DaemonStatus.DONE
        assert not reg.pause(d.id)

    def test_resume_nonpaused_fails(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.STEP, "active")
        assert not reg.resume(d.id)  # already active

    def test_children(self):
        reg = DaemonRegistry()
        parent = reg.spawn(DaemonKind.EXECUTOR, "parent")
        c1 = reg.spawn(DaemonKind.STEP, "c1", parent_id=parent.id)
        c2 = reg.spawn(DaemonKind.COHERENCE, "c2", parent_id=parent.id)
        _orphan = reg.spawn(DaemonKind.STEP, "orphan")  # no parent

        children = reg.children(parent.id)
        assert len(children) == 2
        assert c1 in children
        assert c2 in children

    def test_active(self):
        reg = DaemonRegistry()
        d1 = reg.spawn(DaemonKind.STEP, "a")
        d2 = reg.spawn(DaemonKind.STEP, "b")
        d2.status = DaemonStatus.DONE
        d3 = reg.spawn(DaemonKind.STEP, "c")

        active = reg.active()
        assert len(active) == 2
        assert d1 in active
        assert d3 in active

    def test_active_count(self):
        reg = DaemonRegistry()
        reg.spawn(DaemonKind.STEP, "a")
        reg.spawn(DaemonKind.STEP, "b")
        d3 = reg.spawn(DaemonKind.STEP, "c")
        d3.status = DaemonStatus.FAILED
        assert reg.active_count == 2
        assert reg.total_count == 3


class TestDaemonTree:
    def test_single_root(self):
        reg = DaemonRegistry()
        d = reg.spawn(DaemonKind.EXECUTOR, "root")
        tree = reg.tree()
        assert tree == [(d, 0)]

    def test_parent_child(self):
        reg = DaemonRegistry()
        parent = reg.spawn(DaemonKind.EXECUTOR, "parent")
        child = reg.spawn(DaemonKind.STEP, "child", parent_id=parent.id)
        tree = reg.tree()
        assert tree == [(parent, 0), (child, 1)]

    def test_deep_hierarchy(self):
        reg = DaemonRegistry()
        root = reg.spawn(DaemonKind.EXECUTOR, "root")
        mid = reg.spawn(DaemonKind.STEP, "mid", parent_id=root.id)
        leaf = reg.spawn(DaemonKind.COHERENCE, "leaf", parent_id=mid.id)
        tree = reg.tree()
        assert tree == [(root, 0), (mid, 1), (leaf, 2)]

    def test_multiple_roots(self):
        reg = DaemonRegistry()
        r1 = reg.spawn(DaemonKind.EXECUTOR, "root1")
        r2 = reg.spawn(DaemonKind.EXECUTOR, "root2")
        tree = reg.tree()
        assert tree == [(r1, 0), (r2, 0)]

    def test_tree_ordering(self):
        """Children sorted by ID, depth-first."""
        reg = DaemonRegistry()
        root = reg.spawn(DaemonKind.EXECUTOR, "root")
        c2 = reg.spawn(DaemonKind.STEP, "step2", parent_id=root.id)
        c1_child = reg.spawn(DaemonKind.COHERENCE, "cohere", parent_id=c2.id)
        c3 = reg.spawn(DaemonKind.STEP, "step3", parent_id=root.id)

        tree = reg.tree()
        assert tree == [
            (root, 0),
            (c2, 1),
            (c1_child, 2),
            (c3, 1),
        ]

    def test_daemon_kind_enum(self):
        assert DaemonKind.EXECUTOR.value == "executor"
        assert DaemonKind.STEP.value == "step"
        assert DaemonKind.COHERENCE.value == "coherence"

    def test_daemon_status_enum(self):
        assert DaemonStatus.ACTIVE.value == "active"
        assert DaemonStatus.PAUSED.value == "paused"
        assert DaemonStatus.DONE.value == "done"
        assert DaemonStatus.FAILED.value == "failed"

    def test_spawn_with_all_params(self):
        reg = DaemonRegistry()
        parent = reg.spawn(DaemonKind.EXECUTOR, "parent")
        d = reg.spawn(
            kind=DaemonKind.STEP,
            description="do thing",
            parent_id=parent.id,
            step_index=3,
            scope="myproject",
            model="qwen3-coder",
        )
        assert d.parent_id == parent.id
        assert d.step_index == 3
        assert d.scope == "myproject"
        assert d.model == "qwen3-coder"
