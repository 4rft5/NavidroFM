#!/bin/bash
set -e


umask 000


PYTHON_PATH=$(which python3)

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
export SYNC_SCHEDULE="${SYNC_SCHEDULE}"
export TZ="${TZ}"
export PATH="/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
EOF

chmod +x /app/cron-env.sh

# Only set up cron if at least one playlist is enabled
if [ "${RECOMMENDED}" = "true" ] || [ "${MIX}" = "true" ] || [ "${LIBRARY}" = "true" ]; then

    if [ -n "${SYNC_SCHEDULE}" ]; then
        SCHEDULE="${SYNC_SCHEDULE}"
    else

        SCHEDULE="0 20 * * *" 
        
        if [ "${RECOMMENDED}" = "true" ]; then
            SCHEDULE="${RECOMMENDED_SCHEDULE:-0 20 * * *}"
        elif [ "${MIX}" = "true" ]; then
            SCHEDULE="${MIX_SCHEDULE:-0 20 * * *}"
        elif [ "${LIBRARY}" = "true" ]; then
            SCHEDULE="${LIBRARY_SCHEDULE:-0 20 * * *}"
        fi
    fi
    

    cat > /app/cron-wrapper.sh << 'WRAPPER_EOF'
#!/bin/bash
source /app/cron-env.sh
/usr/local/bin/python3 /app/app.py all >> /var/log/cron.log 2>&1
WRAPPER_EOF
    
    chmod +x /app/cron-wrapper.sh
    

    echo "${SCHEDULE} /app/cron-wrapper.sh" > /etc/cron.d/lastfm-sync
    

    chmod 0644 /etc/cron.d/lastfm-sync
    

    crontab /etc/cron.d/lastfm-sync
    echo "NavidroFM starting."
    echo "Cron job configured successfully"
else
    echo "No playlists enabled"
fi


if [ "${RUN_ON_STARTUP}" = "true" ]; then
    if [ "${RECOMMENDED}" = "true" ] || [ "${MIX}" = "true" ] || [ "${LIBRARY}" = "true" ]; then
        echo ""
        echo "=========================================="
        echo "Running initial sync..."
        echo "=========================================="
        echo ""
        ${PYTHON_PATH} /app/app.py all 2>&1
        echo ""
        echo "=========================================="
        echo "Initial sync completed"
        echo "=========================================="
    else
        echo ""
        echo "No playlists enabled. Set RECOMMENDED, MIX, or LIBRARY to 'true' in docker-compose.yml"
        echo ""
    fi
fi


echo ""
if [ "${RECOMMENDED}" = "true" ] || [ "${MIX}" = "true" ] || [ "${LIBRARY}" = "true" ]; then
    echo "Starting cron daemon..."
    echo "Next sync scheduled for: ${SCHEDULE}"
    echo ""
    

    cron
    

    tail -f /var/log/cron.log
else
    echo "No playlists enabled and no cron jobs configured."
    echo "Container will exit. Enable at least one playlist in docker-compose.yml"
    exit 1
fi