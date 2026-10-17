"""Iniciar e preparar somente a composição dedicada de demonstração."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compose',type=Path,default=ROOT/'compose.demo.yml')
    a=p.parse_args()
    if a.compose.resolve()!= (ROOT/'compose.demo.yml').resolve():
        raise SystemExit('Este inicializador aceita somente compose.demo.yml; nenhuma composição operacional será iniciada ou alterada.')
    docker=shutil.which('docker')
    if not docker and os.name=='nt':
        candidato=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/DockerDesktop/resources/bin/docker.exe'
        if candidato.is_file():docker=str(candidato)
    if not docker:raise SystemExit('Inicie/instale o Docker Desktop antes de executar.')
    compose=[docker,'compose','-f',str(a.compose.resolve(strict=True))]
    subprocess.run(compose+['up','-d','--build','api'],cwd=ROOT,check=True)
    for _ in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:18000/api/v1/health/readiness',timeout=3) as r:
                if r.status==200:break
        except OSError:pass
        time.sleep(2)
    else:raise SystemExit('A API de demonstração não ficou pronta; consulte seus logs. Nenhum volume foi apagado.')
    subprocess.run([__import__('sys').executable,str(ROOT/'scripts/preparar_demonstracao.py')],cwd=ROOT,check=True)

if __name__=='__main__':main()
