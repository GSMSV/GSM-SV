# 배포 방식 개선을 위해 과거에 사용하던 배포 방식을 설명합니다.

## 기존 배포
- 수동으로 git repository를 clone, pull함
- Dockerfile, docker-compose.yml은 git repository가 아닌 배포 VM 로컬에만 존재
- https://github.com/GSMSV/GSM-SV/pull/100 해당 PR 이전 상태의 폴더 구조를 사용함.
### 기존 Dockerfile, docker-compose.yml
./DockerFile
```
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir psycopg2-binary && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads/avatars backups

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"

```
./docker-compose.yml
```
services:
  db:
    image: postgres:16-alpine
    restart: always
    command: postgres -c log_connections=on -c log_disconnections=on
    environment:
      POSTGRES_USER: gsmsv
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: gsmsv
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gsmsv"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build: .
    restart: always
    depends_on:
      db:
        condition: service_healthy
    env_file: .env
    environment:
      DATABASE_URL: postgresql://gsmsv:${DB_PASSWORD}@db:5432/gsmsv
    volumes:
      - uploads:/app/uploads
      - backups:/app/backups
    ports:
      - "127.0.0.1:8000:8000"

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_DISCORD_URL: ${NEXT_PUBLIC_DISCORD_URL}
        NEXT_PUBLIC_API_URL: http://backend:8000
    restart: always
    depends_on:
      - backend
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
    ports:
      - "127.0.0.1:3000:3000"

volumes:
  pgdata:
  uploads:
  backups:
```
./frontend/Dockerfile
```
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NEXT_PUBLIC_DISCORD_URL
ENV NEXT_PUBLIC_DISCORD_URL=$NEXT_PUBLIC_DISCORD_URL


RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.mjs ./

EXPOSE 3000

CMD ["npm", "start"]
```

## 개선 해야할 내용들

### phase 1

- https://github.com/GSMSV/GSM-SV/pull/100 에서 바뀐 폴더 구조에 따라 Dockerfile, docker-compose.yml 변경
- 변경된 새 Dockerfile과 docker-compose.yml을 git repository에 명시적으로 등록후 커밋

### phase 2

- github actions를 통해 CD 구축
- BE, FE 각각의 폴더 변경에 따라 개별 CD workflow 작성
- BE, FE 이외 전역 파일 변경시 전역 CD 발생 ex) docker-compose.yml
- 전역 CD시 .agents, .claude, .codex 같은 실제 코드와 관련 없는 경우 제외
- github self hosted runner 사용을 기준으로 CD 파이프라인 작성해야함
