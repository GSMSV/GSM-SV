import ivm from "isolated-vm";
import * as esbuild from "esbuild";

export async function compileTypeScript(code: string): Promise<string> {
  const result = await esbuild.transform(code, {
    loader: "ts",
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
      execCode = compiledCode ?? await compileTypeScript(code);
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
      let hostname: string;
      try {
        hostname = new URL(url).hostname;
      } catch {
        throw new Error(`Invalid URL: ${url}`);
      }
      const host = hostname.startsWith("[") ? hostname.slice(1, -1) : hostname;
      if (
        /^169\.254\.\d+\.\d+$/.test(host) ||  // IPv4 link-local (cloud IMDS)
        /^fe80:/i.test(host) ||                 // IPv6 link-local
        /^fd00:ec2:/i.test(host)                // AWS IPv6 IMDS
      ) {
        throw new Error(`Blocked URL: ${url}`);
      }
      const opts = options ? JSON.parse(options) : {};
      const res = await fetch(url, opts);
      const body = await res.text();
      return JSON.stringify({
        status: res.status,
        statusText: res.statusText,
        headers: Object.fromEntries(res.headers.entries()),
        body,
      });
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

    const wrappedCode = `
      const exports = {};
      const module = { exports };
      ${execCode}

      (async () => {
        const req = __request;
        const request = {
          method: req.method,
          url: req.url,
          headers: req.headers,
          body: req.body,
          json: () => JSON.parse(req.body || '{}'),
          text: () => req.body || '',
        };

        const handlerFn = exports.default || module.exports || (typeof handler === 'function' ? handler : null);
        if (!handlerFn) {
          throw new Error('No handler function found. Define: export default async function handler(request) { ... }');
        }

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
