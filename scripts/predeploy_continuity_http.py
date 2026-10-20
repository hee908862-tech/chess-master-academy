"""Real HTTP + restart checks, opt-in named local 1CPU/512MiB container only."""
import json
import secrets
import subprocess
import time
import urllib.request

BASE = 'http://127.0.0.1:18080/api/'
CONTAINER = 'cma-predeploy-app'
info = json.loads(subprocess.check_output(['docker', 'inspect', CONTAINER], text=True))[0]
assert info['HostConfig']['Memory'] == 536870912
assert info['HostConfig']['NanoCpus'] == 1000000000
assert info['Config']['Image'] == 'cma-interactive:review'
assert any(e.startswith('DATABASE_URL=') and '@127.0.0.1:55432/cma_predeploy' in e for e in info['Config']['Env'])


def api(path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def restart():
    subprocess.run(['docker', 'restart', CONTAINER], check=True, stdout=subprocess.DEVNULL)
    for _ in range(120):
        try:
            api('health')
            return
        except OSError:
            time.sleep(.25)
    raise AssertionError('health after restart timed out')


code = 'CONTINUITYIMAGE-' + secrets.token_hex(4).upper()
token = api('register', {'code': code, 'pin': 'temporary-local-pin'})['token']
level = api('starting-level', {'choice': 'rules', 'revision': 0}, token)
for step, move in enumerate(['a1a4', 'a1a4', 'a1a8', 'g1f2']):
    level = api('starting-level/move', {'revision': level['revision'], 'step': step, 'move': move}, token)
    assert level['correct'] and level['rules_step'] == step + 1
entry = api('journey/start', {'mode': 'entry'}, token)
assert entry['version'] == 'journey-entry-v1' and 1 <= entry['total'] <= 6
assert entry['starting_conditions']['self_choice'] == 'rules'
assert entry['starting_conditions']['bands'] == [[600, 1000]]
a = api('learning/start', {'fresh': True}, token)
a = api('learning/action', {'session_id': a['session_id'], 'revision': a['revision'], 'action': 'hint'}, token)
b = api('learning/start', {'fresh': True, 'pause_session_id': a['session_id'], 'pause_revision': a['revision']}, token)
course_a = api('v9/course/start', {'theme': 'mateIn1', 'level': '입문'}, token)
course_saved = api('v9/session/course', token=token)
api('v9/course/start', {'theme': 'fork', 'level': '중급', 'replace_token': course_saved['replace_token']}, token)
restart()
assert api('starting-level', token=token)['rules_step'] == 4
assert api('journey', token=token)['active'] == entry
saved = api('learning/dashboard', token=token)
assert saved['active']['session_id'] == b['session_id'] and len(saved['paused']) == 1
restored = api('learning/resume', {'session_id': a['session_id'], 'active_id': b['session_id'], 'active_revision': b['revision']}, token)
assert restored['fen'] == a['fen'] and restored['hint_level'] == a['hint_level']
assert restored['revision'] > a['revision']
current_course = api('v9/session/course', token=token)
api('v9/course/resume/' + course_a['session_id'], {'theme': 'mateIn1', 'level': '입문', 'replace_token': current_course['replace_token']}, token)
restored_course = api('v9/session/course', token=token)
assert restored_course['fen'] == course_a['fen'] and restored_course['session_id'] != course_a['session_id']
assert api('me', token=token)['stats']['courses_completed'] == 0
assert api('learning/dashboard', token=token)['attempts'] == []
info = json.loads(subprocess.check_output(['docker', 'inspect', CONTAINER], text=True))[0]
peak = int(subprocess.check_output(['docker', 'exec', CONTAINER, 'cat', '/sys/fs/cgroup/memory.peak'], text=True))
print(json.dumps({'conditions': 'local image 1CPU/512MiB, PostgreSQL17, unique temporary account',
                  'image': info['Image'], 'rules_to_actual_entry': 'PASS', 'diagnosis_restart': 'PASS',
                  'learning_switch_help_restart_resume': 'PASS', 'course_restart_resume': 'PASS',
                  'no_completion_credit_created': 'PASS', 'oom_killed': info['State']['OOMKilled'],
                  'memory_peak_bytes': peak}, indent=2))
