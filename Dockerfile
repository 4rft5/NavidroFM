FROM python:3.11-slim


RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    cron \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /var/cache/apt/archives/*


RUN pip install --no-cache-dir \
    requests \
    yt-dlp \
    yt-dlp-ejs \
    ytmusicapi \
    mutagen \
    && rm -rf /root/.cache/pip


WORKDIR /app


COPY app.py entrypoint.sh /app/


RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /music/navidrofm /app/cookies \
    && chmod -R 777 /music /app/cookies \
    && touch /var/log/cron.log \
    && chmod 666 /var/log/cron.log \
    && chmod 0644 /etc/crontab

ENTRYPOINT ["/app/entrypoint.sh"]
