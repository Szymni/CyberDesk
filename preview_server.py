"""Local interactive preview. It runs the same Flask routes against an explicit SQLite DB."""
import argparse
import os
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','5000')))
parser.add_argument('--host',default='0.0.0.0')
args,_ = parser.parse_known_args()
os.environ['APP_DB']='sqlite'
os.environ['DEMO_MODE']='1'
Path(__file__).resolve().parent.joinpath('instance').mkdir(exist_ok=True)
from app import app,init_db,seed_demo
with app.app_context():
    init_db()
    seed_demo()
print(f'CyberDesk local preview: http://{args.host}:{args.port}',flush=True)
app.run(host=args.host,port=args.port,debug=False)
