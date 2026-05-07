FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cron \
    tini \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/entrypoint.sh /app/scripts/cron_pipeline.sh
RUN crontab /app/crontab.txt

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/scripts/entrypoint.sh"]
