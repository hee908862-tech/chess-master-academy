"""Anonymous browser identities reuse normal grading and isolated progress namespaces.

Linking is additive: never copy guest state over an account's current sessions.
"""
import hashlib
import secrets
import threading
import time
from collections import OrderedDict, deque
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

PREFIX = '~guest:'  # Cannot be entered as a normal account code.

class Limiter:
    def __init__(self):
        self.rows = OrderedDict()
        self.lock = threading.Lock()

    def take(self, key, count, window):
        with self.lock:
            now = time.monotonic()
            row = self.rows.setdefault(key, deque())
            while row and row[0] <= now-window:
                row.popleft()
            if len(row) >= count:
                raise HTTPException(429, '요청이 많습니다. 잠시 후 저장 상태를 확인해 주세요.', headers={'Retry-After':str(window)})
            row.append(now)
            self.rows.move_to_end(key)
            while len(self.rows) > 8192:
                self.rows.popitem(last=False)

LIMITER = Limiter()

def guest_limit(code):
    if code.startswith(PREFIX):
        LIMITER.take(('activity', code), 180, 60)

class Link(BaseModel):
    guest_token: str = Field(min_length=20, max_length=200)

class Resume(BaseModel):
    id: str = Field(max_length=100)

def attach_guests(app, ns):
    db, execute, auth = ns['db'], ns['execute'], ns['auth']
    with db() as conn:
        execute(conn, 'CREATE TABLE IF NOT EXISTS guest_links (guest_code TEXT PRIMARY KEY, owner_code TEXT NOT NULL, linked_at INTEGER NOT NULL)')

    @app.post('/api/guest/start')
    def start(request: Request):
        # Do not trust arbitrary forwarded headers. Deployment proxy may aggregate
        # addresses, making this deliberately conservative, never an auth bypass.
        address = hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
        LIMITER.take(('create', address), 10, 3600)
        LIMITER.take(('global-create',), 300, 3600)
        code = PREFIX + secrets.token_hex(20)
        ns['save_state'](code, ns['blank_state']())
        return {**ns['issue_token'](code), 'guest':True,
                'storage':'브라우저에는 접속 키, 서버에는 이 키로 구분되는 진행·기록을 저장합니다. 브라우저 데이터 삭제·시크릿 창 종료 시 로그인 계정에 연결하지 않은 기록은 다시 열 수 없습니다.'}

    @app.get('/api/guest/links')
    def links(authorization: str | None = Header(default=None)):
        code = auth(authorization)
        if code.startswith(PREFIX):
            return {'guest':True, 'items':[]}
        with db() as conn:
            rows = execute(conn, 'SELECT guest_code,linked_at FROM guest_links WHERE owner_code=? ORDER BY linked_at', (code,)).fetchall()
        return {'guest':False, 'items':[{'id':r['guest_code'], 'linked_at':r['linked_at'], 'label':'별도 보관된 브라우저 학습 기록'} for r in rows]}

    @app.post('/api/guest/link')
    def link(body: Link, authorization: str | None = Header(default=None)):
        owner = auth(authorization)
        if owner.startswith(PREFIX):
            raise HTTPException(403, '로그인 계정에서 기록을 연결하세요.')
        guest = auth('Bearer '+body.guest_token)
        if not guest.startswith(PREFIX):
            raise HTTPException(400, '게스트 기록만 연결할 수 있습니다.')
        with db() as conn:
            execute(conn, 'INSERT INTO guest_links(guest_code,owner_code,linked_at) VALUES(?,?,?) ON CONFLICT(guest_code) DO NOTHING', (guest,owner,int(time.time())))
            row = execute(conn, 'SELECT owner_code FROM guest_links WHERE guest_code=?', (guest,)).fetchone()
            if row['owner_code'] != owner:
                raise HTTPException(409, '이미 다른 계정에 연결된 기록입니다. 기존 연결은 변경하지 않았습니다.')
        return {'linked':True, 'id':guest, 'message':'별도 기록으로 연결했습니다. 기존 계정의 진행·점수와 합산하거나 덮어쓰지 않았습니다.'}

    @app.post('/api/guest/resume')
    def resume(body: Resume, authorization: str | None = Header(default=None)):
        owner = auth(authorization)
        with db() as conn:
            row = execute(conn, 'SELECT guest_code FROM guest_links WHERE owner_code=? AND guest_code=?', (owner,body.id)).fetchone()
        if not row:
            raise HTTPException(404, '연결된 기록을 찾을 수 없습니다.')
        return {**ns['issue_token'](row['guest_code']), 'guest':True}
