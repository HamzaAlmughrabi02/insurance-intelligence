"""Local account authentication. Integration credentials never enter the browser."""
import hashlib,hmac,json,os,re,secrets,threading,time
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHash
import server as base

PASSWORDS=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
HASH_SLOTS=threading.BoundedSemaphore(2)
COOKIE='insurance_session'
DUMMY_HASH=PASSWORDS.hash(secrets.token_urlsafe(32))

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def init():
 with base.conn() as c:
  c.executescript('''
CREATE TABLE IF NOT EXISTS local_users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','operator')),created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS browser_sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES local_users(id),csrf TEXT NOT NULL,expires REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS setup_invites(token_hash TEXT PRIMARY KEY,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS login_throttle(peer TEXT PRIMARY KEY,failures INTEGER NOT NULL DEFAULT 0,locked_until REAL NOT NULL DEFAULT 0);
''')

def issue_setup_invite():
 with base.conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM local_users LIMIT 1').fetchone():return None
  token=secrets.token_urlsafe(32)
  c.execute('UPDATE setup_invites SET used=1 WHERE used=0')
  c.execute('INSERT INTO setup_invites VALUES(?,?,0)',(digest(token),time.time()+900))
  return token

class AuthMixin:
 def end_headers(self):
  self.send_header('X-Frame-Options','SAMEORIGIN' if getattr(self,'_inline_document',False) else 'DENY')
  self.send_header('Referrer-Policy','no-referrer')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Cache-Control','no-store')
  ancestors="'self'" if getattr(self,'_inline_document',False) else "'none'"
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors "+ancestors+"; form-action 'self'")
  if getattr(self,'_set_cookie',None):self.send_header('Set-Cookie',self._set_cookie)
  super().end_headers()

 def local_origin(self):
  host=self.headers.get('Host','')
  try:parsed=urlsplit('http://'+host)
  except ValueError:return False
  if parsed.hostname not in ('127.0.0.1','localhost'):return False
  origin=self.headers.get('Origin')
  return origin is None or origin=='http://'+host

 def _session(self):
  if hasattr(self,'_cached_session'):return self._cached_session
  try:
   cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
   raw=cookies[COOKIE].value if COOKIE in cookies else ''
  except Exception:raw=''
  row=None
  if raw and len(raw)<200:
   with base.conn() as c:
    row=c.execute('SELECT s.token_hash,s.csrf,s.expires,u.id,u.username,u.role FROM browser_sessions s JOIN local_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.revoked=0 AND s.expires>?',(digest(raw),time.time())).fetchone()
  self._cached_session=dict(row) if row else None
  return self._cached_session

 def auth(self,role=None):
  if not self.local_origin():self.fail(403,'Origin not allowed');return False
  session=self._session()
  if session:
   if self.command not in ('GET','HEAD') and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):self.fail(403,'Invalid CSRF token');return False
   if role=='supervisor' and session['role']!='admin':self.fail(403,'Supervisor account required');return False
   self.actor=session['username'];return True
  # Explicit compatibility option for isolated regression scripts only, never default login.
  if os.environ.get('INSURANCE_LEGACY_API')=='1':
   valid=super().auth(role)
   if valid:self.actor='legacy_operator'
   return valid
  self.fail(401,'Authentication required');return False

 def _issue_session(self,c,user,remember):
  raw=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
  ttl=30*24*3600 if remember else 12*3600
  c.execute('INSERT INTO browser_sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)',(digest(raw),user['id'],csrf,time.time()+ttl))
  self._set_cookie=f'{COOKIE}={raw}; Path=/; HttpOnly; SameSite=Strict'+(f'; Max-Age={ttl}' if remember else '')
  return {'authenticated':True,'user':{'username':user['username'],'role':user['role']},'csrf':csrf}

 def auth_get(self,path):
  if path not in ('/api/auth/status','/api/auth/session'):return False
  if not self.local_origin():self.fail(403,'Origin not allowed');return True
  with base.conn() as c:configured=bool(c.execute('SELECT 1 FROM local_users LIMIT 1').fetchone())
  if path.endswith('/status'):self.reply(200,{'setup_required':not configured});return True
  s=self._session()
  if not s:self.fail(401,'Authentication required');return True
  self.reply(200,{'authenticated':True,'user':{'username':s['username'],'role':s['role']},'csrf':s['csrf']});return True

 def auth_post(self,path):
  if path not in ('/api/auth/setup','/api/auth/login','/api/auth/logout'):return False
  if not self.local_origin():self.fail(403,'Origin not allowed');return True
  if path.endswith('/logout'):
   if not self.auth():return True
   with base.conn() as c:c.execute('UPDATE browser_sessions SET revoked=1 WHERE token_hash=?',(self._session()['token_hash'],));base.event(c,None,'logout',self.actor)
   self._set_cookie=f'{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
   self.reply(200,{'authenticated':False});return True
  try:length=int(self.headers.get('Content-Length','0'))
  except ValueError:length=0
  if not 0<length<=4096:self.fail(400,'Invalid authentication request');return True
  obj=self.body()
  if obj is None:return True
  username=obj.get('username','');password=obj.get('password','')
  if not isinstance(username,str) or not isinstance(password,str) or len(password)>256:self.fail(400,'Invalid username or password');return True
  username=username.strip().casefold()
  peer=self.client_address[0]
  with base.conn() as c:
   throttle=c.execute('SELECT * FROM login_throttle WHERE peer=?',(peer,)).fetchone()
   if throttle and throttle['locked_until']>time.time():self.fail(429,'Too many attempts. Try again in a few minutes.');return True
  if not HASH_SLOTS.acquire(blocking=False):self.fail(429,'Authentication is busy. Please try again.');return True
  try:
   if path.endswith('/setup'):
    ticket=obj.get('setup_ticket','')
    if not isinstance(ticket,str) or len(ticket)>200:self.fail(403,'Open the desktop launcher to set up your account');return True
    with base.conn() as c:
     invite=c.execute('SELECT 1 FROM setup_invites WHERE token_hash=? AND used=0 AND expires>?',(digest(ticket),time.time())).fetchone()
     exists=c.execute('SELECT 1 FROM local_users LIMIT 1').fetchone()
    if exists:self.fail(409,'Account already configured. Sign in.');return True
    if not invite:self.fail(403,'Open the desktop launcher to set up your account');return True
    if not re.fullmatch(r'[\w.-]{3,64}',username) or not 12<=len(password)<=256:self.fail(400,'Username needs 3–64 letters or numbers; password needs at least 12 characters');return True
    hashed=PASSWORDS.hash(password)
    with base.conn() as c:
     c.execute('BEGIN IMMEDIATE')
     if c.execute('SELECT 1 FROM local_users LIMIT 1').fetchone():self.fail(409,'Account already configured. Sign in.');return True
     if not c.execute('SELECT 1 FROM setup_invites WHERE token_hash=? AND used=0 AND expires>?',(digest(ticket),time.time())).fetchone():self.fail(403,'Setup invitation expired. Open the desktop launcher again.');return True
     c.execute('INSERT INTO local_users(username,password_hash,role,created_at) VALUES(?,?,?,?)',(username,hashed,'admin',base.now()))
     user=c.execute('SELECT id,username,role FROM local_users WHERE username=?',(username,)).fetchone()
     c.execute('UPDATE setup_invites SET used=1 WHERE used=0');base.event(c,None,'account_created',username)
     response=self._issue_session(c,user,bool(obj.get('remember')))
    self.reply(201,response);return True
   with base.conn() as c:user=c.execute('SELECT * FROM local_users WHERE username=?',(username,)).fetchone()
   try:valid=PASSWORDS.verify(user['password_hash'] if user else DUMMY_HASH,password) and user is not None
   except (VerificationError,InvalidHash):valid=False
   if not valid:
    with base.conn() as c:
     c.execute('BEGIN IMMEDIATE')
     r=c.execute('SELECT * FROM login_throttle WHERE peer=?',(peer,)).fetchone()
     failures=(r['failures'] if r and r['locked_until']<=time.time() else 0)+1
     c.execute('INSERT INTO login_throttle VALUES(?,?,?) ON CONFLICT(peer) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until',(peer,failures,time.time()+300 if failures>=5 else 0))
    self.fail(401,'Incorrect username or password');return True
   with base.conn() as c:
    c.execute('UPDATE login_throttle SET failures=0,locked_until=0 WHERE peer=?',(peer,))
    response=self._issue_session(c,user,bool(obj.get('remember')));base.event(c,None,'login',user['username'])
   self.reply(200,response);return True
  finally:HASH_SLOTS.release()
