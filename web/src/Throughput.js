import React, { useEffect, useState } from 'react';
import $ from 'jquery';

export default function Throughput() {
  const [data, setData] = useState(null);
  const [mode, setMode] = useState(null);

  useEffect(() => {
    const request = $.getJSON(process.env.PUBLIC_URL + '/throughput-results.json', setData);
    return () => request.abort();
  }, []);

  // Older reports contain only latency results.
  if (data === null || data.results.length === 0) return null;

  const modes = Array.from(new Set(data.results.map(result => result.command)));
  const command = mode || modes[0];
  const results = data.results.filter(result => result.command === command);
  const engines = Array.from(new Set(results.map(result => result.engine)));
  const levels = Array.from(new Set(results.map(result => result.concurrency))).sort((a, b) => a - b);
  const best = engines.map(engine => results.filter(result => result.engine === engine)
    .sort((a, b) => b.median_qps - a.median_qps || a.concurrency - b.concurrency)[0]);
  const formatQps = qps => qps.toLocaleString('en-US', { maximumFractionDigits: 2 });

  return <section>
    <h2>Throughput</h2>
    <p>End-to-end queries per second over the full query mix. Higher is better.
      Each worker launches a separate adapter process: Lucene and Tantivy search in
      separate processes; turbopuffer adapters query the shared server.
      The query-type filter above applies only to latency results.</p>
    <label htmlFor="throughputOperation">Throughput operation</label>
    <select id="throughputOperation" value={command} onChange={event => setMode(event.target.value)}>
      {modes.map(value => <option key={value} value={value}>{value}</option>)}
    </select>
    <table>
      <caption>Best measured throughput</caption>
      <thead><tr><th>Engine</th><th>QPS</th><th>Workers</th></tr></thead>
      <tbody>{best.map(result => <tr key={result.engine}>
        <th scope="row">{result.engine}</th>
        <td>{formatQps(result.median_qps)}</td>
        <td>{result.concurrency}</td>
      </tr>)}</tbody>
    </table>
    <details>
      <summary>Throughput at each worker count</summary>
      <table>
        <thead><tr><th>Workers</th>{engines.map(engine => <th key={engine}>{engine} QPS</th>)}</tr></thead>
        <tbody>{levels.map(level => <tr key={level}>
          <th scope="row">{level}</th>
          {engines.map(engine => {
            const result = results.find(row => row.engine === engine && row.concurrency === level);
            return <td key={engine}>{result ? formatQps(result.median_qps) : '—'}</td>;
          })}
        </tr>)}</tbody>
      </table>
    </details>
    <p><a href="./throughput-results.json">Download throughput results</a></p>
  </section>;
}
