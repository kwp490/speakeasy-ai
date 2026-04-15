"""Tests for engine loading, model file detection, and registry."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from dictator.engine import ENGINES, _model_files_exist, get_available_engines
from dictator.engine.granite_speech import GraniteSpeechEngine


class TestEngineRegistry(unittest.TestCase):
    """Engine registry must contain Granite and Cohere."""

    def test_granite_registered(self):
        self.assertIn("granite", ENGINES)

    def test_cohere_registered(self):
        self.assertIn("cohere", ENGINES)

    def test_granite_engine_name(self):
        engine = ENGINES["granite"]()
        self.assertEqual(engine.name, "granite")

    def test_cohere_engine_name(self):
        engine = ENGINES["cohere"]()
        self.assertEqual(engine.name, "cohere")

    def test_granite_vram_estimate(self):
        engine = ENGINES["granite"]()
        self.assertGreater(engine.vram_estimate_gb, 0)

    def test_cohere_vram_estimate(self):
        engine = ENGINES["cohere"]()
        self.assertGreater(engine.vram_estimate_gb, 0)


class TestModelFileDetection(unittest.TestCase):
    """Model file detection must correctly identify present/absent models."""

    def test_granite_with_config(self):
        with tempfile.TemporaryDirectory() as d:
            granite_dir = os.path.join(d, "granite")
            os.makedirs(granite_dir)
            with open(os.path.join(granite_dir, "config.json"), "w") as f:
                f.write("{}")
            self.assertTrue(_model_files_exist("granite", d))

    def test_granite_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            granite_dir = os.path.join(d, "granite")
            os.makedirs(granite_dir)
            self.assertFalse(_model_files_exist("granite", d))

    def test_granite_no_directory(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(_model_files_exist("granite", d))

    def test_cohere_with_config(self):
        with tempfile.TemporaryDirectory() as d:
            cohere_dir = os.path.join(d, "cohere")
            os.makedirs(cohere_dir)
            with open(os.path.join(cohere_dir, "config.json"), "w") as f:
                f.write("{}")
            self.assertTrue(_model_files_exist("cohere", d))

    def test_cohere_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            cohere_dir = os.path.join(d, "cohere")
            os.makedirs(cohere_dir)
            self.assertFalse(_model_files_exist("cohere", d))

    def test_unknown_engine(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(_model_files_exist("nonexistent", d))


class TestGetAvailableEngines(unittest.TestCase):
    """get_available_engines must only return engines with model files."""

    def test_both_present(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("granite", "cohere"):
                engine_dir = os.path.join(d, name)
                os.makedirs(engine_dir)
                with open(os.path.join(engine_dir, "config.json"), "w") as f:
                    f.write("{}")
            available = get_available_engines(d)
            self.assertIn("granite", available)
            self.assertIn("cohere", available)

    def test_none_present(self):
        with tempfile.TemporaryDirectory() as d:
            available = get_available_engines(d)
            self.assertEqual(available, [])

    def test_only_granite_present(self):
        with tempfile.TemporaryDirectory() as d:
            granite_dir = os.path.join(d, "granite")
            os.makedirs(granite_dir)
            with open(os.path.join(granite_dir, "config.json"), "w") as f:
                f.write("{}")
            available = get_available_engines(d)
            self.assertIn("granite", available)
            self.assertNotIn("cohere", available)


class TestGraniteLoadBehavior(unittest.TestCase):
    """Granite engine must isolate runtime work in a dedicated worker process."""

    class _FakeConn:
        def __init__(self, messages=None):
            self._messages = list(messages or [])
            self.sent = []
            self.closed = False

        def poll(self, timeout=None):
            return bool(self._messages)

        def recv(self):
            return self._messages.pop(0)

        def send(self, payload):
            self.sent.append(payload)

        def close(self):
            self.closed = True

    class _FakeProcess:
        def __init__(self):
            self.started = False
            self.alive = True
            self.terminated = False
            self.join_calls = []

        def start(self):
            self.started = True

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True
            self.alive = False

        def join(self, timeout=None):
            self.join_calls.append(timeout)

    class _FakeContext:
        def __init__(self, parent_conn, child_conn, process):
            self.parent_conn = parent_conn
            self.child_conn = child_conn
            self.process = process
            self.process_target = None
            self.process_args = None
            self.process_daemon = None

        def Pipe(self):
            return self.parent_conn, self.child_conn

        def Process(self, target, args, daemon):
            self.process_target = target
            self.process_args = args
            self.process_daemon = daemon
            return self.process

    def test_granite_load_starts_worker_process(self):
        parent_conn = self._FakeConn([{"status": "ready"}])
        child_conn = self._FakeConn()
        process = self._FakeProcess()
        context = self._FakeContext(parent_conn, child_conn, process)

        with tempfile.TemporaryDirectory() as d:
            granite_dir = os.path.join(d, "granite")
            os.makedirs(granite_dir)
            Path(os.path.join(granite_dir, "config.json")).write_text("{}", encoding="utf-8")

            engine = GraniteSpeechEngine()
            engine._make_mp_context = MagicMock(return_value=context)
            engine.load(d, "cuda")

        self.assertTrue(process.started)
        self.assertTrue(context.process_daemon)
        self.assertIsNotNone(engine._model)
        self.assertIs(engine._worker_conn, parent_conn)
        self.assertIs(engine._worker_process, process)
        self.assertTrue(child_conn.closed)

    def test_granite_transcribe_round_trips_through_worker(self):
        engine = GraniteSpeechEngine()
        engine._model = object()
        engine._worker_process = self._FakeProcess()
        engine._worker_conn = self._FakeConn([{"status": "ok", "text": "hello world"}])

        result = engine.transcribe(np.zeros(16000, dtype=np.float32), 16000, "en")

        self.assertEqual(result, "hello world")
        self.assertEqual(engine._worker_conn.sent[0]["cmd"], "transcribe")
        self.assertEqual(engine._worker_conn.sent[0]["language"], "en")

    def test_granite_unload_requests_shutdown(self):
        engine = GraniteSpeechEngine()
        engine._model = object()
        engine._worker_process = self._FakeProcess()
        engine._worker_conn = self._FakeConn([{"status": "bye"}])

        engine.unload()

        self.assertEqual(engine._worker_conn, None)
        self.assertEqual(engine._worker_process, None)
