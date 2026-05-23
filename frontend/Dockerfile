# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: base — install dependencies with layer-cache optimisation
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS base
WORKDIR /app

# Copy manifests first so dependency layer is cached independently of source
COPY package*.json ./
RUN npm ci --frozen-lockfile

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: development — hot reload via Next.js dev server
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS development
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: builder — compile the production bundle
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS builder
COPY . .
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: production — minimal runtime image
# NOTE: next.config.ts must include `output: 'standalone'` for server.js to
# be emitted.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS production
WORKDIR /app

ENV NODE_ENV=production

# Create a non-root user for security
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# Copy only what Next.js standalone output needs
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
