FROM registry.access.redhat.com/ubi8/nginx-120

# Running in port 8080 by default

# Add application sources
COPY  ./docker/nginx-cache/server.conf "${NGINX_DEFAULT_CONF_PATH}"
COPY ./docker/nginx-cache/http.conf "${NGINX_CONFIGURATION_PATH}"

CMD nginx -g "daemon off; error_log /dev/stdout info;"
