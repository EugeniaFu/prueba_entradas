import os
import re

templates_dir = 'templates'

for root, dirs, files in os.walk(templates_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                blocks = len(re.findall(r'\{%\s*block\s+', content))
                endblocks = len(re.findall(r'\{%\s*endblock\s*%\}', content))
                if blocks != endblocks:
                    print(f'{filepath}: {blocks} blocks, {endblocks} endblocks')
