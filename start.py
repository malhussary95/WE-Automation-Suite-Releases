from pathlib import Path
import subprocess, sys, time, webbrowser

def main():
    base=Path(__file__).resolve().parent
    port=8010
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','webapp.server:app','--host','127.0.0.1','--port',str(port)],cwd=str(base))
    try:
        for _ in range(30):
            time.sleep(.3)
            import socket
            s=socket.socket(); s.settimeout(.2)
            ok=s.connect_ex(('127.0.0.1',port))==0; s.close()
            if ok:
                webbrowser.open(f'http://127.0.0.1:{port}/')
                break
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__=='__main__': main()
