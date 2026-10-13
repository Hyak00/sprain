"""Inicializar o Docker de desenvolvimento e a demonstracao sem resetar dados.

Executar na maquina com Docker Desktop em funcionamento. Usa somente a biblioteca padrao.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose',type=Path,default=ROOT/'docker-compose.yml')
    args=parser.parse_args()
    docker=shutil.which('docker')
    if not docker and os.name=='nt':
        candidate=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/DockerDesktop/resources/bin/docker.exe'
        if candidate.is_file():
            docker=str(candidate)
    if not docker:
        raise SystemExit('Docker nao encontrado. Instale/inicie o Docker Desktop antes de executar.')
    compose=[docker,'compose','-f',str(args.compose.resolve(strict=True))]
    env=os.environ.copy();env.setdefault('SPRAIN_API_KEY','key_admin_demo')
    def run(*command,capture=False):
        return subprocess.run(compose+list(command),cwd=ROOT,env=env,check=True,text=True,
                              stdout=subprocess.PIPE if capture else None)
    # Inicializar o banco antes da API evita que o startup crie um schema parcial.
    run('up','-d','db')
    for attempt in range(60):
        try:
            run('exec','-T','db','pg_isready','-h','127.0.0.1','-U','enchentes','-d','enchentes',capture=True)
            break
        except subprocess.CalledProcessError:
            time.sleep(2)
    else:
        raise SystemExit('Banco nao iniciou. Verifique os logs do Docker.')
    def sql(query):
        return run('exec','-T','db','psql','-U','enchentes','-d','enchentes','-At','-v','ON_ERROR_STOP=1','-c',query,capture=True).stdout.strip()
    exists=sql("SELECT to_regclass('public.trechos_osm') IS NOT NULL")=='t'
    if not exists:
        tables=sql("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename<>'spatial_ref_sys'")
        if tables!='0':
            raise SystemExit('Banco parcial detectado. Nada foi apagado. Use uma base de desenvolvimento vazia ou corrija o bootstrap existente.')
        files=sorted((ROOT/'db/ci').glob('*.sql'))
    else:
        files=sorted(p for p in (ROOT/'db/ci').glob('*.sql') if not p.name.startswith('01_'))
    for path in files:
        run('cp',str(path),'db:/tmp/sprain-demo-schema.sql')
        run('exec','-T','db','psql','-U','enchentes','-d','enchentes','-v','ON_ERROR_STOP=1','-f','/tmp/sprain-demo-schema.sql')
    run('up','-d','--build','api')
    for attempt in range(90):
        result=subprocess.run(compose+['exec','-T','api','python','-c',
            "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/readiness',timeout=3)"],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode==0:
            break
        time.sleep(2)
    else:
        raise SystemExit('API nao ficou pronta. Consulte os logs; o banco existente foi preservado.')
    run('exec','-T','-e','SPRAIN_API_KEY','api','python','/app/scripts/bootstrap_demo_caminhoes.py')


if __name__=='__main__':
    main()
