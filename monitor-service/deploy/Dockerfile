FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt


COPY . /app

COPY deploy/entrypoint.sh /entrypoint.sh
RUN useradd -m appuser && chown -R appuser:appuser /app /entrypoint.sh
USER appuser
CMD ["/entrypoint.sh"]
