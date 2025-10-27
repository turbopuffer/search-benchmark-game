import os
from pathlib import Path

build_dir = Path("build")
results = [d for d in build_dir.iterdir() if d.is_dir()]
results.sort(reverse=True)

html = "<html>\n<head>\n<title>turbopuffer Search Benchmark Results</title>\n</head>\n"
html += '<body style="font-family: monospace">\n<h1>turbopuffer Search Benchmark Results</h1>\n<ul>\n'

for result in results:
    result_name = result.name
    html += f'  <li><a href="{result_name}/">{result_name}</a></li>\n'

html += "</ul>\n</body>\n</html>"

(build_dir / "index.html").write_text(html)
