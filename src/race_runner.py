"""Run an identified TORCS controller and retain raw, auditable local telemetry."""
import argparse, datetime, hashlib, importlib.util, json, os, socket, time, sys
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ['TORCS_HOME']).expanduser().resolve()
def load(path):
    spec=importlib.util.spec_from_file_location('race_controller',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--controller',default=str(HERE/'controller_fastest_clean.py'));ap.add_argument('--label',default='fastest-clean');ap.add_argument('--settings',default='{}');ap.add_argument('--settings-file');a=ap.parse_args()
    if a.settings_file:a.settings=Path(a.settings_file).read_text(encoding='utf-8-sig')
    sys.argv=sys.argv[:1]
    path=Path(a.controller);m=load(path)
    if hasattr(m,'configure'):m.configure(json.loads(a.settings))
    base=load(HERE/'snakeoil3_gym.py')
    client=SimpleNamespace(S=base.ServerState(),R=base.DriverAction())
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out=HERE/'runs'/f'{stamp}-{a.label}';out.mkdir(parents=True,exist_ok=True)
    (out/path.name).write_bytes(path.read_bytes())
    files=[path,HERE/'snakeoil3_gym.py',ROOT/'cars/car1-ow1/car1-ow1.xml',ROOT/'tracks/road/corkscrew/corkscrew.xml',ROOT/'config/raceman/quickrace.xml',ROOT/'drivers/scr_server/scr_server.xml',ROOT/'drivers/scr_server/0/default.xml']
    summary={'controller':str(path),'settings':a.settings,'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'status':'waiting','max_damage':0,'lap_completed':False}
    so=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);so.settimeout(1)
    addr=('127.0.0.1',3001);start=time.monotonic();last={};step=0
    print('RUN '+str(out),flush=True)
    try:
        while time.monotonic()-start<180:
            so.sendto(b'SCR(init -45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45)',addr)
            try:packet,_=so.recvfrom(131072)
            except (socket.timeout,ConnectionResetError):continue
            if b'***identified***' in packet:break
        else:raise TimeoutError('No SCR handshake')
        print('CONNECTED',flush=True);summary['status']='running';timeouts=0
        drive=getattr(m,'drive',None) or getattr(m,'drive_v3',None)
        with (out/'telemetry.jsonl').open('w',encoding='utf-8') as f:
            while step<30000:
                try:packet,_=so.recvfrom(131072);timeouts=0
                except (socket.timeout,ConnectionResetError):
                    timeouts+=1
                    if timeouts>20:raise TimeoutError('Telemetry stopped')
                    continue
                msg=packet.decode('utf-8').rstrip('\0')
                if '***shutdown***' in msg or '***restart***' in msg:summary['status']='server_finished';break
                if '***identified***' in msg:continue
                client.S.parse_server_str(msg+'\0');last=dict(client.S.d)
                if step==0:summary['initial_state']=last
                diag=drive(client)
                f.write(json.dumps({'step':step,'s':last,'a':dict(client.R.d),'diag':diag})+'\n')
                so.sendto(repr(client.R).encode(),addr)
                summary['max_damage']=max(summary['max_damage'],last.get('damage',0))
                if last.get('lastLapTime',0)>0:summary.update(lap_completed=True,lap_time=last['lastLapTime'])
                if step%250==0:
                    f.flush();print(json.dumps({k:last.get(k) for k in ['curLapTime','distFromStart','speedX','damage','trackPos','angle','gear','fuel']}),flush=True)
                step+=1
    except Exception as exc:summary['status']='error';summary['error']=repr(exc);print(repr(exc),flush=True)
    finally:
        so.close();summary['final_state']=last;summary['steps']=step;summary['wall_seconds']=time.monotonic()-start
        (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
