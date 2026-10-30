# CoreDent - offsite PostgreSQL backup job (Railway cron service).
#
# Deliberately NOT based on coredent-api/Dockerfile. pg_dump refuses to dump a
# server whose major version is newer than its own, and the API image's Debian
# base carries an older postgresql-client than the server. The official postgres
# image guarantees the client matches, and keeps a full database dump off the
# API container's CPU and IO.
#
# TARGET MUST BE >= THE SERVER'S MAJOR VERSION. The deployed Railway Postgres
# runs 18 (ghcr.io/railwayapp-templates/postgres-ssl:18). Bump this in the same
# change as any server upgrade, or every backup run fails with
# "server version mismatch".
FROM postgres:18

# AWS CLI v2 via the official installer rather than the distro package: the
# Debian "awscli" package tracks v1 and is not present on every base release.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip /var/lib/apt/lists/*

COPY backup-to-s3.sh /usr/local/bin/backup-to-s3.sh
RUN chmod +x /usr/local/bin/backup-to-s3.sh

# One-shot: the platform runs this on a schedule and the process must exit.
# A cron service that keeps running would be charged as an always-on service
# and would never report a failed run.
CMD ["/usr/local/bin/backup-to-s3.sh"]
