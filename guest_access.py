"""Anonymous browser identities reuse normal grading and isolated progress namespaces.

Linking is additive: never copy guest state over an account's current sessions.
"""
import hashlib
import secrets
import time
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

PREFIX = '~guest:'  # Cannot be entered as a normal account code.

SESSION_TTL = 30 * 24 * 3600

def token_hash(authorization):
    return hashlib.sha256((authorization or '').removeprefix('Bearer ').strip().encode()).hexdigest()

def shared_limit(ns, key, count, window):
    """Shared atomic fixed-window budget; never infer identity from proxy headers."""
    now = int(time.time()); bucket = now // window
    digest = hashlib.sha256(key.encode()).hexdigest()
    with ns['db']() as conn:
        row = ns['execute'](conn, 'INSERT INTO guest_budgets(key,bucket,hits,expires) VALUES(?,?,1,?) ON CONFLICT(key) DO UPDATE SET hits=CASE WHEN guest_budgets.bucket=? THEN guest_budgets.hits+1 ELSE 1 END,bucket=?,expires=? RETURNING hits',
            (digest,bucket,(bucket+1)*window,bucket,bucket,(bucket+1)*window)).fetchone()
        ns['execute'](conn, 'DELETE FROM guest_budgets WHERE expires<?', (now-window,))
        hits = row['hits']
    if hits > count:
        retry = (bucket+1)*window-now
        raise HTTPException(429, f'요청이 많습니다. {retry}초 후 다시 시도하세요. 기록은 보존됩니다.', headers={'Retry-After':str(retry)})

def validate_session(ns, conn, digest):
    row = ns['execute'](conn, 'SELECT code,created FROM sessions WHERE token_hash=?', (digest,)).fetchone()
    if not row or (not row['code'].startswith(PREFIX) and row['created'] <= int(time.time())-SESSION_TTL):
        raise HTTPException(401, '로그인이 만료됐습니다. 소유 계정으로 다시 로그인하세요.')
    if row['code'].startswith(PREFIX):
        link = ns['execute'](conn, 'SELECT owner_code FROM guest_links WHERE guest_code=?', (row['code'],)).fetchone()
        if link:
            parent = ns['execute'](conn, 'SELECT s.code,s.created FROM guest_delegations d JOIN sessions s ON s.token_hash=d.parent_hash WHERE d.token_hash=?', (digest,)).fetchone()
            if not parent or parent['code'] != link['owner_code'] or parent['created'] <= int(time.time())-SESSION_TTL:
                raise HTTPException(401, '계정에 연결된 기록입니다. 소유 계정으로 로그인한 뒤 이어하세요.')
    return row['code']

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
        # Shared capacity cap, not a per-IP identity: Render may pool client addresses.
        # Forwarded headers are deliberately ignored.
        shared_limit(ns, 'guest-create-global', 300, 3600)
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
        shared_limit(ns, 'guest-link:'+owner, 30, 60)
        # Proof is used only for idempotent linking, never record access.
        with db() as conn:
            proof = execute(conn, 'SELECT code,created FROM sessions WHERE token_hash=?', (token_hash(body.guest_token),)).fetchone()
        if not proof:
            raise HTTPException(401, '연결 키가 만료됐습니다.')
        guest = proof['code']
        if not guest.startswith(PREFIX):
            raise HTTPException(400, '게스트 기록만 연결할 수 있습니다.')
        with db() as conn:
            execute(conn, 'INSERT INTO guest_links(guest_code,owner_code,linked_at) VALUES(?,?,?) ON CONFLICT(guest_code) DO NOTHING', (guest,owner,int(time.time())))
            row = execute(conn, 'SELECT owner_code FROM guest_links WHERE guest_code=?', (guest,)).fetchone()
            if row['owner_code'] != owner:
                raise HTTPException(409, '이미 다른 계정에 연결된 기록입니다. 기존 연결은 변경하지 않았습니다.')
        return {'linked':True, 'id':guest, 'message':'기록을 보존하여 연결했습니다. 이후 소유 계정으로 로그인해야 이어할 수 있으며 기존 계정 기록은 덮어쓰지 않습니다.'}

    @app.post('/api/guest/resume')
    def resume(body: Resume, authorization: str | None = Header(default=None)):
        owner = auth(authorization)
        if owner.startswith(PREFIX):
            raise HTTPException(403, '소유 계정으로 로그인하세요.')
        shared_limit(ns, 'guest-resume:'+owner, 30, 60)
        with db() as conn:
            row = execute(conn, 'SELECT guest_code FROM guest_links WHERE owner_code=? AND guest_code=?', (owner,body.id)).fetchone()
        if not row:
            raise HTTPException(404, '연결된 기록을 찾을 수 없습니다.')
        result = ns['issue_token'](row['guest_code'])
        with db() as conn:
            execute(conn, 'INSERT INTO guest_delegations(token_hash,parent_hash) VALUES(?,?)', (token_hash(result['token']),token_hash(authorization)))
        return {**result, 'guest':True, 'account_bound':True}
