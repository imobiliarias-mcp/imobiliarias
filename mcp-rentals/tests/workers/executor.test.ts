import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WorkerExecutor } from '../../src/workers/executor.js';
import { WorkerLimiter } from '../../src/workers/limiter.js';

const signal = () => new AbortController().signal;
const command = (source: string) => ({python: process.execPath, args: ['-e', source], directory: process.cwd()});
const valid = 'process.stdin.resume();process.stdin.on("end",()=>console.log(JSON.stringify({version:1,status:"ok",native:{items:[]},display:[]})))';
test('worker accepts only one versioned JSON response', async () => {
  const executor = new WorkerExecutor({timeout: 1000, stdout: 1024, stderr: 128, stdin: 1024});
  const result = await executor.run(command(valid), {version: 1}, signal());
  assert.equal(result.status, 'ok');
  await assert.rejects(executor.run(command('console.log("noise");console.log("{}")'), {}, signal()), /invalid_output/);
});
test('split UTF-8 bytes preserve the native result losslessly', async () => {
  const executor = new WorkerExecutor({timeout: 1000, stdout: 1024, stderr: 128, stdin: 128});
  const source = 'const b=Buffer.from(JSON.stringify({version:1,status:"ok",native:{title:"€"},display:[]}));const i=b.indexOf(Buffer.from("€"));process.stdout.write(b.subarray(0,i+1));setTimeout(()=>process.stdout.write(b.subarray(i+1)),25)';
  const result = await executor.run(command(source), {}, signal());
  assert.equal((result as any).native.title, '€');
});

test('invalid UTF-8 cannot be replaced silently in a native payload', async () => {
  const executor = new WorkerExecutor({timeout: 1000, stdout: 1024, stderr: 128, stdin: 128});
  const source = 'process.stdout.write(Buffer.concat([Buffer.from("{\\\"version\\\":1,\\\"status\\\":\\\"ok\\\",\\\"native\\\":\\\""),Buffer.from([255]),Buffer.from("\\\",\\\"display\\\":[]}")]))';
  await assert.rejects(executor.run(command(source), {}, signal()), /invalid_output/);
});

test('timeout, excess output and cancellation terminate workers', async () => {
  const executor = new WorkerExecutor({timeout: 70, stdout: 128, stderr: 64, stdin: 128});
  await assert.rejects(executor.run(command('setInterval(()=>{},1000)'), {}, signal()), /timeout/);
  await assert.rejects(executor.run(command('console.log("x".repeat(200))'), {}, signal()), /output_limit/);
  const controller = new AbortController();
  const pending = executor.run(command('setInterval(()=>{},1000)'), {}, controller.signal);
  controller.abort();
  await assert.rejects(pending, /cancelled/);
});
test('worker completion also kills a detached grandchild', async () => {
  const executor = new WorkerExecutor({timeout: 1000, stdout: 1024, stderr: 128, stdin: 128});
  const source = 'const {spawn}=require("node:child_process");const c=spawn(process.execPath,["-e","setInterval(()=>{},1000)"],{stdio:"ignore"});console.log(JSON.stringify({version:1,status:"ok",native:{pid:c.pid},display:[]}));process.exit(0)';
  const result = await executor.run(command(source), {}, signal());
  const pid = (result as any).native.pid;
  let alive = true;
  for (let count = 0; count < 20 && alive; count++) {
    try { process.kill(pid, 0); await new Promise(resolve => setTimeout(resolve, 10)); }
    catch { alive = false; }
  }
  assert.equal(alive, false);
});

test('a new-session descendant retaining pipes cannot escape timeout cleanup', async () => {
  const executor = new WorkerExecutor({timeout: 80, stdout: 1024, stderr: 128, stdin: 128});
  const source = 'const {spawn}=require("node:child_process");spawn(process.execPath,["-e","setInterval(()=>{},1000)"],{detached:true,stdio:["ignore",process.stdout,process.stderr]}).unref();setInterval(()=>{},1000)';
  const pending = executor.run(command(source), {}, signal());
  const result = await Promise.race([pending.then(() => 'resolved', error => error.message), new Promise(resolve => setTimeout(() => resolve('hung'), 300))]);
  assert.equal(result, 'timeout');
});

test('global concurrency and per-provider serialization share one limiter', async () => {
  const limiter = new WorkerLimiter(2);
  let running = 0; let maximum = 0; const active = new Set<string>();
  const work = (provider: string) => limiter.run(provider, signal(), async () => {
    assert.equal(active.has(provider), false); active.add(provider);
    running++; maximum = Math.max(maximum, running);
    await new Promise(resolve => setTimeout(resolve, 20));
    running--; active.delete(provider);
    return provider;
  });
  assert.deepEqual(await Promise.all(['a', 'a', 'b', 'c'].map(work)), ['a', 'a', 'b', 'c']);
  assert.equal(maximum, 2);
});
test('cancelled queued work never starts and shutdown rejects pending jobs', async () => {
  const limiter = new WorkerLimiter(1);
  const controller = new AbortController();
  const active = limiter.run('a', signal(), () => new Promise(resolve => setTimeout(resolve, 30)));
  const pending = limiter.run('b', controller.signal, async () => assert.fail('must not start'));
  controller.abort();
  await assert.rejects(pending, /cancelled/); await active;
  limiter.close();
  await assert.rejects(limiter.run('a', signal(), async () => 1), /shutdown/);
});
