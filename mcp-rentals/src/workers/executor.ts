import { worker_response, type WorkerResponse } from '../contracts/responses.js';
import { launch_worker, terminate_worker, type WorkerCommand } from './process.js';

export interface WorkerLimits {timeout: number; stdout: number; stderr: number; stdin: number}
/** Executes a single bounded JSON transaction in an isolated provider process. */
export class WorkerExecutor {
  constructor(private limits: WorkerLimits) {}
  async run(command: WorkerCommand, request: unknown, signal: AbortSignal): Promise<WorkerResponse> {
    if (signal.aborted) throw new Error('cancelled');
    const input = JSON.stringify(request);
    if (Buffer.byteLength(input) > this.limits.stdin) throw new Error('output_limit');
    return this.execute(command, input, signal);
  }
  private execute(command: WorkerCommand, input: string, signal: AbortSignal): Promise<WorkerResponse> {
    const child = launch_worker(command);
    return new Promise((resolve, reject) => {
      const state = {output: '', stderr: 0, failure: '', bytes: 0};
      const fail = (code: string) => { state.failure ||= code; terminate_worker(child); };
      const cancel = () => fail('cancelled');
      const timer = setTimeout(() => fail('timeout'), this.limits.timeout);
      signal.addEventListener('abort', cancel, {once: true});
      this.observe(child, state, fail);
      child.once('close', code => { clearTimeout(timer); signal.removeEventListener('abort', cancel); terminate_worker(child); this.finish(state, code, resolve, reject); });
      child.stdin!.end(input);
      if (signal.aborted) cancel();
    });
  }
  private observe(child: ReturnType<typeof launch_worker>, state: {output: string; bytes: number; stderr: number; failure: string}, fail: (code: string) => void): void {
    child.once('error', () => fail('worker_error'));
    child.stdin!.on('error', () => fail('worker_error'));
    const decoder = new TextDecoder('utf-8', {fatal: true});
    child.stdout!.on('data', (chunk: Buffer) => this.accept_chunk(state, decoder, chunk, fail));
    child.stdout!.once('end', () => {
      try { state.output += decoder.decode(); }
      catch { fail('invalid_output'); }
    });
    child.stderr!.on('data', (chunk: Buffer) => { state.stderr += chunk.length; if (state.stderr > this.limits.stderr) fail('output_limit'); });
  }
  private accept_chunk(state: {output: string; bytes: number}, decoder: TextDecoder, chunk: Buffer, fail: (code: string) => void): void {
    state.bytes += chunk.length;
    if (state.bytes > this.limits.stdout) return fail('output_limit');
    try { state.output += decoder.decode(chunk, {stream: true}); }
    catch { fail('invalid_output'); }
  }
  private finish(state: {output: string; failure: string}, code: number | null, resolve: (value: WorkerResponse) => void, reject: (error: Error) => void): void {
    if (state.failure) return reject(new Error(state.failure));
    if (code !== 0) return reject(new Error('worker_error'));
    try { resolve(worker_response.parse(JSON.parse(state.output))); }
    catch { reject(new Error('invalid_output')); }
  }
}
