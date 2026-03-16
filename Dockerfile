FROM python:3.11-slim

RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        curl \
        unzip \
        xz-utils \
        ca-certificates && \
    curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    mv /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ && \
    mv /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno && \
    rm -rf /root/.deno && \
    apt-get remove -y xz-utils && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/* /var/tmp/* /root/.cache

RUN pip install --no-cache-dir \
    requests \
    yt-dlp[default] \
    ytmusicapi \
    mutagen && \
    rm -rf /root/.cache/pip

WORKDIR /app
COPY app.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /music/navidrofm /app/cookies && \
    chmod -R 777 /music /app/cookies && \
    touch /var/log/cron.log && \
    chmod 666 /var/log/cron.log && \
    chmod 0644 /etc/crontab

ENTRYPOINT ["/app/entrypoint.sh"]
