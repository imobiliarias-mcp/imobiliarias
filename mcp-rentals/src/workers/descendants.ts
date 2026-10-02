import { readdirSync, readFileSync } from 'node:fs';

const marker_name = 'RENTAL_WORKER_LIFETIME';
/** Mark a trusted worker so inherited descendants remain identifiable after setsid. */
export function worker_environment(environment: NodeJS.ProcessEnv, identity: string): NodeJS.ProcessEnv {
  return {...environment, [marker_name]: identity};
}
/** Find only processes inheriting this worker's unique, nonsecret lifetime marker. */
export function marked_descendants(identity: string): number[] {
  const marker = Buffer.from(`${marker_name}=${identity}\0`);
  return readdirSync('/proc').filter(name => /^\d+$/.test(name)).filter(name => inherits_marker(name, marker)).map(Number);
}
function inherits_marker(pid: string, marker: Buffer): boolean {
  try { return readFileSync(`/proc/${pid}/environ`).includes(marker); }
  catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (['ENOENT', 'ESRCH', 'EACCES', 'EPERM'].includes(code ?? '')) return false;
    throw error;
  }
}
