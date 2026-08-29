#!/bin/bash
set -e

umask 000

PYTHON_PATH=$(which python3)

start_pot_server() {
    echo "Starting bgutil POT server..."
    cd /app/bgutil/server/node_modules && \
    deno run --quiet --allow-env --allow-net --allow-ffi=. --allow-read=. ../src/main.ts > /dev/null 2>&1 &
    GREP_PID=$!
    sleep 3
    DENO_PID=$(grep -rl "^deno$" /proc/[0-9]*/comm 2>/dev/null | head -1 | cut -d/ -f3)
}

stop_pot_server() {
    echo "Stopping bgutil POT server..."
    [ -n "$GREP_PID" ] && kill $GREP_PID 2>/dev/null
    [ -n "$DENO_PID" ] && kill $DENO_PID 2>/dev/null
    unset DENO_PID GREP_PID
}

run_sync() {
    start_pot_server
    ${PYTHON_PATH} /app/app.py all 2>&1
    stop_pot_server
}

# Called by cron
if [ "$1" = "sync" ]; then
    source /app/cron-env.sh
    run_sync
    exit 0
fi

cat > /app/cron-env.sh << EOF
#!/bin/bash
export LASTFM_USERNAME="${LASTFM_USERNAME}"
export NAVIDROME_URL="${NAVIDROME_URL}"
export NAVIDROME_USERNAME="${NAVIDROME_USERNAME}"
export NAVIDROME_PASSWORD="${NAVIDROME_PASSWORD}"
export RECOMMENDED="${RECOMMENDED}"
export RECOMMENDED_TRACKS="${RECOMMENDED_TRACKS}"
export RECOMMENDED_SCHEDULE="${RECOMMENDED_SCHEDULE}"
export MIX="${MIX}"
export MIX_TRACKS="${MIX_TRACKS}"
export MIX_SCHEDULE="${MIX_SCHEDULE}"
export LIBRARY="${LIBRARY}"
export LIBRARY_TRACKS="${LIBRARY_TRACKS}"
export LIBRARY_SCHEDULE="${LIBRARY_SCHEDULE}"
export LZ_USERNAME="${LZ_USERNAME}"
export EXPLORATION="${EXPLORATION}"
export EXPLORATION_TRACKS="${EXPLORATION_TRACKS}"
export EXPLORATION_SCHEDULE="${EXPLORATION_SCHEDULE}"
export JAMS="${JAMS}"
export JAMS_TRACKS="${JAMS_TRACKS}"
export JAMS_SCHEDULE="${JAMS_SCHEDULE}"
export TAGS="${TAGS}"
export TAGS_TRACKS="${TAGS_TRACKS}"
export SYNC_SCHEDULE="${SYNC_SCHEDULE}"
export LOCAL_ONLY="${LOCAL_ONLY}"
export TZ="${TZ}"
export PATH="/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
EOF

chmod +x /app/cron-env.sh

ANY_ENABLED=false
if [ "${RECOMMENDED}" = "true" ] || [ "${MIX}" = "true" ] || [ "${LIBRARY}" = "true" ]; then
    ANY_ENABLED=true
fi

if [ -n "${TAGS}" ]; then
    ANY_ENABLED=true
fi

if [ -n "${LZ_USERNAME}" ]; then
    if [ "${EXPLORATION}" = "true" ] || [ "${JAMS}" = "true" ]; then
        ANY_ENABLED=true
    fi
fi

if [ "$ANY_ENABLED" = "true" ]; then
    if [ -n "${SYNC_SCHEDULE}" ]; then
        SCHEDULE="${SYNC_SCHEDULE}"
    else
        SCHEDULE="0 4 * * 1"

        if [ "${RECOMMENDED}" = "true" ]; then
            SCHEDULE="${RECOMMENDED_SCHEDULE:-0 4 * * 1}"
        elif [ "${MIX}" = "true" ]; then
            SCHEDULE="${MIX_SCHEDULE:-0 4 * * 1}"
        elif [ "${LIBRARY}" = "true" ]; then
            SCHEDULE="${LIBRARY_SCHEDULE:-0 4 * * 1}"
        elif [ -n "${TAGS}" ]; then
            SCHEDULE="0 4 * * 1"
        elif [ "${EXPLORATION}" = "true" ]; then
            SCHEDULE="${EXPLORATION_SCHEDULE:-0 4 * * 1}"
        elif [ "${JAMS}" = "true" ]; then
            SCHEDULE="${JAMS_SCHEDULE:-0 4 * * 1}"
        fi
    fi

    # Set up cron job
    echo "${SCHEDULE} /app/entrypoint.sh sync >> /var/log/cron.log 2>&1" > /etc/cron.d/lastfm-sync
    chmod 0644 /etc/cron.d/lastfm-sync
    crontab /etc/cron.d/lastfm-sync

    echo "NavidroFM starting."
    echo "Cron job configured successfully"

    echo ""
    echo "Enabled playlists:"
    [ "${RECOMMENDED}" = "true" ] && echo "  - LastFM Recommended"
    [ "${MIX}" = "true" ] && echo "  - LastFM Mix"
    [ "${LIBRARY}" = "true" ] && echo "  - LastFM Library"
    if [ -n "${TAGS}" ]; then
        IFS=',' read -ra TAG_ARRAY <<< "${TAGS}"
        for TAG in "${TAG_ARRAY[@]}"; do
            TAG_TRIMMED=$(echo "${TAG}" | xargs)
            [ -n "${TAG_TRIMMED}" ] && echo "  - LastFM Tag: ${TAG_TRIMMED}"
        done
    fi
    [ "${EXPLORATION}" = "true" ] && [ -n "${LZ_USERNAME}" ] && echo "  - ListenBrainz Weekly Exploration"
    [ "${JAMS}" = "true" ] && [ -n "${LZ_USERNAME}" ] && echo "  - ListenBrainz Weekly Jams"
    echo ""
else
    echo "No playlists enabled"
fi

if [ "${RUN_ON_STARTUP}" = "true" ]; then
    if [ "$ANY_ENABLED" = "true" ]; then
        echo ""
        echo "=========================================="
        echo "Running initial sync..."
        echo "=========================================="
        echo ""

        run_sync

        echo ""
        echo "=========================================="
        echo "Initial sync completed"
        echo "=========================================="
    else
        echo ""
        echo "No playlists enabled. Configure LASTFM_USERNAME or LZ_USERNAME and enable playlists in docker-compose.yml"
        echo ""
    fi
fi

echo ""
if [ "$ANY_ENABLED" = "true" ]; then
    echo "Starting cron daemon..."
    echo "Next sync scheduled for: ${SCHEDULE}"
    echo ""

    cron

    touch /var/log/cron.log
    tail -f /var/log/cron.log
else
    echo "No playlists enabled and no cron jobs configured."
    echo "Container will exit. Enable at least one playlist in docker-compose.yml"
    exit 1
fi