import crypto from 'crypto';
import dotenv from 'dotenv';
import express, { NextFunction, Request, Response } from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import {
  getDefaultTeamRoster,
  normalizeTeamRoster,
} from './src/config/teamConfig.ts';
import {
  ActivityEvent,
  Competition,
  MissionStatus,
  TeamMember,
} from './src/types/mission.ts';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = Number(process.env.PORT) || 3000;
const DATA_DIR = path.resolve(__dirname, 'data');
const DATA_FILE = path.join(DATA_DIR, 'kryptonix-store.json');

const SESSION_TTL_MS = 12 * 60 * 60 * 1000; // 12 hours
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 60 seconds
const MAX_FAILED_ATTEMPTS = 5;

interface PersistentStoreData {
  pinSalt?: string;
  pinHash?: string;
  sessionSecret: string;
  nextSequenceNumber: number;
  competitions: Competition[];
  teamMembers: TeamMember[];
  activityLog: ActivityEvent[];
}

// Active non-revoked session tokens (tokenId -> expiresAtMs)
const activeSessions = new Map<string, number>();

// Login rate limiter state (ipKey -> { failures, lockUntilMs })
const loginRateLimits = new Map<
  string,
  { failures: number; lockUntilMs: number }
>();

// Serialized write lock to prevent concurrent file/Sheets race conditions
let writeQueue: Promise<void> = Promise.resolve();

function ensureStoreLoaded(): PersistentStoreData {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }

  if (fs.existsSync(DATA_FILE)) {
    try {
      const raw = fs.readFileSync(DATA_FILE, 'utf-8');
      const parsed = JSON.parse(raw) as Partial<PersistentStoreData>;
      return {
        pinSalt: parsed.pinSalt,
        pinHash: parsed.pinHash,
        sessionSecret:
          process.env.SESSION_SECRET ||
          parsed.sessionSecret ||
          crypto.randomBytes(32).toString('hex'),
        nextSequenceNumber:
          typeof parsed.nextSequenceNumber === 'number' &&
          parsed.nextSequenceNumber >= 1
            ? parsed.nextSequenceNumber
            : 1,
        competitions: Array.isArray(parsed.competitions)
          ? parsed.competitions
          : [],
        teamMembers: normalizeTeamRoster(parsed.teamMembers),
        activityLog: Array.isArray(parsed.activityLog)
          ? parsed.activityLog
          : [],
      };
    } catch {
      // If corrupted, initialize clean empty store
    }
  }

  const initial: PersistentStoreData = {
    sessionSecret:
      process.env.SESSION_SECRET || crypto.randomBytes(32).toString('hex'),
    nextSequenceNumber: 1,
    competitions: [], // Starts strictly empty; zero sample data
    teamMembers: getDefaultTeamRoster(),
    activityLog: [],
  };

  // If KRYPTONIX_INITIAL_PIN is provided in server environment, hash it immediately
  const envPin = process.env.KRYPTONIX_TEAM_PIN?.trim();
  if (envPin && envPin.length >= 4) {
    const salt = crypto.randomBytes(16).toString('hex');
    const derived = crypto.scryptSync(envPin, salt, 64).toString('hex');
    initial.pinSalt = salt;
    initial.pinHash = derived;
  }

  saveStoreSync(initial);
  return initial;
}

function saveStoreSync(data: PersistentStoreData): void {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  const tmpFile = `${DATA_FILE}.tmp`;
  fs.writeFileSync(tmpFile, JSON.stringify(data, null, 2), 'utf-8');
  fs.renameSync(tmpFile, DATA_FILE);
}

let store: PersistentStoreData = ensureStoreLoaded();

function enqueueStoreWrite(mutator: () => Promise<void> | void): Promise<void> {
  const next = writeQueue.then(async () => {
    await mutator();
    saveStoreSync(store);
  });
  writeQueue = next.catch(() => {});
  return next;
}

function isPinConfigured(): boolean {
  if (process.env.KRYPTONIX_PIN_HASH && process.env.KRYPTONIX_PIN_SALT) {
    return true;
  }
  return Boolean(store.pinHash && store.pinSalt);
}

function verifyPinHash(candidatePin: string): boolean {
  const salt = process.env.KRYPTONIX_PIN_SALT || store.pinSalt;
  const expectedHashHex = process.env.KRYPTONIX_PIN_HASH || store.pinHash;
  if (!salt || !expectedHashHex) return false;

  const candidateBuf = crypto.scryptSync(candidatePin, salt, 64);
  const expectedBuf = Buffer.from(expectedHashHex, 'hex');
  if (candidateBuf.length !== expectedBuf.length) return false;
  return crypto.timingSafeEqual(candidateBuf, expectedBuf);
}

function createSignedSessionToken(): { token: string; expiresAt: string } {
  const tokenId = crypto.randomBytes(24).toString('hex');
  const expMs = Date.now() + SESSION_TTL_MS;
  activeSessions.set(tokenId, expMs);

  const payload = `${tokenId}.${expMs}`;
  const sig = crypto
    .createHmac('sha256', store.sessionSecret)
    .update(payload)
    .digest('hex');

  return {
    token: `${payload}.${sig}`,
    expiresAt: new Date(expMs).toISOString(),
  };
}

function verifySessionToken(rawToken: string | undefined): {
  valid: boolean;
  tokenId?: string;
  expiresAt?: string;
} {
  if (!rawToken) return { valid: false };
  const parts = rawToken.split('.');
  if (parts.length !== 3) return { valid: false };

  const [tokenId, expStr, providedSig] = parts;
  const expMs = Number(expStr);
  if (!tokenId || isNaN(expMs) || Date.now() > expMs) {
    if (tokenId) activeSessions.delete(tokenId);
    return { valid: false };
  }

  const sessionExp = activeSessions.get(tokenId);
  if (!sessionExp || Date.now() > sessionExp) {
    activeSessions.delete(tokenId);
    return { valid: false };
  }

  const payload = `${tokenId}.${expStr}`;
  const expectedSig = crypto
    .createHmac('sha256', store.sessionSecret)
    .update(payload)
    .digest('hex');

  const a = Buffer.from(providedSig, 'hex');
  const b = Buffer.from(expectedSig, 'hex');
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return { valid: false };
  }

  return {
    valid: true,
    tokenId,
    expiresAt: new Date(expMs).toISOString(),
  };
}

function extractBearerToken(req: Request): string | undefined {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) return undefined;
  return authHeader.slice('Bearer '.length).trim();
}

function requireAuth(req: Request, res: Response, next: NextFunction): void {
  const token = extractBearerToken(req);
  const check = verifySessionToken(token);
  if (!check.valid) {
    res.status(401).json({
      ok: false,
      error: 'Session expired or unauthorized. Please log in with your KRYPTØNIX Team PIN.',
    });
    return;
  }
  next();
}

// Validation helpers
function isValidHttpUrlServer(val: string): boolean {
  if (!val) return true;
  try {
    const parsed = new URL(val);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function isValidDateStrServer(val: string): boolean {
  if (!val) return true;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(val);
  if (!match) return false;
  const y = Number(match[1]);
  const m = Number(match[2]) - 1;
  const d = Number(match[3]);
  const dt = new Date(y, m, d);
  return (
    dt.getFullYear() === y && dt.getMonth() === m && dt.getDate() === d
  );
}

const VALID_STATUSES: MissionStatus[] = ['ONGOING', 'SUBMITTED', 'COMPLETED'];

function validateCompetitionPayload(body: Record<string, unknown>): {
  valid: boolean;
  error?: string;
  sanitized?: {
    name: string;
    organiser: string;
    competitionUrl: string;
    deadline: string;
    status: MissionStatus;
    progressDocUrl: string;
    notes: string;
  };
} {
  const name = typeof body.name === 'string' ? body.name.trim() : '';
  const organiser =
    typeof body.organiser === 'string' ? body.organiser.trim() : '';
  const competitionUrl =
    typeof body.competitionUrl === 'string' ? body.competitionUrl.trim() : '';
  const deadline =
    typeof body.deadline === 'string' ? body.deadline.trim() : '';
  const status = body.status as MissionStatus;
  const progressDocUrl =
    typeof body.progressDocUrl === 'string' ? body.progressDocUrl.trim() : '';
  const notes = typeof body.notes === 'string' ? body.notes.trim() : '';

  if (!name || name.length < 2) {
    return {
      valid: false,
      error: 'Competition name is required (minimum 2 characters).',
    };
  }
  if (name.length > 160) {
    return {
      valid: false,
      error: 'Competition name cannot exceed 160 characters.',
    };
  }
  if (organiser.length > 160) {
    return {
      valid: false,
      error: 'Organiser name cannot exceed 160 characters.',
    };
  }
  if (!VALID_STATUSES.includes(status)) {
    return {
      valid: false,
      error: 'Status must be ONGOING, SUBMITTED, or COMPLETED.',
    };
  }
  if (!isValidDateStrServer(deadline)) {
    return {
      valid: false,
      error: 'Deadline must be a valid calendar date in YYYY-MM-DD format.',
    };
  }
  if (!isValidHttpUrlServer(competitionUrl)) {
    return {
      valid: false,
      error: 'Competition URL must be a valid http:// or https:// address.',
    };
  }
  if (!isValidHttpUrlServer(progressDocUrl)) {
    return {
      valid: false,
      error: 'Progress document URL must be a valid http:// or https:// address.',
    };
  }
  if (notes.length > 4000) {
    return {
      valid: false,
      error: 'Notes cannot exceed 4000 characters.',
    };
  }

  return {
    valid: true,
    sanitized: {
      name,
      organiser,
      competitionUrl,
      deadline,
      status,
      progressDocUrl,
      notes,
    },
  };
}

async function startServer() {
  const app = express();
  app.use(express.json({ limit: '256kb' }));

  // Optional CORS support if frontend is hosted on GitHub Pages calling this backend
  const allowedOrigin = process.env.ALLOWED_ORIGIN || '*';
  app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', allowedOrigin);
    res.setHeader(
      'Access-Control-Allow-Headers',
      'Content-Type, Authorization'
    );
    res.setHeader(
      'Access-Control-Allow-Methods',
      'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    );
    if (req.method === 'OPTIONS') {
      res.status(204).end();
      return;
    }
    next();
  });

  // 1. Check Auth & Server Configuration Status
  app.get('/api/auth/status', (req, res) => {
    const token = extractBearerToken(req);
    const check = verifySessionToken(token);
    res.json({
      ok: true,
      pinConfigured: isPinConfigured(),
      authenticated: check.valid,
      expiresAt: check.expiresAt,
      storageBackend: process.env.GOOGLE_APPS_SCRIPT_URL
        ? 'google_sheets_proxy'
        : 'server_persistent_store',
      appsScriptConnected: Boolean(process.env.GOOGLE_APPS_SCRIPT_URL),
    });
  });

  // 2. Initial Server-Side PIN Setup (only allowed when no PIN hash exists yet)
  app.post('/api/auth/setup-pin', async (req, res) => {
    if (isPinConfigured()) {
      res.status(403).json({
        ok: false,
        error: 'Team PIN is already configured on the server. Please log in with your existing PIN.',
      });
      return;
    }

    const pin = typeof req.body?.pin === 'string' ? req.body.pin.trim() : '';
    if (pin.length < 4 || pin.length > 64) {
      res.status(400).json({
        ok: false,
        error: 'Team PIN must be between 4 and 64 characters.',
      });
      return;
    }

    await enqueueStoreWrite(() => {
      const salt = crypto.randomBytes(16).toString('hex');
      const derived = crypto.scryptSync(pin, salt, 64).toString('hex');
      store.pinSalt = salt;
      store.pinHash = derived;
    });

    const session = createSignedSessionToken();
    res.json({
      ok: true,
      token: session.token,
      expiresAt: session.expiresAt,
    });
  });

  // 3. Server-Side PIN Login with Rate Limiting
  app.post('/api/auth/login', (req, res) => {
    const clientKey = req.ip || 'global';
    const now = Date.now();
    const rateRecord = loginRateLimits.get(clientKey);

    if (rateRecord && now < rateRecord.lockUntilMs) {
      const retrySec = Math.ceil((rateRecord.lockUntilMs - now) / 1000);
      res.status(429).json({
        ok: false,
        error: `Too many failed login attempts. Try again in ${retrySec} seconds.`,
        retryAfterSeconds: retrySec,
      });
      return;
    }

    if (!isPinConfigured()) {
      res.status(400).json({
        ok: false,
        error: 'Team PIN has not been initialized yet. Complete first-time PIN setup.',
      });
      return;
    }

    const pin = typeof req.body?.pin === 'string' ? req.body.pin.trim() : '';
    if (!pin) {
      res.status(400).json({
        ok: false,
        error: 'Please enter your KRYPTØNIX Team PIN.',
      });
      return;
    }

    const isValid = verifyPinHash(pin);
    if (!isValid) {
      const failures = (rateRecord?.failures || 0) + 1;
      const lockUntilMs =
        failures >= MAX_FAILED_ATTEMPTS ? now + RATE_LIMIT_WINDOW_MS : 0;
      loginRateLimits.set(clientKey, { failures, lockUntilMs });

      if (lockUntilMs > 0) {
        res.status(429).json({
          ok: false,
          error: 'Maximum failed login attempts reached. Terminal locked for 60 seconds.',
          retryAfterSeconds: 60,
        });
        return;
      }

      res.status(401).json({
        ok: false,
        error: `Invalid Team PIN. (${MAX_FAILED_ATTEMPTS - failures} attempts remaining before cooldown)`,
      });
      return;
    }

    loginRateLimits.delete(clientKey);
    const session = createSignedSessionToken();
    res.json({
      ok: true,
      token: session.token,
      expiresAt: session.expiresAt,
    });
  });

  // 4. Logout & Revoke Session Token
  app.post('/api/auth/logout', (req, res) => {
    const token = extractBearerToken(req);
    const check = verifySessionToken(token);
    if (check.tokenId) {
      activeSessions.delete(check.tokenId);
    }
    res.json({ ok: true });
  });

  // 5. Rotate / Change Team PIN (Protected)
  app.post('/api/auth/change-pin', requireAuth, async (req, res) => {
    const currentPin =
      typeof req.body?.currentPin === 'string'
        ? req.body.currentPin.trim()
        : '';
    const newPin =
      typeof req.body?.newPin === 'string' ? req.body.newPin.trim() : '';

    if (!verifyPinHash(currentPin)) {
      res.status(401).json({
        ok: false,
        error: 'Current Team PIN is incorrect.',
      });
      return;
    }

    if (newPin.length < 4 || newPin.length > 64) {
      res.status(400).json({
        ok: false,
        error: 'New Team PIN must be between 4 and 64 characters.',
      });
      return;
    }

    await enqueueStoreWrite(() => {
      const salt = crypto.randomBytes(16).toString('hex');
      const derived = crypto.scryptSync(newPin, salt, 64).toString('hex');
      store.pinSalt = salt;
      store.pinHash = derived;
    });

    res.json({ ok: true });
  });

  // 6. Fetch All Mission Records, Team Roster, and Activity Log (Protected)
  app.get('/api/competitions', requireAuth, (_req, res) => {
    res.json({
      ok: true,
      competitions: store.competitions,
      teamMembers: normalizeTeamRoster(store.teamMembers),
      activityLog: store.activityLog,
      syncedAt: new Date().toISOString(),
    });
  });

  // 7. Create a New Competition (Protected)
  app.post('/api/competitions', requireAuth, async (req, res) => {
    const validation = validateCompetitionPayload(req.body || {});
    if (!validation.valid || !validation.sanitized) {
      res.status(400).json({ ok: false, error: validation.error });
      return;
    }

    const { sanitized } = validation;
    const duplicate = store.competitions.find(
      (c) =>
        !c.archived &&
        c.name.trim().toLowerCase() === sanitized.name.toLowerCase()
    );
    if (duplicate) {
      res.status(409).json({
        ok: false,
        error: `An active competition named "${duplicate.name}" (${duplicate.id}) already exists.`,
      });
      return;
    }

    let createdRecord!: Competition;

    await enqueueStoreWrite(() => {
      const seq = store.nextSequenceNumber;
      store.nextSequenceNumber = seq + 1;
      const id = `KRYP-${String(seq).padStart(3, '0')}`;
      const nowIso = new Date().toISOString();

      createdRecord = {
        id,
        ...sanitized,
        createdAt: nowIso,
        updatedAt: nowIso,
        archived: false,
      };

      store.competitions = [createdRecord, ...store.competitions];
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}-${crypto.randomBytes(2).toString('hex')}`,
        competitionId: createdRecord.id,
        competitionName: createdRecord.name,
        action: 'CREATED',
        summary: `Registered mission (${createdRecord.status})`,
        timestamp: nowIso,
      };
      store.activityLog = [event, ...store.activityLog].slice(0, 50);
    });

    res.status(201).json({
      ok: true,
      competition: createdRecord,
      competitions: store.competitions,
      activityLog: store.activityLog,
    });
  });

  // 8. Update an Existing Competition (Protected)
  app.put('/api/competitions/:id', requireAuth, async (req, res) => {
    const targetId = req.params.id;
    const existingIndex = store.competitions.findIndex(
      (c) => c.id === targetId
    );
    if (existingIndex === -1) {
      res.status(404).json({
        ok: false,
        error: `Competition record ${targetId} not found.`,
      });
      return;
    }

    const validation = validateCompetitionPayload(req.body || {});
    if (!validation.valid || !validation.sanitized) {
      res.status(400).json({ ok: false, error: validation.error });
      return;
    }

    const { sanitized } = validation;
    const duplicateOther = store.competitions.find(
      (c) =>
        c.id !== targetId &&
        !c.archived &&
        c.name.trim().toLowerCase() === sanitized.name.toLowerCase()
    );
    if (duplicateOther) {
      res.status(409).json({
        ok: false,
        error: `Another active competition named "${duplicateOther.name}" (${duplicateOther.id}) already exists.`,
      });
      return;
    }

    let updatedRecord!: Competition;

    await enqueueStoreWrite(() => {
      const current = store.competitions[existingIndex];
      const nowIso = new Date().toISOString();
      updatedRecord = {
        ...current,
        ...sanitized,
        updatedAt: nowIso,
      };
      store.competitions[existingIndex] = updatedRecord;
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}-${crypto.randomBytes(2).toString('hex')}`,
        competitionId: updatedRecord.id,
        competitionName: updatedRecord.name,
        action: 'UPDATED',
        summary: `Updated mission details (${updatedRecord.status})`,
        timestamp: nowIso,
      };
      store.activityLog = [event, ...store.activityLog].slice(0, 50);
    });

    res.json({
      ok: true,
      competition: updatedRecord,
      competitions: store.competitions,
      activityLog: store.activityLog,
    });
  });

  // 9. Update Competition Status (Protected)
  app.patch('/api/competitions/:id/status', requireAuth, async (req, res) => {
    const targetId = req.params.id;
    const status = req.body?.status as MissionStatus;

    if (!VALID_STATUSES.includes(status)) {
      res.status(400).json({
        ok: false,
        error: 'Status must be ONGOING, SUBMITTED, or COMPLETED.',
      });
      return;
    }

    const existingIndex = store.competitions.findIndex(
      (c) => c.id === targetId
    );
    if (existingIndex === -1) {
      res.status(404).json({
        ok: false,
        error: `Competition ${targetId} not found.`,
      });
      return;
    }

    let updatedRecord!: Competition;

    await enqueueStoreWrite(() => {
      const current = store.competitions[existingIndex];
      const prevStatus = current.status;
      const nowIso = new Date().toISOString();
      updatedRecord = {
        ...current,
        status,
        updatedAt: nowIso,
      };
      store.competitions[existingIndex] = updatedRecord;
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}-${crypto.randomBytes(2).toString('hex')}`,
        competitionId: updatedRecord.id,
        competitionName: updatedRecord.name,
        action: 'STATUS_CHANGED',
        summary: `Status changed from ${prevStatus} to ${status}`,
        timestamp: nowIso,
      };
      store.activityLog = [event, ...store.activityLog].slice(0, 50);
    });

    res.json({
      ok: true,
      competition: updatedRecord,
      competitions: store.competitions,
      activityLog: store.activityLog,
    });
  });

  // 10. Archive or Restore Competition (Protected)
  app.patch('/api/competitions/:id/archive', requireAuth, async (req, res) => {
    const targetId = req.params.id;
    const archived = Boolean(req.body?.archived);

    const existingIndex = store.competitions.findIndex(
      (c) => c.id === targetId
    );
    if (existingIndex === -1) {
      res.status(404).json({
        ok: false,
        error: `Competition ${targetId} not found.`,
      });
      return;
    }

    let updatedRecord!: Competition;

    await enqueueStoreWrite(() => {
      const current = store.competitions[existingIndex];
      const nowIso = new Date().toISOString();
      updatedRecord = {
        ...current,
        archived,
        status: archived ? 'COMPLETED' : current.status,
        updatedAt: nowIso,
      };
      store.competitions[existingIndex] = updatedRecord;
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}-${crypto.randomBytes(2).toString('hex')}`,
        competitionId: updatedRecord.id,
        competitionName: updatedRecord.name,
        action: archived ? 'ARCHIVED' : 'RESTORED',
        summary: archived
          ? `Archived completed mission (${updatedRecord.id})`
          : `Restored mission (${updatedRecord.id}) to active roster`,
        timestamp: nowIso,
      };
      store.activityLog = [event, ...store.activityLog].slice(0, 50);
    });

    res.json({
      ok: true,
      competition: updatedRecord,
      competitions: store.competitions,
      activityLog: store.activityLog,
    });
  });

  // 11. Update Official KRYPTØNIX Team Member Role/Profile Config (Protected)
  app.put('/api/team', requireAuth, async (req, res) => {
    const incoming = req.body?.teamMembers;
    if (!Array.isArray(incoming)) {
      res.status(400).json({
        ok: false,
        error: 'teamMembers array is required.',
      });
      return;
    }

    for (const item of incoming) {
      if (
        item?.profileUrl &&
        typeof item.profileUrl === 'string' &&
        item.profileUrl.trim() &&
        !isValidHttpUrlServer(item.profileUrl.trim())
      ) {
        res.status(400).json({
          ok: false,
          error: `Invalid profile URL for ${item.name || 'team member'}. Must start with https:// or http://`,
        });
        return;
      }
    }

    await enqueueStoreWrite(() => {
      store.teamMembers = normalizeTeamRoster(incoming);
    });

    res.json({
      ok: true,
      teamMembers: store.teamMembers,
    });
  });

  // Vite middleware in development, static assets in production
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(
      `KRYPTØNIX Star Command server running on http://0.0.0.0:${PORT}`
    );
  });
}

startServer();
