// Cloudflare Worker entry point for DocShield — PAID mode (Cloudflare Containers).
// Used by wrangler.containers.jsonc. The default free deployment uses index.js.
//
//   Browser -> this Worker (static assets + /api/*) -> DocShieldBackendContainer (Container)
//                                                    -> FastAPI OCR / CV pipeline
//            and D1 (redacted case records, reviewer tokens, audit log)

import { Container, getContainer } from "@cloudflare/containers";
import { handleRequest } from "./app.js";
import { purgeExpired } from "./cases.js";

const BACKEND_PORT = 8000;
// One named instance: the pipeline runs with bounded concurrency inside the
// container, and requests queue there rather than fanning out.
const BACKEND_INSTANCE = "docshield-backend-v1";
// Model warm-up (EasyOCR + dlib) happens before uvicorn binds the port.
const PORT_READY_TIMEOUT_MS = 180_000;

export class DocShieldBackendContainer extends Container {
  defaultPort = BACKEND_PORT;
  sleepAfter = "15m";
  // The image contains every model it needs; it never needs outbound internet.
  enableInternet = false;

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      PORT: String(BACKEND_PORT),
      DOCSHIELD_ENV: "production",
      DOCSHIELD_MODE: env.DOCSHIELD_MODE || "PROTOTYPE",
      PERSISTENCE_MODE: "none",
      // Edge rate limiting is authoritative; keep the container limiter as a backstop.
      RATE_LIMIT_ANALYZE_PER_MINUTE: "30",
    };
  }

  async fetch(request) {
    await this.startAndWaitForPorts({
      ports: BACKEND_PORT,
      cancellationOptions: { portReadyTimeoutMS: PORT_READY_TIMEOUT_MS },
    });
    return this.containerFetch(request, BACKEND_PORT);
  }

  onError(error) {
    log("container_error", { error: String(error && error.message ? error.message : error) });
    throw error;
  }
}

function log(event, fields) {
  console.log(JSON.stringify({ event, ...fields }));
}

const deps = {
  backendFetch: (request, env) => getContainer(env.DOCSHIELD_BACKEND, BACKEND_INSTANCE).fetch(request),
  log,
};

export default {
  fetch(request, env) {
    return handleRequest(request, env, deps);
  },

  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(
      purgeExpired(env.DB).then((deleted) => log("retention_purge", { deleted }))
    );
  },
};
