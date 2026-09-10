import { mkdir, copyFile, rm } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
await rm('dist', { recursive:true, force:true });
await mkdir('dist/assets', { recursive:true });
const result=spawnSync(process.env.TSC_BIN || 'tsc', ['-p','tsconfig.json'], {stdio:'inherit',shell:process.platform==='win32'});
if (result.status !== 0) process.exit(result.status || 1);
await copyFile('index.html','dist/index.html');
await copyFile('src/styles.css','dist/assets/styles.css');
console.log('Built RAGOps web client -> dist/');
