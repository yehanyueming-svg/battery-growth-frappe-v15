ARG SOURCE_IMAGE=battery-growth:v15.120.0-build
FROM ${SOURCE_IMAGE}

USER root
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh /usr/local/bin/start.sh
USER frappe
