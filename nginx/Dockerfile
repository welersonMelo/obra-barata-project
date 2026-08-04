FROM nginx:1.19-alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/templates/nginx.conf.template
COPY generate-internal-cert.sh /docker-entrypoint.d/15-generate-internal-cert.sh

RUN chmod +x /docker-entrypoint.d/15-generate-internal-cert.sh
