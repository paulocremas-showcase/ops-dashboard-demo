"""Smoke tests, not a full suite. Run directly: python tests/test_dashboard.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.app import find_collisions


def test_collision_detection_flags_overlapping_different_jobs():
    now = datetime.now(timezone.utc)
    a = {"job_name": "a", "started_at": now.isoformat(), "finished_at": (now + timedelta(minutes=10)).isoformat()}
    b = {
        "job_name": "b",
        "started_at": (now + timedelta(minutes=5)).isoformat(),
        "finished_at": (now + timedelta(minutes=15)).isoformat(),
    }
    c = {
        "job_name": "c",
        "started_at": (now + timedelta(minutes=20)).isoformat(),
        "finished_at": (now + timedelta(minutes=25)).isoformat(),
    }

    collisions = find_collisions([a, b, c])
    assert len(collisions) == 1
    assert {collisions[0][0]["job_name"], collisions[0][1]["job_name"]} == {"a", "b"}


def test_collision_detection_ignores_same_job_overlap():
    now = datetime.now(timezone.utc)
    a1 = {"job_name": "a", "started_at": now.isoformat(), "finished_at": (now + timedelta(minutes=10)).isoformat()}
    a2 = {
        "job_name": "a",
        "started_at": (now + timedelta(minutes=5)).isoformat(),
        "finished_at": (now + timedelta(minutes=15)).isoformat(),
    }
    assert find_collisions([a1, a2]) == []


if __name__ == "__main__":
    test_collision_detection_flags_overlapping_different_jobs()
    test_collision_detection_ignores_same_job_overlap()
    print("all tests passed")
