# Build preparation only. No build/push/deployment is invoked by prepare.yaml.
FROM docker.io/library/nextcloud:35.0.2-apache@sha256:d88929dc8386420b8963f86cabb667fdaf733eef9dcf8fc98e226801a32c023c
COPY user_oidc.tar.gz /opt/perkforge/user_oidc.tar.gz
RUN echo '6f13fa0477144a6812d8648626c64cee91807d1d0b60ca41424543086b9e2775  /opt/perkforge/user_oidc.tar.gz' | sha256sum -c - \
 && mkdir -p /opt/perkforge/apps \
 && tar -xzf /opt/perkforge/user_oidc.tar.gz -C /opt/perkforge/apps --no-same-owner \
 && test -f /opt/perkforge/apps/user_oidc/vendor/autoload.php \
 && test -f /opt/perkforge/apps/user_oidc/appinfo/signature.json \
 && chmod -R a-w /opt/perkforge/apps
# Deliberately outside /usr/src/nextcloud and the persistent custom_apps mount.
# No entrypoint or hook installs/enables this app automatically.
