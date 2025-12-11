#!/usr/bin/env python3
# Note: this file is 99% vibe-coded
"""
Script to extract latency data from results.json files and generate an HTML page
with latency over time plots for each query.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Annotations mapping directory names to annotation strings or dicts with optional PR numbers
# These will be displayed as vertical lines with labels on all charts
# Format examples:
#   Simple string: '2025-11-18T10-39-24': 'Deployment v1.2.3'
#   With PR link: '2025-11-20T13-01-23': {'text': 'Performance optimization', 'pr': 123}
ANNOTATIONS = {
    '2025-11-22T11-01-12': { 'text': 'Made block postings generic over weight', 'pr': 5995 },
    '2025-11-23T11-42-28': { 'text': 'Inlined decoding of weights', 'pr': 6043 },
}


def parse_date_from_dirname(dirname):
    """Parse date from directory name like '2025-11-30T10-52-49'."""
    try:
        return datetime.strptime(dirname, '%Y-%m-%dT%H-%M-%S')
    except ValueError:
        return None


def extract_min_latency(results_data, result_type='TOP_10'):
    """
    Extract minimum latency for each query from results.json structure.
    Returns a dict mapping query -> min_latency.
    """
    query_latencies = {}
    
    # Navigate to results.{result_type}.turbopuffer
    results = results_data.get('results', {})
    result_data = results.get(result_type, {})
    turbopuffer_data = result_data.get('turbopuffer', [])
    
    # For each query result, extract query and minimum duration
    for query_result in turbopuffer_data:
        query = query_result.get('query')
        durations = query_result.get('duration', [])
        
        if query and durations:
            min_latency = min(durations)
            query_latencies[query] = min_latency
    
    return query_latencies


def get_available_result_types(build_dir='build'):
    """
    Get all available result types from the latest results.json file.
    Returns a list of result type names.
    """
    build_path = Path(build_dir)
    if not build_path.exists():
        return []
    
    # Find all date directories with their dates
    date_dirs = []
    for subdir in build_path.iterdir():
        if not subdir.is_dir():
            continue
        date = parse_date_from_dirname(subdir.name)
        if date is not None:
            results_file = subdir / 'results.json'
            if results_file.exists():
                date_dirs.append((date, results_file))
    
    if not date_dirs:
        return []
    
    # Get the latest file
    latest_date, latest_file = max(date_dirs, key=lambda x: x[0])
    
    try:
        with open(latest_file, 'r') as f:
            results_data = json.load(f)
        
        results = results_data.get('results', {})
        return sorted(results.keys())
    except Exception as e:
        print(f"Warning: Error reading latest file {latest_file}: {e}")
        return []


def get_latest_comparison_index_path(build_dir='build'):
    """
    Get the path to the index.html file in the latest date directory.
    Returns a Path object or None if not found.
    """
    build_path = Path(build_dir)
    if not build_path.exists():
        return None
    
    # Find all date directories with their dates that have index.html
    date_dirs = []
    for subdir in build_path.iterdir():
        if not subdir.is_dir():
            continue
        date = parse_date_from_dirname(subdir.name)
        if date is not None:
            index_file = subdir / 'index.html'
            if index_file.exists():
                date_dirs.append((date, index_file))
    
    if not date_dirs:
        return None
    
    # Get the latest file
    latest_date, latest_index_file = max(date_dirs, key=lambda x: x[0])
    return latest_index_file


def get_query_order_from_latest(build_dir='build', result_type='TOP_10'):
    """
    Get the query order from the latest results.json file.
    Returns a list of queries in the order they appear.
    """
    build_path = Path(build_dir)
    if not build_path.exists():
        return []
    
    # Find all date directories with their dates
    date_dirs = []
    for subdir in build_path.iterdir():
        if not subdir.is_dir():
            continue
        date = parse_date_from_dirname(subdir.name)
        if date is not None:
            results_file = subdir / 'results.json'
            if results_file.exists():
                date_dirs.append((date, results_file))
    
    if not date_dirs:
        return []
    
    # Get the latest file
    latest_date, latest_file = max(date_dirs, key=lambda x: x[0])
    
    try:
        with open(latest_file, 'r') as f:
            results_data = json.load(f)
        
        # Extract query order from results.{result_type}.turbopuffer
        results = results_data.get('results', {})
        result_data = results.get(result_type, {})
        turbopuffer_data = result_data.get('turbopuffer', [])
        
        # Return queries in the order they appear
        query_order = []
        for query_result in turbopuffer_data:
            query = query_result.get('query')
            if query:
                query_order.append(query)
        
        return query_order
    except Exception as e:
        print(f"Warning: Error reading latest file {latest_file}: {e}")
        return []


def collect_data_from_build_dir(build_dir='build', annotations=None, result_types=None):
    """
    Collect latency data from all results.json files in build directory.
    Returns a tuple: (dict mapping result_type -> dict mapping query -> list of (date, latency) tuples, 
                     query_order list, annotations_dict, available_result_types).
    """
    if annotations is None:
        annotations = {}
    
    build_path = Path(build_dir)
    if not build_path.exists():
        raise FileNotFoundError(f"Build directory '{build_dir}' not found")
    
    # Get available result types if not provided
    if result_types is None:
        result_types = get_available_result_types(build_dir)
        if not result_types:
            result_types = ['TOP_10']  # Fallback
    
    # Dictionary mapping result_type -> dict mapping query -> list of (date, latency) tuples
    all_query_data = {rt: defaultdict(list) for rt in result_types}
    # Dictionary mapping date (as ISO string) -> dict with 'text' and optionally 'pr'
    date_annotations = {}
    
    # Iterate through all subdirectories
    for subdir in sorted(build_path.iterdir()):
        if not subdir.is_dir():
            continue
        
        # Skip if not a date directory
        date = parse_date_from_dirname(subdir.name)
        if date is None:
            continue
        
        # Check for annotation for this directory
        if subdir.name in annotations:
            annotation_value = annotations[subdir.name]
            # Handle both string and dict formats
            if isinstance(annotation_value, str):
                date_annotations[date.isoformat()] = {'text': annotation_value}
            elif isinstance(annotation_value, dict):
                date_annotations[date.isoformat()] = annotation_value
            else:
                # Fallback: convert to string
                date_annotations[date.isoformat()] = {'text': str(annotation_value)}
        
        # Check for results.json
        results_file = subdir / 'results.json'
        if not results_file.exists():
            continue
        
        try:
            with open(results_file, 'r') as f:
                results_data = json.load(f)
            
            # Extract query latencies for each result type
            for result_type in result_types:
                query_latencies = extract_min_latency(results_data, result_type)
                
                # Add to our collection
                for query, latency in query_latencies.items():
                    all_query_data[result_type][query].append((date, latency))
        
        except Exception as e:
            print(f"Warning: Error processing {results_file}: {e}")
            continue
    
    # Sort each query's data by date for each result type
    for result_type in result_types:
        for query in all_query_data[result_type]:
            all_query_data[result_type][query].sort(key=lambda x: x[0])
    
    # Get query order from latest file (use first available result type)
    query_order = get_query_order_from_latest(build_dir, result_types[0] if result_types else 'TOP_10')
    
    return all_query_data, query_order, date_annotations, result_types


def generate_html(all_query_data, query_order, date_annotations, result_types, output_file='build/index.html', build_dir='build'):
    """Generate an HTML page with charts for each query."""
    
    # Get the latest comparison index.html path for linking
    latest_comparison_index = get_latest_comparison_index_path(build_dir)
    latest_comparison_link = None
    if latest_comparison_index:
        # Make path relative to output file location
        output_path = Path(output_file)
        try:
            latest_comparison_link = latest_comparison_index.relative_to(output_path.parent)
        except ValueError:
            # If paths are not relative, use absolute path
            latest_comparison_link = latest_comparison_index
    
    # Use TOP_10 as default if available, otherwise use first result type
    default_result_type = 'TOP_10' if 'TOP_10' in result_types else result_types[0] if result_types else 'TOP_10'
    
    # Prepare data for Chart.js for all result types
    all_chart_data = {}
    for result_type in result_types:
        chart_data = {}
        query_data = all_query_data[result_type]
        for query, data_points in query_data.items():
            dates = [dp[0].isoformat() for dp in data_points]
            latencies = [dp[1] for dp in data_points]
            chart_data[query] = {
                'dates': dates,
                'latencies': latencies
            }
        all_chart_data[result_type] = chart_data
    
    # Use default result type for initial display
    chart_data = all_chart_data[default_result_type]
    
    # Determine the order to display queries
    # Use query_order if available, otherwise fall back to sorted order
    if query_order:
        # Filter to only queries that exist in chart_data, preserving order
        ordered_queries = [q for q in query_order if q in chart_data]
        # Add any queries not in the order list at the end
        remaining_queries = sorted(set(chart_data.keys()) - set(ordered_queries))
        display_order = ordered_queries + remaining_queries
    else:
        display_order = sorted(chart_data.keys())
    
    # Generate HTML
    latest_link_html = ''
    if latest_comparison_link:
        latest_link_html = f'        <p style="margin-bottom: 20px;"><a href="{latest_comparison_link}" style="color: #007bff; text-decoration: none; font-size: 14px;">See most recent comparison against Lucene and Tantivy</a></p>\n'
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Query Latency Over Time</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: #333;
            margin-bottom: 30px;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart-title {{
            font-size: 18px;
            font-weight: 600;
            color: #555;
            margin-bottom: 15px;
        }}
        .chart-wrapper {{
            position: relative;
            height: 400px;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 15px;
            font-size: 14px;
            color: #666;
        }}
        .stat-item {{
            padding: 8px 12px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .stat-label {{
            font-weight: 600;
            margin-right: 5px;
        }}
        .result-type-selector {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .result-type-selector label {{
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
            cursor: pointer;
            font-size: 14px;
        }}
        .result-type-selector input[type="radio"] {{
            margin-right: 8px;
            cursor: pointer;
        }}
        .result-type-selector h2 {{
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 16px;
            color: #555;
        }}
        .zoom-controls {{
            margin-top: 10px;
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .zoom-button {{
            padding: 6px 12px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
        }}
        .zoom-button:hover {{
            background: #0056b3;
        }}
        .zoom-button:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .zoom-info {{
            font-size: 12px;
            color: #666;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>turbopuffer text search nightly benchmarks</h1>
{latest_link_html}        <div class="result-type-selector">
            <h2>Result Type:</h2>
"""
    
    # Add radio buttons for each result type
    for result_type in result_types:
        checked = 'checked' if result_type == default_result_type else ''
        html_content += f'            <label><input type="radio" name="resultType" value="{result_type}" {checked}> {result_type}</label>\n'
    
    html_content += """        </div>
"""
    
    # Add JavaScript to store all chart data
    all_chart_data_json = json.dumps(all_chart_data)
    result_types_json = json.dumps(result_types)
    default_result_type_json = json.dumps(default_result_type)
    date_annotations_json = json.dumps(date_annotations)
    
    html_content += f"""
    <script>
        // Register zoom plugin when Chart.js is ready
        if (typeof Chart !== 'undefined') {{
            // The zoom plugin from CDN should auto-register, but we'll ensure it's available
            Chart.defaults.set('plugins.zoom', {{
                pan: {{
                    enabled: true,
                    mode: 'x'
                }},
                zoom: {{
                    wheel: {{
                        enabled: true
                    }},
                    pinch: {{
                        enabled: true
                    }},
                    drag: {{
                        enabled: true,
                        modifierKey: null
                    }},
                    mode: 'x'
                }}
            }});
        }}
        
        // Store all chart data for all result types
        const allChartData = {all_chart_data_json};
        const resultTypes = {result_types_json};
        const defaultResultType = {default_result_type_json};
        const dateAnnotations = {date_annotations_json};
        const chartInstances = {{}};
        
        // Handle radio button changes
        document.querySelectorAll('input[name="resultType"]').forEach(radio => {{
            radio.addEventListener('change', function() {{
                if (this.checked) {{
                    const selectedType = this.value;
                    updateCharts(selectedType);
                }}
            }});
        }});
        
        function updateCharts(resultType) {{
            const chartData = allChartData[resultType];
            if (!chartData) return;
            
            // Update each chart
            Object.keys(chartInstances).forEach(chartId => {{
                const instance = chartInstances[chartId];
                if (!instance) return;
                
                const query = instance.config.data.datasets[0]._query;
                if (chartData[query]) {{
                    const data = chartData[query];
                    instance.data.labels = data.dates;
                    instance.data.datasets[0].data = data.latencies;
                    
                    // Update annotations based on new dates
                    const newAnnotations = [];
                    data.dates.forEach((dateStr, idx) => {{
                        if (dateAnnotations[dateStr]) {{
                            const annInfo = dateAnnotations[dateStr];
                            newAnnotations.push({{
                                x: idx,
                                text: annInfo.text || '',
                                pr: annInfo.pr
                            }});
                        }}
                    }});
                    
                    // Update annotation plugin configuration
                    if (instance.options.plugins && instance.options.plugins.annotation) {{
                        const annotationConfig = {{
                            annotations: {{}}
                        }};
                        
                        newAnnotations.forEach((ann, idx) => {{
                            const annotationKey = `annotation_${{idx}}`;
                            const isEven = idx % 2 === 0;
                            const position = isEven ? 'start' : 'end';
                            const baseOffset = isEven ? -6 : 6;
                            const staggerOffset = (idx % 4 < 2) ? 0 : (isEven ? -12 : 12);
                            const yAdjust = baseOffset + staggerOffset;
                            
                            let labelText = ann.text;
                            if (ann.pr) {{
                                labelText += ' #' + ann.pr;
                            }}
                            
                            annotationConfig.annotations[annotationKey] = {{
                                type: 'line',
                                xMin: ann.x,
                                xMax: ann.x,
                                borderColor: 'rgb(255, 99, 132)',
                                borderWidth: 2,
                                borderDash: [5, 5],
                                label: {{
                                    display: true,
                                    content: labelText,
                                    position: position,
                                    backgroundColor: ann.pr ? 'rgba(255, 99, 132, 0.9)' : 'rgba(255, 99, 132, 0.8)',
                                    color: 'white',
                                    font: {{
                                        size: 10,
                                        weight: 'bold'
                                    }},
                                    padding: {{
                                        top: 2,
                                        bottom: 2,
                                        left: 4,
                                        right: 4
                                    }},
                                    xAdjust: 0,
                                    yAdjust: yAdjust
                                }}
                            }};
                        }});
                        
                        instance.options.plugins.annotation = annotationConfig;
                    }}
                    
                    instance.update('none'); // Update without animation
                }}
            }});
        }}
    </script>
"""
    
    # Add a chart for each query in the determined order
    for query in display_order:
        data = chart_data[query]
        dates_json = json.dumps(data['dates'])
        latencies_json = json.dumps(data['latencies'])
        
        # Find annotations that match dates in this chart
        chart_annotations = []
        for i, date_str in enumerate(data['dates']):
            if date_str in date_annotations:
                ann_info = date_annotations[date_str]
                chart_annotations.append({
                    'x': i,  # Index in the dates array
                    'text': ann_info.get('text', ''),
                    'pr': ann_info.get('pr')
                })
        
        annotations_json = json.dumps(chart_annotations)
        
        # Calculate statistics
        latencies = data['latencies']
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        chart_id = f"chart_{hash(query) % 1000000}"
        
        html_content += f"""
        <div class="chart-container">
            <div class="chart-title">Query: "{query}"</div>
            <div class="chart-wrapper">
                <canvas id="{chart_id}"></canvas>
            </div>
            <div class="stats">
                <div class="stat-item">
                    <span class="stat-label">Min:</span>
                    <span>{min_latency:.2f} ms</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Max:</span>
                    <span>{max_latency:.2f} ms</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Avg:</span>
                    <span>{avg_latency:.2f} ms</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Data Points:</span>
                    <span>{len(latencies)}</span>
                </div>
            </div>
        </div>
        
        <script>
            (function() {{
                const ctx = document.getElementById('{chart_id}').getContext('2d');
                const dates = {dates_json};
                const latencies = {latencies_json};
                const annotations = {annotations_json};
                
                // Build annotation configuration
                const annotationConfig = {{
                    annotations: {{}}
                }};
                
                // Add vertical line annotations for each annotated date
                // Use staggered vertical positions to prevent overlap
                annotations.forEach((ann, idx) => {{
                    const annotationKey = `annotation_${{idx}}`;
                    // Build compact label text with optional PR link indicator
                    let labelText = ann.text;
                    if (ann.pr) {{
                        labelText += ' #' + ann.pr;
                    }}
                    
                    // Stagger labels vertically: alternate between top and bottom, with slight offsets
                    const isEven = idx % 2 === 0;
                    const position = isEven ? 'start' : 'end';
                    // Use different yAdjust values to create staggered effect
                    const baseOffset = isEven ? -6 : 6;
                    const staggerOffset = (idx % 4 < 2) ? 0 : (isEven ? -12 : 12);
                    const yAdjust = baseOffset + staggerOffset;
                    
                    annotationConfig.annotations[annotationKey] = {{
                        type: 'line',
                        xMin: ann.x,
                        xMax: ann.x,
                        borderColor: 'rgb(255, 99, 132)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        label: {{
                            display: true,
                            content: labelText,
                            position: position,
                            backgroundColor: ann.pr ? 'rgba(255, 99, 132, 0.9)' : 'rgba(255, 99, 132, 0.8)',
                            color: 'white',
                            font: {{
                                size: 10,
                                weight: 'bold'
                            }},
                            padding: {{
                                top: 2,
                                bottom: 2,
                                left: 4,
                                right: 4
                            }},
                            xAdjust: 0,
                            yAdjust: yAdjust,
                            // Store PR number for click handler
                            _pr: ann.pr
                        }},
                        // Store annotation index and PR for click handling
                        _annIndex: idx,
                        _pr: ann.pr
                    }};
                }});
                
                // Store chart reference for click handling
                let chartInstance = null;
                
                chartInstance = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: dates,
                        datasets: [{{
                            label: 'Latency (ms)',
                            data: latencies,
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            tension: 0.1,
                            pointRadius: 3,
                            pointHoverRadius: 5,
                            _query: {json.dumps(query)}
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'top'
                            }},
                            tooltip: {{
                                mode: 'index',
                                intersect: false,
                                callbacks: {{
                                    title: function(context) {{
                                        const dateLabel = context[0].label;
                                        const annotation = annotations.find(a => dates[a.x] === dateLabel);
                                        if (annotation) {{
                                            let tooltipText = 'Date: ' + dateLabel + ' [' + annotation.text + ']';
                                            if (annotation.pr) {{
                                                tooltipText += ' (PR #' + annotation.pr + ')';
                                            }}
                                            return tooltipText;
                                        }}
                                        return 'Date: ' + dateLabel;
                                    }},
                                    label: function(context) {{
                                        return 'Latency: ' + context.parsed.y.toFixed(2) + ' ms';
                                    }}
                                }}
                            }},
                            annotation: annotationConfig,
                            zoom: {{
                                pan: {{
                                    enabled: true,
                                    mode: 'x',
                                    modifierKey: null
                                }},
                                zoom: {{
                                    wheel: {{
                                        enabled: false
                                    }},
                                    pinch: {{
                                        enabled: false
                                    }},
                                    drag: {{
                                        enabled: true,
                                        modifierKey: null,
                                        backgroundColor: 'rgba(225, 225, 225, 0.3)',
                                        borderColor: 'rgba(225, 225, 225, 0.8)',
                                        borderWidth: 1
                                    }},
                                    mode: 'x'
                                }},
                                limits: {{
                                    x: {{min: 'original', max: 'original'}},
                                    y: {{min: 'original', max: 'original'}}
                                }}
                            }}
                        }},
                        onClick: function(event, elements) {{
                            // Check if click is near an annotation
                            if (!chartInstance) return;
                            
                            const canvasPosition = Chart.helpers.getRelativePosition(event, chartInstance);
                            const xScale = chartInstance.scales.x;
                            const xValue = xScale.getValueForPixel(canvasPosition.x);
                            
                            // Find closest annotation
                            let closestAnn = null;
                            let minDist = Infinity;
                            annotations.forEach(ann => {{
                                const dist = Math.abs(ann.x - xValue);
                                if (dist < minDist && dist < 0.5) {{
                                    minDist = dist;
                                    closestAnn = ann;
                                }}
                            }});
                            
                            // If clicked on annotation with PR, open PR link
                            if (closestAnn && closestAnn.pr) {{
                                window.open('https://github.com/turbopuffer/turbopuffer/pull/' + closestAnn.pr, '_blank');
                            }}
                        }},
                        scales: {{
                            x: {{
                                display: true,
                                title: {{
                                    display: true,
                                    text: 'Date'
                                }},
                                ticks: {{
                                    maxRotation: 45,
                                    minRotation: 45
                                }}
                            }},
                            y: {{
                                display: true,
                                title: {{
                                    display: true,
                                    text: 'Latency (ms)'
                                }},
                                beginAtZero: true
                            }}
                        }}
                    }}
                }});
                
                // Store chart instance for result type switching
                chartInstances['{chart_id}'] = chartInstance;
                
                // Enable zoom event handlers
                try {{
                    chartInstance.on('zoom', function() {{
                        const resetBtn = document.getElementById('resetZoom_{chart_id}');
                        if (resetBtn) {{
                            resetBtn.disabled = false;
                        }}
                    }});
                    
                    chartInstance.on('pan', function() {{
                        const resetBtn = document.getElementById('resetZoom_{chart_id}');
                        if (resetBtn) {{
                            resetBtn.disabled = false;
                        }}
                    }});
                }} catch(e) {{
                    // Zoom events might not be available, that's OK
                }}
                
                // Make canvas cursor pointer when hovering over annotations with PRs
                const canvas = document.getElementById('{chart_id}');
                canvas.addEventListener('mousemove', function(event) {{
                    const canvasPosition = Chart.helpers.getRelativePosition(event, chartInstance);
                    const xScale = chartInstance.scales.x;
                    const xValue = xScale.getValueForPixel(canvasPosition.x);
                    
                    // Check if mouse is near an annotation with PR
                    let nearAnnotationWithPR = false;
                    annotations.forEach(ann => {{
                        if (Math.abs(ann.x - xValue) < 0.5 && ann.pr) {{
                            nearAnnotationWithPR = true;
                        }}
                    }});
                    canvas.style.cursor = nearAnnotationWithPR ? 'pointer' : 'default';
                }});
            }})();
        </script>
"""
    
    # Add global reset zoom function
    html_content += """
    <script>
        function resetZoom(chartId) {
            const chartInstance = chartInstances[chartId];
            if (chartInstance && typeof chartInstance.resetZoom === 'function') {
                chartInstance.resetZoom();
                const resetBtn = document.getElementById('resetZoom_' + chartId);
                if (resetBtn) {
                    resetBtn.disabled = true;
                }
            }
        }
    </script>
"""
    
    html_content += """
    </div>
</body>
</html>
"""
    
    # Ensure build directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"HTML page generated: {output_file}")


def main():
    """Main function."""
    print("Collecting data from build directory...")
    all_query_data, query_order, date_annotations, result_types = collect_data_from_build_dir(annotations=ANNOTATIONS)
    
    if not all_query_data or not any(all_query_data.values()):
        print("No data found. Make sure results.json files exist in build subdirectories.")
        return
    
    print(f"Found {len(result_types)} result types: {', '.join(result_types)}")
    default_result_type = 'TOP_10' if 'TOP_10' in result_types else result_types[0] if result_types else 'TOP_10'
    query_data = all_query_data[default_result_type]
    
    print(f"Found data for {len(query_data)} queries (showing {default_result_type})")
    if query_order:
        print(f"Using query order from latest results.json ({len(query_order)} queries)")
    if date_annotations:
        print(f"Found {len(date_annotations)} annotations")
    for query, data_points in query_data.items():
        print(f"  - {query}: {len(data_points)} data points")
    
    print("\nGenerating HTML page...")
    generate_html(all_query_data, query_order, date_annotations, result_types, build_dir='build')
    print("Done!")


if __name__ == '__main__':
    main()

