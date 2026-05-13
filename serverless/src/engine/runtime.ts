// 실행 흐름:
// HTTP 요청 → gateway.ts (URL에서 ownerId/funcName 추출)
//           → DB에서 Function 조회 + HTTP 트리거 유효성 검사
//           → executionService.runFunction() (FunctionRequest 빌드)
//           → executeFunction() (isolated-vm 샌드박스에서 사용자 handler 실행)
//           → 결과를 HTTP 응답으로 반환
import ivm from "isolated-vm";
import * as esbuild from "esbuild";
import { lookup } from "dns/promises";
import { isIPv4 } from "net";
import * as http from "http";
import * as https from "https";

function isPrivateIP(ip: string): boolean {
  if (isIPv4(ip)) {
    const parts = ip.split(".").map(Number);
    const [a, b] = parts;
    return (
      a === 127 ||
      a === 10 ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      (a === 169 && b === 254) ||
      (a === 100 && b >= 64 && b <= 127) ||
      a === 0
    );
  }
  const lower = ip.toLowerCase();
  return (
    lower === "::1" ||
    lower.startsWith("fc") ||
    lower.startsWith("fd") ||
    lower.startsWith("fe80:") ||
    lower.startsWith("::ffff:")
  );
}

// esbuild로 TS/JS → CJS 변환. isolated-vm의 eval()은 ESM을 지원하지 않으므로
// `export default` 같은 ESM 구문을 CJS `exports.default =`로 바꿔야 한다.
export async function compileTypeScript(code: string): Promise<string> {
  const result = await esbuild.transform(code, {
    loader: "ts",
    target: "es2022",
    format: "cjs",
  });
  return result.code;
}

export async function compileJavaScript(code: string): Promise<string> {
  const result = await esbuild.transform(code, {
    loader: "js",
    target: "es2022",
    format: "cjs",
  });
  return result.code;
}

export interface ExecutionResult {
  status: "success" | "error" | "timeout";
  body: string;
  statusCode: number;
  headers: Record<string, string>;
  logs: string[];
  error?: string;
  duration: number;
}

export interface FunctionRequest {
  method: string;
  url: string;
  headers: Record<string, string>;
  body: string | null;
}

export async function executeFunction(
  code: string,
  runtime: "javascript" | "typescript",
  request: FunctionRequest,
  envVars: Record<string, string>,
  options: { timeout: number; memoryLimit: number },
  compiledCode?: string | null
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const logs: string[] = [];
  let isolate: ivm.Isolate | null = null;

  try {
    let execCode = code;
    if (runtime === "typescript") {
      // compiledCode가 있으면 재컴파일 없이 사용 (함수 저장 시 미리 컴파일됨)
      execCode = compiledCode ?? await compileTypeScript(code);
    } else {
      // JavaScript도 CJS로 변환 필요 — `export default` ESM 구문은 eval()에서 SyntaxError
      execCode = compiledCode ?? await compileJavaScript(code);
    }

    isolate = new ivm.Isolate({ memoryLimit: options.memoryLimit });
    const context = await isolate.createContext();
    const jail = context.global;

    await jail.set("__logs", new ivm.ExternalCopy(logs).copyInto());
    await context.eval(`
      const console = {
        log: (...args) => { __logs.push('[LOG] ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')); },
        warn: (...args) => { __logs.push('[WARN] ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')); },
        error: (...args) => { __logs.push('[ERROR] ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')); },
      };
    `);

    await jail.set("__env", new ivm.ExternalCopy(envVars).copyInto());
    await context.eval(`const env = __env;`);

    const fetchCallback = new ivm.Reference(async function (url: string, options?: string) {
      let parsed: URL;
      try {
        parsed = new URL(url);
      } catch {
        throw new Error(`Invalid URL: ${url}`);
      }
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error(`Blocked URL: ${url}`);
      }
      const hostname = parsed.hostname;
      const host = hostname.startsWith("[") ? hostname.slice(1, -1) : hostname;

      let resolvedIP: string;
      if (isIPv4(host) || host.includes(":")) {
        resolvedIP = host;
      } else {
        try {
          const result = await lookup(host);
          resolvedIP = result.address;
        } catch {
          throw new Error(`Failed to resolve hostname: ${hostname}`);
        }
      }

      if (isPrivateIP(resolvedIP)) {
        throw new Error(`Blocked URL: ${url}`);
      }

      // DNS Rebinding(TOCTOU) 방지: 검증한 IP로 직접 소켓 연결을 맺고,
      // Host 헤더와 TLS SNI(servername)는 원래 호스트네임을 사용한다.
      // fetch(url)를 그대로 호출하면 내부적으로 DNS가 재조회되어 검증을 우회할 수 있다.
      const opts: { method?: string; headers?: Record<string, string>; body?: string } =
        options ? JSON.parse(options) : {};
      const isHttps = parsed.protocol === "https:";
      const port = parsed.port ? Number(parsed.port) : (isHttps ? 443 : 80);
      const reqHeaders: Record<string, string> = {};
      for (const [k, v] of Object.entries(opts.headers ?? {})) {
        if (k.toLowerCase() !== "host") reqHeaders[k] = v;
      }
      reqHeaders["Host"] = parsed.host;
      const body = opts.body;
      if (body !== undefined && body !== null && reqHeaders["Content-Length"] === undefined) {
        reqHeaders["Content-Length"] = String(Buffer.byteLength(body));
      }

      const response = await new Promise<{
        status: number;
        statusText: string;
        headers: Record<string, string>;
        body: string;
      }>((resolve, reject) => {
        const mod = isHttps ? https : http;
        const req = mod.request(
          {
            host: resolvedIP,
            port,
            method: opts.method ?? "GET",
            path: parsed.pathname + parsed.search,
            headers: reqHeaders,
            servername: isHttps ? host : undefined,
          },
          (res) => {
            const chunks: Buffer[] = [];
            res.on("data", (chunk: Buffer) => chunks.push(chunk));
            res.on("end", () => {
              const respHeaders: Record<string, string> = {};
              for (const [k, v] of Object.entries(res.headers)) {
                if (v === undefined) continue;
                respHeaders[k] = Array.isArray(v) ? v.join(", ") : String(v);
              }
              resolve({
                status: res.statusCode ?? 0,
                statusText: res.statusMessage ?? "",
                headers: respHeaders,
                body: Buffer.concat(chunks).toString("utf8"),
              });
            });
          }
        );
        req.on("error", reject);
        if (body !== undefined && body !== null) req.write(body);
        req.end();
      });

      return JSON.stringify(response);
    });
    await jail.set("__fetchRef", fetchCallback);
    await context.eval(`
      async function fetch(url, options) {
        const result = await __fetchRef.apply(undefined, [url, options ? JSON.stringify(options) : undefined], { result: { promise: true } });
        const parsed = JSON.parse(result);
        return {
          ok: parsed.status >= 200 && parsed.status < 300,
          status: parsed.status,
          statusText: parsed.statusText,
          headers: parsed.headers,
          text: async () => parsed.body,
          json: async () => JSON.parse(parsed.body),
        };
      }
    `);

    await context.eval(`
      class Response {
        constructor(body, init = {}) {
          this._body = body ?? '';
          this.status = init.status ?? 200;
          this.headers = init.headers ?? {};
        }
      }
    `);

    await jail.set("__request", new ivm.ExternalCopy(request).copyInto());

    // CJS 래퍼: esbuild가 변환한 코드는 exports/module.exports를 사용한다.
    // __request는 gateway(HTTP 트리거) 또는 execute 라우트(수동 실행)에서 전달된 요청 정보다.
    // 사용자 코드가 `export default async function handler(request) { ... }` 형태이면
    // esbuild가 `exports.default = handler`로 변환하므로 handlerFn = exports.default로 찾는다.
    const wrappedCode = `
      const exports = {};
      const module = { exports };
      ${execCode}

      (async () => {
        // __request: { method, url, headers, body } — HTTP 요청 또는 수동 실행 페이로드
        const req = __request;
        const request = {
          method: req.method,
          url: req.url,
          headers: req.headers,
          body: req.body,
          // json()/text()는 body를 파싱하는 편의 메서드
          json: () => JSON.parse(req.body || '{}'),
          text: () => req.body || '',
        };

        // esbuild CJS 변환 시 module.exports = __toCommonJS(stdin_exports) 로 참조가 교체됨.
        // 그 결과 exports 는 여전히 {} 이고, module.exports 는 { __esModule: true, default: handler } 가 됨.
        // 따라서 module.exports.default → module.exports(함수 직접) → exports.default 순서로 탐색해야 한다.
        const mod = module.exports;
        const handlerFn =
          (mod && typeof mod.default === 'function' ? mod.default : null) ||
          (typeof mod === 'function' ? mod : null) ||
          (typeof exports.default === 'function' ? exports.default : null) ||
          (typeof handler === 'function' ? handler : null);
        if (!handlerFn) {
          throw new Error('No handler function found. Define: export default async function handler(request) { ... }');
        }

        // handler를 호출하면 Response 인스턴스를 반환해야 한다.
        // Response는 샌드박스에 주입된 커스텀 클래스: new Response(body, { status, headers })
        const response = await handlerFn(request);
        return JSON.stringify({
          body: response._body ?? String(response),
          status: response.status ?? 200,
          headers: response.headers ?? {},
        });
      })();
    `;

    const result = await context.eval(wrappedCode, {
      timeout: options.timeout,
      promise: true,
    });

    const capturedLogs = await context.eval(`JSON.stringify(__logs)`);
    const parsedLogs: string[] = JSON.parse(capturedLogs as string);
    const parsed = JSON.parse(result as string);

    return {
      status: "success",
      body: parsed.body,
      statusCode: parsed.status,
      headers: parsed.headers,
      logs: parsedLogs,
      duration: Date.now() - startTime,
    };
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    const isTimeout = errorMessage.includes("Script execution timed out");
    return {
      status: isTimeout ? "timeout" : "error",
      body: isTimeout ? "Function execution timed out" : errorMessage,
      statusCode: 500,
      headers: {},
      logs,
      error: errorMessage,
      duration: Date.now() - startTime,
    };
  } finally {
    if (isolate) isolate.dispose();
  }
}
