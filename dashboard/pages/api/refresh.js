import { spawn } from 'child_process';
import path from 'path';

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const pipelineDir = path.join(process.cwd(), '..', 'pipeline');
  const scriptPath  = path.join(pipelineDir, 'run_pipeline.py');

  const child = spawn('python3', [scriptPath], {
    cwd: pipelineDir,
    detached: true,
    stdio: 'ignore',
  });

  child.unref();

  res.status(202).json({ message: 'Pipeline started', pid: child.pid });
}
