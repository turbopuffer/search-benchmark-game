import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import random
import statistics
import threading
import time

from client import SearchClient, read_queries


def measure(engine, command, queries, concurrency, iterations, warmup, duration=None):
    workload = list(queries) * (iterations if duration is None else 1)
    random.Random(2).shuffle(workload)
    if not workload or concurrency < 1 or (duration is None and len(workload) < concurrency):
        raise ValueError("Each worker needs at least one measured query")

    started = None

    def start():
        nonlocal started
        started = time.monotonic()

    ready = threading.Barrier(concurrency, action=start)
    stopped = threading.Event()

    def worker(worker_id):
        client = None
        try:
            client = SearchClient(engine)

            def query(text):
                if client.query(text, command) is None:
                    raise ValueError(f"{engine} does not support {command}")

            # Always run one full pass, including when warmup is zero.
            warmup_started = time.monotonic()
            while True:
                for offset in range(len(queries)):
                    if stopped.is_set():
                        raise RuntimeError("Another worker failed")
                    query(queries[(offset + worker_id) % len(queries)])
                if time.monotonic() - warmup_started >= warmup:
                    break
            ready.wait()

            durations = []
            index = worker_id
            while True:
                if duration is None:
                    if index >= len(workload):
                        break
                elif time.monotonic() >= started + duration:
                    break
                if stopped.is_set():
                    raise RuntimeError("Another worker failed")
                before = time.monotonic()
                query(workload[index % len(workload)])
                durations.append((time.monotonic() - before) * 1e6)
                # Timed workers each traverse the full mix; striding could repeat
                # only a subset when the worker count divides the query count.
                index += concurrency if duration is None else 1
            return durations, time.monotonic()
        except BaseException:
            stopped.set()
            ready.abort()
            raise
        finally:
            if client is not None:
                client.close()
                # Reap the make process before starting the next benchmark.
                client.process.wait()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker, i) for i in range(concurrency)]
        results = [future.result() for future in futures]

    elapsed = max(finished for _, finished in results) - started
    durations = sorted(duration for values, _ in results for duration in values)
    if not durations:
        raise ValueError("No measured requests; increase the duration")
    return {
        "completed": len(durations),
        "elapsed_seconds": elapsed,
        "qps": len(durations) / elapsed,
        "latency_us": {
            f"p{p}": durations[math.ceil(len(durations) * p / 100) - 1]
            for p in (50, 95, 99)
        },
    }


def sweep(run_level, max_workers, min_gain):
    scores = {}
    best = 0
    stalled = 0
    concurrency = 1
    while True:
        qps = run_level(concurrency)
        scores[concurrency] = qps
        stalled = stalled + 1 if best and qps < best * (1 + min_gain) else 0
        best = max(best, qps)
        if stalled >= 2:
            reason = "plateau"
            break
        if concurrency == max_workers:
            reason = "worker_cap"
            break
        concurrency = min(concurrency * 2, max_workers)

    print(f"Sweep stopped: {reason}; refining around the best measured level", flush=True)
    levels = sorted(scores)
    best_workers = max(levels, key=scores.get)
    index = levels.index(best_workers)
    neighbors = levels[max(0, index - 1):index] + levels[index + 1:index + 2]
    for neighbor in neighbors:
        midpoint = (neighbor + best_workers) // 2
        if midpoint not in scores:
            scores[midpoint] = run_level(midpoint)
    best_workers = max(sorted(scores), key=scores.get)
    return {"stop_reason": reason, "best_concurrency": best_workers,
            "best_median_qps": scores[best_workers]}


def main():
    parser = argparse.ArgumentParser(description="Measure end-to-end query throughput")
    parser.add_argument("engines", nargs="+")
    parser.add_argument("--queries", default="queries.txt")
    parser.add_argument("--commands", nargs="+", default=["TOP_10"])
    parser.add_argument("--concurrency", nargs="+", type=int,
                        help="Explicit worker counts; omit for an automatic doubling sweep")
    parser.add_argument("--max-workers", type=int, default=64)
    parser.add_argument("--min-gain", type=float, default=0.05,
                        help="Minimum QPS gain over the prior best (default: 0.05 = 5%%)")
    length = parser.add_mutually_exclusive_group()
    length.add_argument("--duration", type=float,
                        help="Measured seconds per run (default: 60); drains in-flight requests")
    length.add_argument("--iterations", type=int,
                        help="Total passes over the query set per run, across all workers")
    parser.add_argument("--warmup", type=float, default=60,
                        help="Minimum warmup seconds per worker (at least one full pass)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", default="throughput-results.json")
    args = parser.parse_args()
    if args.iterations is None and args.duration is None:
        args.duration = 60
    queries = [q.query for q in read_queries(args.queries)]
    if not queries or (args.iterations is not None and args.iterations < 1) or args.repeats < 1:
        parser.error("Queries must be nonempty; iterations and repeats must be positive")
    if not math.isfinite(args.warmup) or args.warmup < 0:
        parser.error("Warmup must be finite and nonnegative")
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        parser.error("Duration must be finite and positive")
    if args.max_workers < 1 or not math.isfinite(args.min_gain) or args.min_gain <= 0:
        parser.error("Max workers and minimum gain must be positive")
    levels = args.concurrency if args.concurrency is not None else [args.max_workers]
    if any(c < 1 or (args.iterations is not None and c > len(queries) * args.iterations)
           for c in levels):
        parser.error("Concurrency must be positive and no greater than total queries")

    output = {"config": vars(args), "results": [], "sweeps": []}

    def save():
        with open(args.output, "w") as file:
            json.dump(output, file, indent=2)

    for command in args.commands:
        for engine in args.engines:
            def run_level(concurrency):
                runs = []
                for repeat in range(args.repeats):
                    print(f"{engine} {command} concurrency={concurrency} "
                          f"run={repeat + 1}/{args.repeats}", flush=True)
                    run = measure(engine, command, queries, concurrency,
                                  args.iterations, args.warmup, args.duration)
                    runs.append(run)
                    latency = run["latency_us"]
                    print(f"  {run['qps']:.2f} QPS; "
                          f"p50/p95/p99: {latency['p50']:.0f}/"
                          f"{latency['p95']:.0f}/{latency['p99']:.0f} us", flush=True)
                median_qps = statistics.median(run["qps"] for run in runs)
                output["results"].append({
                    "engine": engine, "command": command,
                    "concurrency": concurrency, "median_qps": median_qps, "runs": runs,
                })
                print(f"  Median: {median_qps:.2f} QPS", flush=True)
                save()
                return median_qps

            if args.concurrency is not None:
                for concurrency in args.concurrency:
                    run_level(concurrency)
            else:
                summary = sweep(run_level, args.max_workers, args.min_gain)
                output["sweeps"].append({"engine": engine, "command": command, **summary})
                save()
                print(f"Best measured: {summary['best_median_qps']:.2f} QPS at "
                      f"{summary['best_concurrency']} workers ({summary['stop_reason']})", flush=True)


if __name__ == "__main__":
    main()
