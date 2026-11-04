from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from throughput import main, measure, sweep


class ThroughputTests(unittest.TestCase):
    def test_timed_run_drains_last_request_and_excludes_warmup(self):
        now = 0.0
        calls = []

        def query(text, command):
            nonlocal now
            calls.append(text)
            now += 0.1
            return 1000

        client = Mock()
        client.query.side_effect = query
        with patch("throughput.SearchClient", return_value=client):
            with patch("throughput.time.monotonic", side_effect=lambda: now):
                result = measure("fake", "COUNT", ["a", "b"], 1, None, 0, duration=0.25)
        self.assertEqual(result["completed"], 3)
        self.assertAlmostEqual(result["elapsed_seconds"], 0.3)
        self.assertAlmostEqual(result["qps"], 10)
        self.assertEqual(len(calls), 5)  # Two warmup requests plus three measured.
        self.assertEqual(set(calls[2:]), {"a", "b"})

    def test_sweep_stops_and_refines(self):
        cases = [
            ("plateau", {1: 100, 2: 200, 4: 202, 8: 201, 3: 210, 6: 203},
             64, [1, 2, 4, 8, 3, 6], "plateau", 3),
            ("cap", {1: 100, 2: 200, 4: 400, 5: 500},
             5, [1, 2, 4, 5], "worker_cap", 5),
            ("regression", {1: 100, 2: 90, 4: 80},
             64, [1, 2, 4], "plateau", 1),
            ("recovery", {1: 100, 2: 101, 4: 200, 8: 400, 6: 300},
             8, [1, 2, 4, 8, 6], "worker_cap", 8),
        ]
        for name, scores, cap, expected, reason, best in cases:
            with self.subTest(name=name):
                run = Mock(side_effect=scores.__getitem__)
                with contextlib.redirect_stdout(io.StringIO()):
                    result = sweep(run, cap, 0.05)
                self.assertEqual([c.args[0] for c in run.call_args_list], expected)
                self.assertEqual(result["stop_reason"], reason)
                self.assertEqual(result["best_concurrency"], best)
                self.assertEqual(result["best_median_qps"], scores[best])

    def test_workers_overlap_and_warmup_is_excluded(self):
        clients = []
        overlap = threading.Barrier(2, timeout=5)

        class Client:
            def __init__(self, engine):
                self.calls = []
                self.closed = False
                self.process = Mock()
                clients.append(self)

            def query(self, query, command):
                self.calls.append(query)
                # Two warmup queries, then require both workers to be in flight.
                if len(self.calls) > 2:
                    overlap.wait()
                return 1000

            def close(self):
                self.closed = True

        with patch("throughput.SearchClient", Client):
            result = measure("fake", "COUNT", ["a", "b"], 2, 3, 0)

        self.assertEqual(result["completed"], 6)
        self.assertEqual(result["qps"], 6 / result["elapsed_seconds"])
        self.assertEqual(Counter(q for c in clients for q in c.calls[2:]),
                         Counter({"a": 3, "b": 3}))
        self.assertTrue(all(c.closed for c in clients))
        for client in clients:
            client.process.wait.assert_called_once()
        self.assertLessEqual(result["latency_us"]["p50"], result["latency_us"]["p99"])

    def test_failure_during_warmup_releases_other_workers(self):
        clients = []

        def create(engine):
            client = Mock()
            client.query.return_value = None if not clients else 1
            clients.append(client)
            return client

        with patch("throughput.SearchClient", side_effect=create):
            with self.assertRaisesRegex(ValueError, "does not support"):
                measure("fake", "COUNT", ["a"], 2, 2, 0)
        for client in clients:
            client.close.assert_called_once()
            client.process.wait.assert_called_once()

    def test_real_pipe_protocol_and_process_cleanup(self):
        from client import SearchClient

        clients = []

        def create(engine):
            client = SearchClient.__new__(SearchClient)
            client.process = subprocess.Popen(
                [sys.executable, "-u", "-c",
                 "import sys\nfor line in sys.stdin:\n print(1000, flush=True)"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            )
            clients.append(client)
            return client

        with patch("throughput.SearchClient", side_effect=create):
            result = measure("fake", "COUNT", ["a", "b", "c"], 2, 3, 0)
        self.assertEqual(result["completed"], 9)
        self.assertTrue(all(c.process.poll() == 0 for c in clients))

    def test_cli_saves_runs_and_median(self):
        with tempfile.TemporaryDirectory() as directory:
            queries = Path(directory) / "queries.jsonl"
            queries.write_text('{"query": "a", "tags": []}\n')
            output = Path(directory) / "results.json"
            argv = ["throughput.py", "fake", "--queries", str(queries),
                    "--commands", "TOP_10", "--concurrency", "1", "--repeats", "3", "--output", str(output)]
            runs = [{"qps": qps, "latency_us": {"p50": 1, "p95": 2, "p99": 3}}
                    for qps in (10, 30, 20)]
            with patch.object(sys, "argv", argv), patch("throughput.measure", side_effect=runs):
                with contextlib.redirect_stdout(io.StringIO()):
                    main()
            result = json.loads(output.read_text())["results"][0]
            self.assertEqual(result["median_qps"], 20)
            self.assertEqual(result["runs"], runs)


if __name__ == "__main__":
    unittest.main()
