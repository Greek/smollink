"""
Main entry point for SmolLink
"""

import logging
import os
import re

import redis
import waitress
from flask import (Flask, abort, make_response, redirect, render_template,
                   request)

from werkzeug.exceptions import BadRequest, TooManyRequests
from werkzeug.wrappers import Request, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from nanoid import generate as _gen
from prisma import Prisma, register
from prisma.models import Link

def generate(size: int):
    """Generate a nanoid with a custom alphabet."""
    return _gen("1234567890AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz", size)


LINK_REGEX = "((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*"
APP_NAME = "linker32"

db = Prisma()
db.connect()
register(db)

# load_dotenv()
redis = redis.Redis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)

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

app = Flask(__name__)
app.wsgi_app = Middleware(app.wsgi_app)

limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL"),
)


@app.errorhandler(429)
def ratelimit_handler(error: TooManyRequests):
    """Handle a ratelimit"""
    return app.json.response(error=error.description), 429


@app.errorhandler(400)
def bad_request_handler(error: BadRequest):
    """Render a page on a bad request"""
    return app.json.response(error=error.description), 400


@app.route("/")
def index():
    return render_template("index.html", app_name=APP_NAME)

@app.route("/<id>")
async def id_redirect(id: str):
    """Fetch a shortlink from Redis"""
    shortlink = redis.get(id)

    # If the link doesn't exist in cache, find it in the DB
    if shortlink is None:
        app.logger.info(f"Hit DB for {id}")
        shortlink = Link.prisma().find_unique(where={"id": id})

        if shortlink is None:
            return make_response(
                render_template("error.html", code=404, message="Shortlink not found.")
            )

        return redirect(shortlink.redirect_to)

    return redirect(shortlink)


@app.route("/create", methods=["POST"])
@limiter.limit("50/minutes", error_message="Slow down there..")
async def create_shortlink():
    """Create a shortlink"""
    data = request.json
    try:
        link: str = data["link"]
    except KeyError:
        return abort(400, "Please provide a link in the body")

    if link is None or len(link) <= 0:
        return abort(400, "Please provide a link in the body")

    if re.search(LINK_REGEX, link) is None:
        return abort(400, "Please provide a valid URL")

    # If we don't find "http://", we assume it's https. Otherwise, we append "http://".
    # If a protocol isn't found, we'll fallback to https.
    if link.find("http://") == -1:
        desired_protoc = "https://"
    else:
        desired_protoc = "http://"

    shortlink = Link.prisma().create(
        data={
            "id": generate(7),
            "redirect_to": desired_protoc
            + link.replace("http://", "").replace("https://", ""),
        },
    )

    # Entry in Redis
    redis.set(shortlink.id, shortlink.redirect_to)

    return dict(id=shortlink.id)


if __name__ == "__main__":
    logger = logging.getLogger("waitress")
    logger.setLevel(logging.INFO)

    waitress.serve(app, host="localhost", port=8080)
