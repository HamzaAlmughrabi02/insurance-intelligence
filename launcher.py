"""Desktop entry point: start existing local services and open the account UI."""
import ctypes,json,os,shutil,subprocess,sys,time,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE='http://127.0.0.1:8766'
NO_WINDOW=getattr(subprocess,'CREATE_NO_WINDOW',0)

def status(stage,error=None):
 (ROOT/'launcher-status.json').write_text(json.dumps({'stage':stage,'error':error,'updated_at':time.time()},ensure_ascii=False),encoding='utf-8')

def health(url):
 try:
  with urllib.request.urlopen(url,timeout=2) as response:return json.load(response)
 except Exception:return None

def spawn(args,prefix,env=None):
 stamp=time.strftime('%Y%m%d-%H%M%S')
 with open(ROOT/f'{prefix}-{stamp}.stdout.log','ab') as out,open(ROOT/f'{prefix}-{stamp}.stderr.log','ab') as err:
  proc=subprocess.Popen(args,cwd=ROOT,env=env,stdout=out,stderr=err,creationflags=NO_WINDOW)
 (ROOT/(prefix+'.pid')).write_text(str(proc.pid));return proc

def run(command,timeout=10):
 return subprocess.run(command,capture_output=True,timeout=timeout,creationflags=NO_WINDOW)

def start_database():
 docker=shutil.which('docker')
 if not docker:raise RuntimeError('Docker Desktop غير مثبت أو غير متاح. افتحه ثم شغّل الاختصار مجددًا.')
 try:ready=run([docker,'info','--format','{{.ServerVersion}}'],5).returncode==0
 except subprocess.TimeoutExpired:ready=False
 if not ready:
  desktop=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Docker/Docker/Docker Desktop.exe'
  if not desktop.exists():raise RuntimeError('افتح Docker Desktop ثم شغّل الاختصار مجددًا.')
  subprocess.Popen([str(desktop)],creationflags=NO_WINDOW)
  for _ in range(60):
   time.sleep(2)
   try:
    if run([docker,'info','--format','{{.ServerVersion}}'],3).returncode==0:break
   except subprocess.TimeoutExpired:pass
  else:raise RuntimeError('لم يكتمل تشغيل Docker. افتحه وانتظر جاهزيته ثم شغّل الاختصار مجددًا.')
 response=run([docker,'start','insurance-postgres'],30)
 if response.returncode:raise RuntimeError('تعذر تشغيل حاوية insurance-postgres الموجودة. لم يتم إنشاء أو استبدال أي قاعدة.')
 for _ in range(30):
  response=run([docker,'inspect','--format','{{.State.Health.Status}}','insurance-postgres'])
  if response.returncode==0 and response.stdout.strip()==b'healthy':return
  time.sleep(1)
 raise RuntimeError('قاعدة البيانات لم تصبح جاهزة بعد. راجع Docker Desktop.')

def start_n8n():
 if health('http://127.0.0.1:5678/healthz'):return
 node=shutil.which('node')
 script=Path(os.environ.get('APPDATA',''))/'npm/node_modules/n8n/bin/n8n'
 if not node or not script.exists():raise RuntimeError('تعذر العثور على تثبيت n8n الحالي. لم يتم تثبيت بديل أو تغيير قواعده.')
 spawn([node,str(script),'start'],'n8n')
 for _ in range(60):
  if health('http://127.0.0.1:5678/healthz'):return
  time.sleep(1)
 raise RuntimeError('لم يكتمل تشغيل n8n. راجع سجل n8n الأخير في مجلد المنصة.')

def main():
 import msvcrt
 lock=open(ROOT/'launcher.lock','a+b');lock.seek(0)
 if lock.read(1)==b'':lock.write(b'0');lock.flush()
 lock.seek(0)
 try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 except OSError:
  if '--no-browser' not in sys.argv:webbrowser.open(BASE)
  return
 try:
  status('starting_website')
  sys.path.insert(0,str(ROOT/'backend'))
  import integration
  integration.init()
  current=health(BASE+'/api/health')
  if current and not current.get('account_login'):raise RuntimeError('تعمل نسخة قديمة من الموقع على 8766؛ أعد تشغيل خادم المنصة لتطبيق تسجيل الدخول الجديد.')
  if not current:
   env=dict(os.environ,PORT='8766');env.pop('INSURANCE_LEGACY_API',None)
   spawn([str(Path(sys.executable).with_name('python.exe')),'-u',str(ROOT/'backend/integration.py')],'backend',env)
   for _ in range(30):
    if health(BASE+'/api/health'):break
    time.sleep(.5)
   else:raise RuntimeError('تعذر تشغيل الموقع. راجع سجل backend الأخير في مجلد المنصة.')
  ticket=integration.auth_sessions.issue_setup_invite()
  if '--no-browser' not in sys.argv:webbrowser.open(BASE+('/#setup='+ticket if ticket else '/'))
  status('starting_database');start_database()
  status('starting_n8n');start_n8n()
  status('ready')
 except Exception as error:
  message=str(error) if isinstance(error,RuntimeError) else 'تعذر بدء التشغيل. راجع سجل الخدمات في مجلد المنصة.'
  status('failed',message)
  if '--no-browser' not in sys.argv:ctypes.windll.user32.MessageBoxW(None,message,'تشغيل منصة التأمين',0x10)
  if '--no-browser' in sys.argv:print(message,file=sys.stderr)
 finally:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
