FROM python:3.9

ENV JWT_SECRET_KEY="QYmXTKt6bnzaFi76H7R88FQ"

ENV SCRIPT_NAME="/content"

RUN apt update && apt install -y gcc libmariadb-dev-compat

RUN pip install gunicorn

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

COPY . /app

EXPOSE 8000/tcp

ENTRYPOINT gunicorn -w 4 -b 0.0.0.0:8000 'main:app'