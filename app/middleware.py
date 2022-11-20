import os

from flask import Flask
from werkzeug.wrappers import Request, Response, ResponseStream


class Middleware:
    def __init__(self, app: Flask):
        self.app = app

    def __call__(self, environ, start_response):
        req = Request(environ)

        if req.path == "/create":
            # if req.referrer != os.environ.get("BASE_URL"):
            #     res = Response(
            #         f"Referer check failed; Requests must be made from {os.environ.get('BASE_URL')}",
            #         status=400,
            #     )
            #     return res(environ, start_response)

            if req.content_type != "application/json":
                res = Response("Provided Content-Type not supported", status=400)
                return res(environ, start_response)
            
        return self.app(environ, start_response)
