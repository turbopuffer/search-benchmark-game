
# Welcome to Search Benchmark, the Game!

This repository is standardized benchmark for comparing the speed of various
aspects of search engine technologies.

The results are available [here](https://turbopuffer.github.io/search-benchmark-game/).

This benchmark is both
- **for users** to make it easy for users to compare different libraries
- **for library** developers to identify optimization opportunities by comparing
their implementation to other implementations.

Currently, the benchmark only includes Lucene and tantivy.
It is reasonably simple to add another engine.

You are free to communicate about the results of this benchmark **in
a reasonable manner**.
For instance, twisting this benchmark in marketing material to claim that your search engine is 31x faster than Lucene,
because your product was 31x on one of the test is not tolerated. If this happens, the benchmark will publicly
host a wall of shame.
Bullshit claims about performance are a plague in the database world.


## The benchmark

Different search engine implementation are benched over different real-life tests.
The corpus used is the English wikipedia. Stemming is disabled. Queries have been derived
 from the [AOL query dataset](https://en.wikipedia.org/wiki/AOL_search_data_leak)
 (but do not contain any personal information).

Out of a random sample of query, we filtered queries that had at least two terms and yield at least 1 hit when searches as
a phrase query.

For each of these query, we then run them as :
- `intersection`
- `unions`
- `phrase queries`

with the following collection options :
- `COUNT` only count documents, no need to score them
- `TOP 10` : Identify the 10 documents with the best BM25 score.
- `TOP 10 + COUNT`: Identify the 10  documents with the best BM25 score, and count the matching documents.

We also reintroduced artificially a couple of term queries with different term frequencies.

All tests are run once in order to make sure that
- all of the data is loaded and in page cache
- Java's JIT already kicked in.

Test are run in a single thread.
Out of 10 runs, we only retain the best score, so Garbage Collection likely does not matter.

### Benchmark environment

The results file that is included in this repository was generated using the following benchmark
environment:
 - AWS c7i.2xlarge instance running on us-east-1
 - Processor Intel(R) Xeon(R) Platinum 8488C
 - Amazon Linux 2023
 - Kernel `6.1.148-173.267.amzn2023.x86_64`
 - Rust 1.89
 - Adoptium JDK `Temurin-21.0.8+9`

## Engine specific detail

### Lucene

- Query cache is disabled.
- GC should not influence the results as we pick the best out of 5 runs.
- The `-bp` variant implements document reordering via the bipartite graph partitioning algorithm, also called recursive graph bisection.

### Tantivy

- Tantivy returns slightly more results because its tokenizer handles apostrophes differently.
- Tantivy and Lucene both use BM25 and should return almost identical scores.


# Reproducing

These instructions will get you a copy of the project up and running on your local machine.

### Prerequisites

The lucene benchmarks requires Java, the most recent version is recommended.
The tantivy benchmarks and benchmark driver code requires Cargo. This can be installed using [rustup](https://www.rustup.rs/).

### Installing

Clone this repo.

```
git clone git@github.com:turbopuffer/search-benchmark-game.git
```

## Running

Checkout the [Makefile](Makefile) for all available commands. You can adjust the `ENGINES` parameter for a different set of engines.

Run `make corpus` to download and unzip the corpus used in the benchmark.
```
make corpus
```

Run `make index` to create the indices for the engines.

```
make index
```

Run `make bench` to build the different project and run the benches.
This command may take more than 30mn.

```
make bench
```

The results are outputted in a `results.json` file.

You can then check your results out by running:

```
make serve
```

And open the following in your browser: [http://localhost:8000/](http://localhost:8000/)


# Adding another search engine

See `CONTRIBUTE.md`.

## Measuring throughput

Build the engines and their indices first (`make compile` and `make index`).
The throughput runner uses Python threads, with one engine subprocess per worker:

```sh
python3 src/throughput.py tantivy-0.26 lucene-10.4.0 \
  --commands TOP_10 --max-workers 64 \
  --warmup 60 --duration 60 --repeats 3
```

Add `turbopuffer` to the engine list to measure the configured turbopuffer server;
its usual API key, namespace, and running-server setup are required.

The default sweep doubles workers from 1 up to `--max-workers` (default 64).
It stops early after two consecutive levels each improve median QPS by less
than `--min-gain` over the previous best (default 0.05, or 5%). It then tests
the integer midpoints between the best measured level and its tested neighbors.
The output records the best measured QPS and worker count, and whether the sweep
stopped at a plateau or the worker cap. This is a heuristic, not proof of a global
maximum. Use `--concurrency 1 2 4 8 16 32 64` to run explicit levels without early
stopping or refinement. The cap applies to automatic sweeps only.

Every worker warms up for at least the requested time and one full query pass.
Workers then start together. By default, each worker cycles through the full
seeded, shuffled query list, starting at a different offset, for `--duration`
seconds (default 60). At the deadline, workers stop submitting requests and
finish outstanding ones. The elapsed time includes this final drain. Every
worker traverses the same mix, but partial final passes can change the exact
query proportions between runs.

Alternatively, use `--iterations 30` instead of `--duration` for a fixed workload
of `30 * number of queries` requests divided across workers. This preserves the
exact query mix across levels, but higher concurrency can make runs very short,
and concurrency may fall near the end as workers finish at different times.

QPS is completed requests divided by wall time from the synchronized start to
the last response. Warmup, process startup, and cleanup are excluded. The runner
prints QPS and p50/p95/p99 request latency for each run and median QPS across
repeats. Results, including elapsed seconds, are saved to `throughput-results.json`
(override with `--output`). Unsupported commands and request failures abort the
run rather than counting as successful queries. Requests have no driver timeout.

These are end-to-end measurements, including Python and pipe overhead, plus HTTP
and response decoding for turbopuffer. Tantivy and Lucene use multiple processes
reading the same index, with separate process memory and shared OS page cache.
The turbopuffer subprocesses all query the same server. Keep engine hardware
resources fixed and report the process count when comparing results. This is a
closed-loop workload: each worker sends its next request after receiving a
response, rather than submitting at a fixed arrival rate.

Run the driver tests with `python3 -m unittest discover -s src -p 'test_*.py'`.
