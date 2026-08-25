FROM python:3.11-slim

RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        curl \
        unzip \
        xz-utils \
        ca-certificates && \
    curl -L https://ffmpeg.martin-riedl.de/redirect/latest/linux/amd64/release/ffmpeg.zip -o /tmp/ffmpeg.zip && \
    curl -L https://ffmpeg.martin-riedl.de/redirect/latest/linux/amd64/release/ffprobe.zip -o /tmp/ffprobe.zip && \
    unzip -o /tmp/ffmpeg.zip -d /usr/local/bin/ && \
    unzip -o /tmp/ffprobe.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg* /tmp/ffprobe* && \
    curl -fsSL https://deno.land/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno && \
    rm -rf /root/.deno && \
    apt-get remove -y xz-utils && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/* /var/tmp/* /root/.cache

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    git clone --single-branch --branch master \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil && \
    cd /app/bgutil/server && \
    deno install --allow-scripts=npm:canvas --frozen && \
    apt-get remove -y git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/* /var/tmp/* /root/.cache

RUN pip install --no-cache-dir \
    requests \
    yt-dlp[default] \
    "ytmusicapi>=1.12.1" \
    mutagen \
    bgutil-ytdlp-pot-provider && \
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