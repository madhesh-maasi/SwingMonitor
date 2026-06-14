import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const pipelineDir = path.join(process.cwd(), '..', 'pipeline');
  const scriptPath  = path.join(pipelineDir, 'run_pipeline.py');
  const flagPath    = path.join(pipelineDir, 'running.flag');

  // Already running
  if (fs.existsSync(flagPath)) {
    return res.status(202).json({ message: 'Already running' });
  }

  try { fs.writeFileSync(flagPath, String(Date.now())); } catch {}

  const child = spawn('python3', [scriptPath], {
    cwd: pipelineDir,
    detached: true,
    stdio: 'ignore',
    env: { ...process.env },
  });

  child.unref();

  res.status(202).json({ message: 'Pipeline started', pid: child.pid });
}
