"""
Main entry point for SmolLink
"""

# pylint: disable=E1101

import logging
import os
import re

import redis
from redis import Redis
import waitress
from flask import Flask, abort, make_response, redirect, render_template, request

from werkzeug.exceptions import BadRequest, TooManyRequests
from werkzeug.wrappers import Request, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from nanoid import generate as _gen
from prisma import Prisma, register
from prisma.models import Link, Creator


def generate(size: int):
    """Generate a nanoid with a custom alphabet."""
    return _gen("1234567890AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz", size)


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


db = Prisma()
db.connect()
register(db)

redis: Redis = redis.Redis.from_url(os.environ.get("REDIS_URL"), decode_responses=True)

app = Flask(__name__)
app.wsgi_app = Middleware(app.wsgi_app)

LINK_REGEX = "((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*"
APP_NAME = "SmolLink"

limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri=os.environ.get("REDIS_URL"),
)

link_cache = {}


def clear_cache():
    """Clear link cache"""
    link_cache.clear()
    return True


def remove_cached_link(shortlink_id: str):
    """Remove a cached link."""
    if shortlink_id not in link_cache:
        return False

    link_cache.pop(shortlink_id)
    return True

def get_real_ip():
    """ Get a user's real IP. """
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
       return request.environ.split(',', 1)['HTTP_X_FORWARDED_FOR'] # if behind a proxy

@app.errorhandler(500)
def server_error_handler(error):
    """Render a page on a bad request"""
    print(error.description)
    return (
        render_template(
            "error.html",
            message="Sorry! There was an error on the server. This has been reported and will be fixed shortly",
        ),
        500,
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
    """The base index page everyone sees :P. Probably ;)"""

    anarchy: bool = os.environ.get("ANARCHY")
    creator = Creator.prisma().find_first(
        where={
            "ip_address": get_real_ip()
        }
    )

    if creator is not None and creator.disabled:
        disable_reason = (
            f"Reason: {creator.disabled_reason}" if creator.disabled_reason else ""
        )
        return (
            render_template(
                "error.html",
                app_name=APP_NAME,
                is_disabled=creator.disabled,
                message=disable_reason,
                title="Uh oh!!",
            ),
            401,
        )

    return render_template(
        "index.html",
        app_name=APP_NAME,
        anarchy=anarchy,
        report_link=os.environ.get("REPORT_CONTACT"),
    )


@app.route("/tos")
def tos():
    """ Terms of Use page. """
    return render_template("info.html")


@app.route("/<shortlink_id>")
def id_redirect(shortlink_id: str):
    """Fetch a shortlink from cache, redis, or db."""
    if shortlink_id in link_cache:
        app.logger.info(f"Hit CACHE for {shortlink_id}")
        return redirect(link_cache[shortlink_id])

    shortlink = redis.get(shortlink_id)
    if shortlink:
        link_cache[shortlink_id] = shortlink

    # If the link doesn't exist in Redis or the local cache, find it in the DB
    if shortlink is None:
        shortlink = Link.prisma().find_unique(where={"id": shortlink_id})
        app.logger.info(f"Hit DATABASE for {shortlink_id}")

        if shortlink is None:
            return (
                make_response(
                    render_template(
                        "error.html", code=404, message="SmolLink not found."
                    )
                ),
                404,
            )

        if shortlink.disabled:
            return make_response(
                render_template(
                    "error.html",
                    code=403,
                    message=f"This SmolLink has been disabled due to a violation in {APP_NAME}'s Terms of Use.\n{shortlink.disabled_reason}",
                )
            )

        link_cache[shortlink_id] = shortlink.redirect_to
        return redirect(shortlink.redirect_to)

    return redirect(shortlink)


@app.route("/create", methods=["POST"])
@limiter.limit("10/seconds", error_message="Slow down there..")
def create_shortlink():
    """Create a shortlink"""
    data = request.json
    try:
        link: str = data["link"]
    except KeyError:
        return abort(400, "Please provide a link.")

    if link is None or len(link) <= 0:
        return abort(400, "Please provide a link.")

    if re.search(LINK_REGEX, link) is None:
        return abort(400, "Please provide a valid URL")

    # If we don't find "http://", we assume it's https. Otherwise, we append "http://".
    # If a protocol isn't found, we'll fallback to https.
    if link.find("http://") == -1:
        desired_protoc = "https://"
    else:
        desired_protoc = "http://"

    creator = Creator.prisma().find_first(
        where={
            "ip_address": get_real_ip()
        },
    )
    if creator is None:
        creator = Creator.prisma().create(
            data={
                "ip_address": get_real_ip(),
            }
        )

    if creator.disabled:
        return app.json.response(error="You cannot make shortlinks."), 403

    shortlink = Link.prisma().create(
        data={
            "id": generate(7),
            "redirect_to": desired_protoc
            + link.replace("http://", "").replace("https://", ""),
            "creator_id": creator.id,
        },
    )

    # Entry in Redis
    redis.set(shortlink.id, shortlink.redirect_to)

    return dict(id=shortlink.id)


@app.route("/sh/remove/<shortlink_id>", methods=["DELETE"])
async def delete_shortlink(shortlink_id: str):
    """Delete a shortlink."""
    if os.environ.get("ANARCHY") == "1":
        return app.json.response(error="This route is not available!"), 401

    remove_cached_link(shortlink_id)
    redis.delete(shortlink_id)
    Link.prisma().delete(where={"id": shortlink_id})

    return app.json.response(result=f"Deleted {shortlink_id}.")


@app.route("/sh/disable/<shortlink_id>", methods=["PATCH"])
async def disable_shortlink(shortlink_id: str):
    """Disable a shortlink. Only use this for TOS, legal and privacy reasons."""
    if os.environ.get("ANARCHY") == "1":
        return app.json.response(error="This route is not available!"), 401

    reason: str = request.args.get("reason")

    remove_cached_link(shortlink_id)
    redis.delete(shortlink_id)
    Link.prisma().update(
        where={"id": shortlink_id},
        data={
            "disabled": True,
            "disabled_reason": reason if reason is not None else "No reason provided.",
        },
    )

    return app.json.response(
        result=f"Disabled {shortlink_id}{f' for {reason}.' if reason is not None else '.'}"
    )


if __name__ == "__main__":
    logger = logging.getLogger("waitress")
    logger.setLevel(logging.INFO)

    waitress.serve(app, port=os.environ.get("PORT") or 3000)
