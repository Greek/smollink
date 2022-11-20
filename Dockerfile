FROM python:3.9

WORKDIR /code
EXPOSE 8013

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

RUN prisma generate
RUN cd app

CMD ["python", "app/app.py"]