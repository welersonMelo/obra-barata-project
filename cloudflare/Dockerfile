FROM cloudflare/cloudflared:2026.3.0 AS cloudflared

FROM alpine:3.20

RUN apk add --no-cache ca-certificates

COPY --from=cloudflared /usr/local/bin/cloudflared /usr/local/bin/cloudflared
COPY run-with-internal-ca.sh /usr/local/bin/run-with-internal-ca.sh

RUN chmod +x /usr/local/bin/run-with-internal-ca.sh

ENTRYPOINT ["/usr/local/bin/run-with-internal-ca.sh"]
CMD ["version"]
