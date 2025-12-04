import sys
sys.path.insert(0, '.')

import json
import os

sessions_dir = 'sessions'
for filename in os.listdir(sessions_dir):
    if filename.endswith('.json'):
        with open(os.path.join(sessions_dir, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)
        session_name = data.get('session_name', 'KEIN NAME')
        role = data.get('role', 'keine Rolle')
        print(f"Datei: {filename}")
        print(f"  session_name: {session_name}")
        print(f"  role: {role}")
        print()
