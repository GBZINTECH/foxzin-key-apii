from __future__ import annotations
import os, secrets, threading
from datetime import datetime, timezone
from collections import deque
from flask import Flask, jsonify, request, abort
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
API_SECRET = os.getenv('API_SECRET', '').strip()
POLL_SECRET = os.getenv('POLL_SECRET', '').strip()
lock = threading.Lock()
commands = deque(maxlen=1000)

@app.get('/')
def health():
    return jsonify({'ok': True, 'service': 'Foxzin Key API'})

def check_api_key():
    if not API_SECRET or not secrets.compare_digest(request.headers.get('X-API-Key', ''), API_SECRET):
        abort(401)

def check_poll_secret():
    # Optional shared secret. If set, Roblox must call /poll?token=YOUR_POLL_SECRET.
    if POLL_SECRET and not secrets.compare_digest(request.args.get('token', ''), POLL_SECRET):
        abort(401)

@app.post('/api/commands')
def create_command():
    check_api_key()
    data = request.get_json(silent=True) or {}
    key_type = str(data.get('type', '')).lower()
    if key_type not in {'daily', 'monthly', 'permanent'}:
        return jsonify({'ok': False, 'error': 'type deve ser daily, monthly ou permanent'}), 400
    item = {
        'id': secrets.token_hex(8),
        'type': key_type,
        'processed': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'requested_by': str(data.get('requested_by', 'unknown'))[:100],
        'discord_user_id': str(data.get('discord_user_id', ''))[:30],
    }
    with lock:
        commands.append(item)
    return jsonify({'ok': True, 'command': item}), 201

@app.get('/poll')
def poll_commands():
    check_poll_secret()
    with lock:
        pending = [dict(c) for c in commands if not c['processed']]
    # Compatible with the shape documented in the Roblox script comment.
    return jsonify({'commands': pending})

@app.post('/api/commands/<command_id>/processed')
def mark_processed(command_id):
    check_api_key()
    data = request.get_json(silent=True) or {}
    with lock:
        for item in commands:
            if item['id'] == command_id:
                item['processed'] = True
                if data.get('result') is not None:
                    item['result'] = str(data['result'])[:500]
                return jsonify({'ok': True, 'command': dict(item)})
    return jsonify({'ok': False, 'error': 'comando não encontrado'}), 404

@app.get('/api/status')
def status():
    check_api_key()
    with lock:
        return jsonify({'ok': True, 'pending': sum(not c['processed'] for c in commands), 'total': len(commands)})

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8080'))
    app.run(host='0.0.0.0', port=port)
