import React from 'react';
import { fireEvent, render, within } from '@testing-library/react';
import $ from 'jquery';
import Throughput from './Throughput';

jest.mock('jquery', () => ({ getJSON: jest.fn() }));

test('shows best QPS and uneven sweeps, and switches operations', () => {
  const data = { results: [
    { engine: 'tantivy', command: 'TOP_10', concurrency: 1, median_qps: 100 },
    { engine: 'tantivy', command: 'TOP_10', concurrency: 2, median_qps: 200 },
    { engine: 'lucene', command: 'TOP_10', concurrency: 1, median_qps: 150 },
    { engine: 'tantivy', command: 'COUNT', concurrency: 4, median_qps: 300 },
  ] };
  $.getJSON.mockImplementation((url, done) => {
    done(data);
    return { abort: jest.fn() };
  });
  const view = render(<Throughput />);
  expect($.getJSON.mock.calls[0][0]).toMatch(/\/throughput-results.json$/);
  let tables = view.getAllByRole('table');
  const bestRow = within(tables[0]).getByText('tantivy').closest('tr');
  expect(within(bestRow).getByText('200')).toBeTruthy();
  expect(within(bestRow).getByText('2')).toBeTruthy();
  expect(within(tables[1]).getByText('—')).toBeTruthy();

  fireEvent.change(view.getByLabelText('Throughput operation'), { target: { value: 'COUNT' } });
  tables = view.getAllByRole('table');
  expect(within(tables[0]).getByText('300')).toBeTruthy();
  expect(within(tables[0]).getByText('4')).toBeTruthy();
  expect(view.queryByText('lucene')).toBeNull();
});

test('legacy reports without a throughput file remain empty', () => {
  const abort = jest.fn();
  // A missing JSON file never invokes the success callback.
  $.getJSON.mockImplementation(() => ({ abort }));
  const view = render(<Throughput />);
  expect(view.container.textContent).toBe('');
  view.unmount();
  expect(abort).toHaveBeenCalledTimes(1);
});

test('an empty throughput result remains empty', () => {
  $.getJSON.mockImplementation((url, done) => {
    done({ results: [] });
    return { abort: jest.fn() };
  });
  expect(render(<Throughput />).container.textContent).toBe('');
});
