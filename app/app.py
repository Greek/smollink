"""
Main entry point for SmolLink
"""

import os
import re
import waitress

import redis
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, make_response

from nanoid import generate as _gen
from prisma.models import Link

from prisma import Prisma, register

# from middleware import Middleware


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


app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL"),
)


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle a ratelimit"""
    return app.json.response(error=e), 429


@app.errorhandler(400)
def bad_request_handler(e):
    """Render a page on a bad request"""
    return app.json.response(error=e), 400


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
@limiter.limit("5/minute")
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

    # Entry in database
    shortlink = Link.prisma().create(
        data={
            "id": generate(7),
            "redirect_to": desired_protoc
            + link.replace("http://", "").replace("https://", ""),
        }
    )

    # Entry in Redis
    redis.set(shortlink.id, shortlink.redirect_to)

    return dict(shortlink)


if __name__ == "__main__":
    waitress.serve(app, host="0.0.0.0", port=8080)
