from argparse import ArgumentParser
from pathlib import Path

import falcon
import uvicorn

from login_resource import LoginResource, OAuthCallbackResource, LogoutResource
from chat_resource import StreamQueryResource, ModelResource

from config import AppConfig

parser = ArgumentParser()
parser.add_argument("-c", "--config_file", type=Path, required=True)
parser.add_argument("-s", "--store_dir", type=Path, required=True)
parser.add_argument("-m", "--model_name", type=str, required=True)
parser.add_argument("-p", "--port", type=int, default=8000)
args = parser.parse_args()

config = AppConfig(args)

app = falcon.asgi.App()

app.add_route('/login', LoginResource(config))
app.add_route('/oauth2', OAuthCallbackResource(config))
app.add_route('/logout', LogoutResource())
app.add_route('/stream_query', StreamQueryResource(config))
app.add_route('/models', ModelResource(config))

if __name__ == '__main__':
    uvicorn.run(app=app, host="0.0.0.0", port=args.port)