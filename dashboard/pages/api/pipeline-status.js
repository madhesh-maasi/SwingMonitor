import path from 'path';
import fs from 'fs';

function getDb() {
  try {
    const Database = require('better-sqlite3');
    const dbPath = path.join(process.cwd(), '..', 'data', 'history.db');
    if (!fs.existsSync(dbPath)) return null;
    return new Database(dbPath, { readonly: true });
  } catch {
    return null;
  }
}

export default function handler(req, res) {
  const flagPath = path.join(process.cwd(), '..', 'pipeline', 'running.flag');
  const running  = fs.existsSync(flagPath);

  const today = new Date().toISOString().slice(0, 10);

  const db = getDb();
  let lastDate = null;
  let upToDate = false;

  if (db) {
    try {
      const row = db.prepare('SELECT MAX(date) as d FROM candidates_log').get();
      lastDate = row?.d ?? null;
      upToDate = lastDate === today;
    } catch {
      // ignore
    } finally {
      db.close();
    }
  }

  res.status(200).json({ running, upToDate, lastDate, today });
}
