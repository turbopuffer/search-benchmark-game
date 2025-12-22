import numpy as np
from scipy import stats

TPUF = "turbopuffer"
GREEN = '\033[92m'
RED = '\033[91m'
COLOR_END = '\033[0m'

def print_diff(baseline, contender):
  first = True
  for collection_type in baseline:
    if collection_type not in contender:
      continue
    if first:
      first = False
    else:
      print("")
    print(f"\033[1m{collection_type}\033[0m")
    print("                                            Query \\ Latency (μs)     Baseline avg  Baseline stddev    Contender avg Contender stddev            Change          p-value")    
    print_diff_engine(baseline[collection_type][TPUF], contender[collection_type][TPUF])

def print_diff_engine(baseline, contender):
  baseline_query_to_latencies = {}
  for query in baseline:
    baseline_query_to_latencies[query["query"]] = query["duration"]

  for query in contender:
    query_str = query["query"]
    if query_str not in baseline_query_to_latencies:
      print("[WARN] Query [%s] not found in baseline results\n" %query_str)

    baseline_durations = np.array(baseline_query_to_latencies[query_str])
    contender_durations = np.array(query["duration"])

    if len(query_str) > 64:
      query_str = query_str[:63] + "…"

    baseline_mean = np.mean(baseline_durations)
    baseline_stddev = np.std(baseline_durations, ddof=1)
    contender_mean = np.mean(contender_durations)
    contender_stddev = np.std(contender_durations, ddof=1)
    change = 100 * (contender_mean - baseline_mean) / baseline_mean
    p_value = stats.ttest_ind(baseline_durations, contender_durations, equal_var=True)[1]
    print(f"{query_str:>64} {baseline_mean:16.2f} {baseline_stddev:16.2f} {contender_mean:16.2f} {contender_stddev:16.2f} {GREEN if change <= 0 else RED}{change:16.2f}%{COLOR_END} {p_value:16.2f}")


if __name__ == '__main__':
  import json, sys

  if len(sys.argv) != 3:
    print("Usage: %s results1.json results2.json" %sys.argv[0])
    sys.exit(1)

  with open(sys.argv[1]) as baseline_file, open(sys.argv[2]) as contender_file:
    baseline = json.load(baseline_file)
    contender = json.load(contender_file)
    print_diff(baseline["results"], contender["results"])
