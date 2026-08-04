# Obra Barata

Projeto full-stack do Obra Barata com backend FastAPI, frontend React e containerizacao com Docker.

## Estrutura

```text
obra-barata-project/
+-- backend/                  # Backend FastAPI
+-- cloudflare/               # Configuracao opcional de Cloudflare Tunnel
+-- nginx/                    # Proxy Nginx
+-- docker-compose-dev.yml
+-- docker-compose-test.yml
```

## Uso Local

Copie `.env.example` para `.env` e preencha apenas valores locais:

```bash
cp .env.example .env
```

Ambiente de desenvolvimento:

```bash
docker compose -f docker-compose-dev.yml up
```

Ambiente local com tunnel HTTPS:

```bash
docker compose -f docker-compose-test.yml up
```

## Seguranca

Nao publique o arquivo `.env`, tokens de tunnel, chaves de API, certificados privados, logs ou arquivos gerados em `data/`.

## Licenca

Distribuido sob a licenca MIT. Veja `LICENSE`.
