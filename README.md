# SmolLink

SmolLink is a simple, yet effective, link shortening application.

## Setup

To setup SmolLink for your own setup, you first need to install Python 3.10. Then follow these steps:
1. Copy `.env.example` to `.env` **AND `./app/.env`**
2. Set the database, redis, and contact values to your liking.
3. Install project requirements
```sh
$ python -m pip install -r requirements.txt
``` 
4. Generate and push the database schema
```sh
$ python -m prisma generate # Generate models
$ python -m prisma migrate deploy # Push the migrations
```
## Running SmolLink

Simply run,
```sh
# This will start a waitress server running on any port you specify or port 3000
# You can also use your WSGI server tool of your choice if you want, like gunicorn.
$ python app/app.py 

```

For development, run
```sh
# This will start a Flask dev server with hot-reloading
$ flask --debug --app app/app.py run 
```
