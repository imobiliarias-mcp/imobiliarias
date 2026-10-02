import { spawn, type ChildProcess } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { marked_descendants, worker_environment } from './descendants.js';

export interface WorkerCommand {python: string; args: string[]; directory: string; environment?: NodeJS.ProcessEnv}
const lifetimes = new WeakMap<ChildProcess, string>();

/** Launch only a trusted prevalidated command, never a shell or user-selected path. */
export function launch_worker(command: WorkerCommand): ChildProcess {
  const identity = randomUUID();
  const env = worker_environment(command.environment ?? process.env, identity);
  const child = spawn(command.python, command.args, {cwd: command.directory, env, detached: true, stdio: ['pipe', 'pipe', 'pipe'], shell: false});
  lifetimes.set(child, identity);
  return child;
}
/** Kill the group and inherited descendants, including processes starting new sessions. */
export function terminate_worker(child: ChildProcess): void {
  if (child.pid) signal_process(-child.pid);
  const identity = lifetimes.get(child);
  if (!identity) return;
  for (const pid of marked_descendants(identity)) signal_process(pid);
}
function signal_process(pid: number): void {
  try { process.kill(pid, 'SIGKILL'); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
}
