import {
  DEFAULT_GOOGLE_APPS_SCRIPT_URL,
  normalizeTeamRoster,
} from '../config/teamConfig';
import {
  ActivityEvent,
  AuthStatusResponse,
  Competition,
  MissionStatus,
  StorageConfig,
  TeamMember,
} from '../types/mission';

const STORAGE_KEYS = {
  CONFIG_V2: 'kryptonix_star_command_prod_config_v2',
  CONFIG_V1: 'kryptonix_star_command_config_v1',
  SESSION_TOKEN: 'kryptonix_star_command_session_token_v2',
  SESSION_PIN: 'kryptonix_star_command_session_pin_v2',
};

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(
    /\/+$/,
    ''
  ) || '';

export function getStorageConfig(): StorageConfig {
  const fixedUrl = DEFAULT_GOOGLE_APPS_SCRIPT_URL.trim();

  // If a permanent Google Apps Script URL is configured in teamConfig.ts or VITE_GOOGLE_APPS_SCRIPT_URL,
  // always lock to Google Sheets mode so users never have to enter the sheet link on any device.
  if (fixedUrl) {
    return {
      provider: 'apps_script',
      appsScriptUrl: fixedUrl,
      lastSyncedAt: null,
    };
  }

  const isGitHubPages =
    typeof window !== 'undefined' &&
    window.location.hostname.endsWith('github.io');

  try {
    const rawV2 = localStorage.getItem(STORAGE_KEYS.CONFIG_V2);
    if (rawV2) {
      const parsed = JSON.parse(rawV2) as Partial<StorageConfig>;
      if (parsed.appsScriptUrl && parsed.appsScriptUrl.trim()) {
        return {
          provider: 'apps_script',
          appsScriptUrl: parsed.appsScriptUrl.trim(),
          lastSyncedAt: parsed.lastSyncedAt || null,
        };
      }
      if (parsed.provider === 'express_api' && !isGitHubPages) {
        return {
          provider: 'express_api',
          appsScriptUrl: '',
          lastSyncedAt: parsed.lastSyncedAt || null,
        };
      }
    }

    const rawV1 = localStorage.getItem(STORAGE_KEYS.CONFIG_V1);
    if (rawV1) {
      const parsedV1 = JSON.parse(rawV1);
      if (
        parsedV1 &&
        typeof parsedV1.appsScriptUrl === 'string' &&
        parsedV1.appsScriptUrl.trim()
      ) {
        const migrated: StorageConfig = {
          provider: 'apps_script',
          appsScriptUrl: parsedV1.appsScriptUrl.trim(),
          lastSyncedAt: parsedV1.lastSyncedAt || null,
        };
        localStorage.setItem(STORAGE_KEYS.CONFIG_V2, JSON.stringify(migrated));
        return migrated;
      }
    }
  } catch {
    // ignore storage read error
  }

  return {
    provider: isGitHubPages ? 'apps_script' : 'express_api',
    appsScriptUrl: '',
    lastSyncedAt: null,
  };
}

export function saveStorageConfig(config: StorageConfig): void {
  localStorage.setItem(STORAGE_KEYS.CONFIG_V2, JSON.stringify(config));
}

export function getStoredSessionToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEYS.SESSION_TOKEN);
  } catch {
    return null;
  }
}

export function getStoredSessionPin(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEYS.SESSION_PIN) || '';
  } catch {
    return '';
  }
}

export function setStoredSessionToken(
  token: string | null,
  pinForAppsScript?: string
): void {
  try {
    if (!token) {
      sessionStorage.removeItem(STORAGE_KEYS.SESSION_TOKEN);
      sessionStorage.removeItem(STORAGE_KEYS.SESSION_PIN);
    } else {
      sessionStorage.setItem(STORAGE_KEYS.SESSION_TOKEN, token);
      if (pinForAppsScript !== undefined) {
        sessionStorage.setItem(STORAGE_KEYS.SESSION_PIN, pinForAppsScript);
      }
    }
  } catch {
    // ignore storage write error
  }
}

/**
 * Helper to invoke Google Apps Script Web App with POST JSON payload.
 */
async function callAppsScript(
  appsScriptUrl: string,
  payload: Record<string, unknown>
): Promise<Record<string, any>> {
  const response = await fetch(appsScriptUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(
      `Google Apps Script returned HTTP ${response.status}. Verify Web App deployment permissions.`
    );
  }
  const data = await response.json();
  return data;
}

/**
 * Checks backend health, whether a Team PIN is configured on the server,
 * and whether the current session is valid.
 * Compatible with both v1 (PIN-per-request) and v2 (token-based) Google Apps Script deployments.
 */
export async function checkAuthStatus(
  config: StorageConfig
): Promise<AuthStatusResponse> {
  const token = getStoredSessionToken() || '';
  const storedPin = getStoredSessionPin();

  if (config.provider === 'apps_script') {
    if (!config.appsScriptUrl) {
      throw new Error(
        'Google Apps Script Web App URL is not configured. Click "Backend" in the top right to paste your /exec URL or switch to the Backend API Server.'
      );
    }

    const data = await callAppsScript(config.appsScriptUrl, {
      action: 'AUTH_STATUS',
      token,
      pin: storedPin,
    });

    // v2 Apps Script returns { ok: true, pinConfigured, authenticated }
    if (data.ok && typeof data.pinConfigured === 'boolean') {
      return {
        ok: true,
        pinConfigured: Boolean(data.pinConfigured),
        authenticated: Boolean(data.authenticated),
        expiresAt: data.expiresAt,
        storageBackend: 'google_sheets_proxy',
        appsScriptConnected: true,
      };
    }

    // v1 Apps Script checks verifyPin(payload.pin) first on every action:
    // - If storedPin was valid, v1 reaches the end of doPost and returns "Unknown action: AUTH_STATUS"
    // - If storedPin was empty/invalid, v1 returns "Invalid Team PIN. Access denied by Star Command Apps Script."
    const errText = String(data.error || '');
    if (errText.includes('Unknown action')) {
      return {
        ok: true,
        pinConfigured: true,
        authenticated: Boolean(storedPin),
        storageBackend: 'google_sheets_proxy',
        appsScriptConnected: true,
      };
    }

    if (errText.toLowerCase().includes('invalid team pin')) {
      // The Apps Script endpoint is reachable and online, and has a PIN configured!
      return {
        ok: true,
        pinConfigured: true,
        authenticated: false,
        storageBackend: 'google_sheets_proxy',
        appsScriptConnected: true,
      };
    }

    throw new Error(errText || 'Failed to check Google Apps Script status.');
  }

  const response = await fetch(`${API_BASE}/api/auth/status`, {
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    throw new Error(
      `Backend API unreachable (HTTP ${response.status}). Ensure the server is running.`
    );
  }

  return (await response.json()) as AuthStatusResponse;
}

/**
 * Initializes the Team PIN on the server when no PIN hash has been configured yet.
 */
export async function setupInitialServerPin(
  pin: string,
  config: StorageConfig
): Promise<{ token: string; expiresAt: string }> {
  const cleaned = pin.trim();
  if (config.provider === 'apps_script') {
    const data = await callAppsScript(config.appsScriptUrl, {
      action: 'SETUP_PIN',
      pin: cleaned,
    });
    if (!data.ok || !data.token) {
      throw new Error(
        data.error || 'Failed to initialize PIN on Google Apps Script.'
      );
    }
    setStoredSessionToken(data.token, cleaned);
    return { token: data.token, expiresAt: data.expiresAt || '' };
  }

  const response = await fetch(`${API_BASE}/api/auth/setup-pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pin: cleaned }),
  });

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to initialize Team PIN.');
  }

  setStoredSessionToken(data.token);
  return { token: data.token, expiresAt: data.expiresAt };
}

/**
 * Authenticates the user's Team PIN on the server and stores the returned session token.
 * Supports both v2 (LOGIN) and v1 (VERIFY_PIN) Google Apps Script endpoints.
 */
export async function loginWithTeamPin(
  pin: string,
  config: StorageConfig
): Promise<{
  ok: boolean;
  token?: string;
  error?: string;
  retryAfterSeconds?: number;
}> {
  const cleaned = pin.trim();
  if (!cleaned) {
    return { ok: false, error: 'Please enter the KRYPTØNIX Team PIN.' };
  }

  if (config.provider === 'apps_script') {
    if (!config.appsScriptUrl) {
      return {
        ok: false,
        error: 'Google Apps Script Web App URL is missing.',
      };
    }
    try {
      const data = await callAppsScript(config.appsScriptUrl, {
        action: 'VERIFY_PIN',
        pin: cleaned,
      });

      if (data.ok) {
        const token = data.token || `gas-session-${Date.now()}`;
        setStoredSessionToken(token, cleaned);
        return { ok: true, token };
      }

      // If it's a v2 script that only has LOGIN instead of VERIFY_PIN
      if (String(data.error || '').includes('Unknown action')) {
        const loginData = await callAppsScript(config.appsScriptUrl, {
          action: 'LOGIN',
          pin: cleaned,
        });
        if (loginData.ok) {
          const token = loginData.token || `gas-session-${Date.now()}`;
          setStoredSessionToken(token, cleaned);
          return { ok: true, token };
        }
        return {
          ok: false,
          error: loginData.error || 'Invalid Team PIN.',
          retryAfterSeconds: loginData.retryAfterSeconds,
        };
      }

      return {
        ok: false,
        error: data.error || 'Invalid Team PIN.',
        retryAfterSeconds: data.retryAfterSeconds,
      };
    } catch (err) {
      return {
        ok: false,
        error:
          err instanceof Error
            ? err.message
            : 'Unable to reach Google Apps Script backend.',
      };
    }
  }

  try {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: cleaned }),
    });
    const data = await response.json();
    if (response.ok && data.ok && data.token) {
      setStoredSessionToken(data.token);
      return { ok: true, token: data.token };
    }
    return {
      ok: false,
      error: data.error || 'Invalid Team PIN.',
      retryAfterSeconds: data.retryAfterSeconds,
    };
  } catch (err) {
    return {
      ok: false,
      error:
        err instanceof Error
          ? `Backend connection failed: ${err.message}`
          : 'Unable to reach authentication server.',
    };
  }
}

/**
 * Revokes the active session token on the server and clears client session storage.
 */
export async function logoutSession(config: StorageConfig): Promise<void> {
  const token = getStoredSessionToken();
  const pin = getStoredSessionPin();
  setStoredSessionToken(null);
  if (!token) return;

  try {
    if (config.provider === 'apps_script' && config.appsScriptUrl) {
      await callAppsScript(config.appsScriptUrl, {
        action: 'LOGOUT',
        token,
        pin,
      });
      return;
    }
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    // Ignore network error during logout cleanup
  }
}

/**
 * Changes the server-side Team PIN hash (requires current PIN verification).
 */
export async function changeServerPin(
  currentPin: string,
  newPin: string,
  config: StorageConfig
): Promise<void> {
  const token = getStoredSessionToken();
  if (!token) throw new Error('Unauthorized session. Please log in again.');

  if (config.provider === 'apps_script') {
    const data = await callAppsScript(config.appsScriptUrl, {
      action: 'CHANGE_PIN',
      token,
      pin: currentPin.trim(),
      currentPin: currentPin.trim(),
      newPin: newPin.trim(),
    });
    if (!data.ok) {
      if (String(data.error || '').includes('Unknown action')) {
        throw new Error(
          'To change the PIN on your Google Apps Script v1 deployment, update TEAM_PIN in Apps Script -> Project Settings -> Script Properties, or update Code.gs to v2.'
        );
      }
      throw new Error(data.error || 'Failed to update Team PIN.');
    }
    setStoredSessionToken(token, newPin.trim());
    return;
  }

  const response = await fetch(`${API_BASE}/api/auth/change-pin`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      currentPin: currentPin.trim(),
      newPin: newPin.trim(),
    }),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to update Team PIN.');
  }
}

/**
 * Fetches all competitions, official team member configurations, and audit activity logs
 * strictly from the authenticated server / Google Sheets backend.
 */
export async function fetchMissionData(config: StorageConfig): Promise<{
  competitions: Competition[];
  teamMembers: TeamMember[];
  activityLog: ActivityEvent[];
}> {
  const token = getStoredSessionToken();
  const pin = getStoredSessionPin();
  if (!token) {
    throw new Error('UNAUTHENTICATED');
  }

  if (config.provider === 'apps_script') {
    if (!config.appsScriptUrl) {
      throw new Error('Google Apps Script Web App URL is not configured.');
    }
    const data = await callAppsScript(config.appsScriptUrl, {
      action: 'GET_ALL',
      token,
      pin,
    });
    if (!data.ok) {
      if (
        data.unauthorized ||
        String(data.error || '').toLowerCase().includes('invalid team pin')
      ) {
        setStoredSessionToken(null);
        throw new Error('UNAUTHENTICATED');
      }
      throw new Error(
        data.error || 'Failed to retrieve records from Google Sheets.'
      );
    }

    const rawCompetitions: Competition[] = Array.isArray(data.competitions)
      ? data.competitions
      : [];
    const normalizedRoster = normalizeTeamRoster(data.teamMembers);
    const rawActivity: ActivityEvent[] = Array.isArray(data.activityLog)
      ? data.activityLog
      : [];

    // If the Google Sheet TeamMembers tab didn't have the 4 official names yet, sync them once
    const sheetNames = Array.isArray(data.teamMembers)
      ? data.teamMembers.map((m: any) => m?.name).join('|')
      : '';
    const officialNames = normalizedRoster.map((m) => m.name).join('|');
    if (sheetNames !== officialNames) {
      callAppsScript(config.appsScriptUrl, {
        action: 'SYNC_ALL',
        token,
        pin,
        competitions: rawCompetitions,
        teamMembers: normalizedRoster,
        activityLog: rawActivity,
      }).catch(() => {});
    }

    return {
      competitions: rawCompetitions,
      teamMembers: normalizedRoster,
      activityLog: rawActivity,
    };
  }

  const response = await fetch(`${API_BASE}/api/competitions`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (response.status === 401) {
    setStoredSessionToken(null);
    throw new Error('UNAUTHENTICATED');
  }

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(
      data.error || 'Failed to load competition records from server.'
    );
  }

  return {
    competitions: Array.isArray(data.competitions) ? data.competitions : [],
    teamMembers: normalizeTeamRoster(data.teamMembers),
    activityLog: Array.isArray(data.activityLog) ? data.activityLog : [],
  };
}

/**
 * Helper for Google Apps Script (supports both v1 SYNC_ALL and v2 granular actions).
 */
async function mutateAppsScriptData(
  config: StorageConfig,
  mutator: (current: {
    competitions: Competition[];
    teamMembers: TeamMember[];
    activityLog: ActivityEvent[];
  }) => {
    targetCompetition?: Competition;
    competitions: Competition[];
    teamMembers: TeamMember[];
    activityLog: ActivityEvent[];
  }
): Promise<{
  competition: Competition;
  competitions: Competition[];
  teamMembers: TeamMember[];
  activityLog: ActivityEvent[];
}> {
  const token = getStoredSessionToken();
  const pin = getStoredSessionPin();
  if (!token) throw new Error('UNAUTHENTICATED');

  const current = await fetchMissionData(config);
  const next = mutator(current);

  const syncRes = await callAppsScript(config.appsScriptUrl, {
    action: 'SYNC_ALL',
    token,
    pin,
    competitions: next.competitions,
    teamMembers: next.teamMembers,
    activityLog: next.activityLog.slice(0, 50),
  });

  if (!syncRes.ok) {
    if (
      syncRes.unauthorized ||
      String(syncRes.error || '').toLowerCase().includes('invalid team pin')
    ) {
      setStoredSessionToken(null);
      throw new Error('UNAUTHENTICATED');
    }
    throw new Error(syncRes.error || 'Failed to write changes to Google Sheets.');
  }

  return {
    competition: next.targetCompetition!,
    competitions: next.competitions,
    teamMembers: next.teamMembers,
    activityLog: next.activityLog,
  };
}

function generateNextMissionId(list: Competition[]): string {
  let maxNum = 0;
  list.forEach((c) => {
    const m = /^KRYP-(\d+)$/i.exec(c.id);
    if (m) {
      const n = Number(m[1]);
      if (n > maxNum) maxNum = n;
    }
  });
  return `KRYP-${String(maxNum + 1).padStart(3, '0')}`;
}

/**
 * Creates a new competition record on the backend and returns the updated state.
 */
export async function createCompetitionRecord(
  config: StorageConfig,
  payload: {
    name: string;
    organiser: string;
    competitionUrl: string;
    deadline: string;
    status: MissionStatus;
    progressDocUrl: string;
    notes: string;
  }
): Promise<{
  competition: Competition;
  competitions: Competition[];
  activityLog: ActivityEvent[];
}> {
  const token = getStoredSessionToken();
  if (!token) throw new Error('UNAUTHENTICATED');

  if (config.provider === 'apps_script') {
    return mutateAppsScriptData(config, (curr) => {
      const dup = curr.competitions.find(
        (c) =>
          !c.archived &&
          c.name.trim().toLowerCase() === payload.name.trim().toLowerCase()
      );
      if (dup) {
        throw new Error(
          `An active competition named "${dup.name}" (${dup.id}) already exists.`
        );
      }
      const nowIso = new Date().toISOString();
      const created: Competition = {
        id: generateNextMissionId(curr.competitions),
        name: payload.name.trim(),
        organiser: payload.organiser.trim(),
        competitionUrl: payload.competitionUrl.trim(),
        deadline: payload.deadline.trim(),
        status: payload.status,
        progressDocUrl: payload.progressDocUrl.trim(),
        notes: payload.notes.trim(),
        createdAt: nowIso,
        updatedAt: nowIso,
        archived: false,
      };
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}`,
        competitionId: created.id,
        competitionName: created.name,
        action: 'CREATED',
        summary: `Registered mission (${created.status})`,
        timestamp: nowIso,
      };
      return {
        targetCompetition: created,
        competitions: [created, ...curr.competitions],
        teamMembers: curr.teamMembers,
        activityLog: [event, ...curr.activityLog].slice(0, 50),
      };
    });
  }

  const response = await fetch(`${API_BASE}/api/competitions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 401) {
    setStoredSessionToken(null);
    throw new Error('UNAUTHENTICATED');
  }

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to create competition.');
  }

  return {
    competition: data.competition,
    competitions: data.competitions,
    activityLog: data.activityLog,
  };
}

/**
 * Updates an existing competition record on the backend.
 */
export async function updateCompetitionRecord(
  config: StorageConfig,
  id: string,
  payload: {
    name: string;
    organiser: string;
    competitionUrl: string;
    deadline: string;
    status: MissionStatus;
    progressDocUrl: string;
    notes: string;
  }
): Promise<{
  competition: Competition;
  competitions: Competition[];
  activityLog: ActivityEvent[];
}> {
  const token = getStoredSessionToken();
  if (!token) throw new Error('UNAUTHENTICATED');

  if (config.provider === 'apps_script') {
    return mutateAppsScriptData(config, (curr) => {
      const idx = curr.competitions.findIndex((c) => c.id === id);
      if (idx === -1) throw new Error(`Competition ${id} not found.`);
      const nowIso = new Date().toISOString();
      const updated: Competition = {
        ...curr.competitions[idx],
        name: payload.name.trim(),
        organiser: payload.organiser.trim(),
        competitionUrl: payload.competitionUrl.trim(),
        deadline: payload.deadline.trim(),
        status: payload.status,
        progressDocUrl: payload.progressDocUrl.trim(),
        notes: payload.notes.trim(),
        updatedAt: nowIso,
      };
      const nextComps = [...curr.competitions];
      nextComps[idx] = updated;
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}`,
        competitionId: updated.id,
        competitionName: updated.name,
        action: 'UPDATED',
        summary: `Updated mission details (${updated.status})`,
        timestamp: nowIso,
      };
      return {
        targetCompetition: updated,
        competitions: nextComps,
        teamMembers: curr.teamMembers,
        activityLog: [event, ...curr.activityLog].slice(0, 50),
      };
    });
  }

  const response = await fetch(
    `${API_BASE}/api/competitions/${encodeURIComponent(id)}`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }
  );

  if (response.status === 401) {
    setStoredSessionToken(null);
    throw new Error('UNAUTHENTICATED');
  }

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to update competition.');
  }

  return {
    competition: data.competition,
    competitions: data.competitions,
    activityLog: data.activityLog,
  };
}

/**
 * Updates a competition's status (ONGOING, SUBMITTED, COMPLETED) on the backend.
 */
export async function updateCompetitionStatusRecord(
  config: StorageConfig,
  id: string,
  status: MissionStatus
): Promise<{
  competition: Competition;
  competitions: Competition[];
  activityLog: ActivityEvent[];
}> {
  const token = getStoredSessionToken();
  if (!token) throw new Error('UNAUTHENTICATED');

  if (config.provider === 'apps_script') {
    return mutateAppsScriptData(config, (curr) => {
      const idx = curr.competitions.findIndex((c) => c.id === id);
      if (idx === -1) throw new Error(`Competition ${id} not found.`);
      const prevStatus = curr.competitions[idx].status;
      const nowIso = new Date().toISOString();
      const updated: Competition = {
        ...curr.competitions[idx],
        status,
        updatedAt: nowIso,
      };
      const nextComps = [...curr.competitions];
      nextComps[idx] = updated;
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}`,
        competitionId: updated.id,
        competitionName: updated.name,
        action: 'STATUS_CHANGED',
        summary: `Status changed from ${prevStatus} to ${status}`,
        timestamp: nowIso,
      };
      return {
        targetCompetition: updated,
        competitions: nextComps,
        teamMembers: curr.teamMembers,
        activityLog: [event, ...curr.activityLog].slice(0, 50),
      };
    });
  }

  const response = await fetch(
    `${API_BASE}/api/competitions/${encodeURIComponent(id)}/status`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ status }),
    }
  );

  if (response.status === 401) {
    setStoredSessionToken(null);
    throw new Error('UNAUTHENTICATED');
  }

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to update status.');
  }

  return {
    competition: data.competition,
    competitions: data.competitions,
    activityLog: data.activityLog,
  };
}

/**
 * Archives or restores a competition record on the backend.
 */
export async function toggleCompetitionArchiveRecord(
  config: StorageConfig,
  id: string,
  archived: boolean
): Promise<{
  competition: Competition;
  competitions: Competition[];
  activityLog: ActivityEvent[];
}> {
  const token = getStoredSessionToken();
  if (!token) throw new Error('UNAUTHENTICATED');

  if (config.provider === 'apps_script') {
    return mutateAppsScriptData(config, (curr) => {
      const idx = curr.competitions.findIndex((c) => c.id === id);
      if (idx === -1) throw new Error(`Competition ${id} not found.`);
      const nowIso = new Date().toISOString();
      const updated: Competition = {
        ...curr.competitions[idx],
        archived,
        status: archived ? 'COMPLETED' : curr.competitions[idx].status,
        updatedAt: nowIso,
      };
      const nextComps = [...curr.competitions];
      nextComps[idx] = updated;
      const event: ActivityEvent = {
        id: `ACT-${Date.now()}`,
        competitionId: updated.id,
        competitionName: updated.name,
        action: archived ? 'ARCHIVED' : 'RESTORED',
        summary: archived
          ? `Archived completed mission (${updated.id})`
          : `Restored mission (${updated.id}) to active roster`,
        timestamp: nowIso,
      };
      return {
        targetCompetition: updated,
        competitions: nextComps,
        teamMembers: curr.teamMembers,
        activityLog: [event, ...curr.activityLog].slice(0, 50),
      };
    });
  }

  const response = await fetch(
    `${API_BASE}/api/competitions/${encodeURIComponent(id)}/archive`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ archived }),
    }
  );

  if (response.status === 401) {
    setStoredSessionToken(null);
    throw new Error('UNAUTHENTICATED');
  }

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to update archive status.');
  }

  return {
    competition: data.competition,
    competitions: data.competitions,
    activityLog: data.activityLog,
  };
}

/**
 * Persists updated roles, focus areas, and optional profile URLs for the 4 official KRYPTØNIX members.
 */
export async function updateTeamRosterRecord(
  config: StorageConfig,
  teamMembers: TeamMember[]
): Promise<TeamMember[]> {
  const token = getStoredSessionToken();
  const pin = getStoredSessionPin();
  if (!token) throw new Error('UNAUTHENTICATED');

  const normalized = normalizeTeamRoster(teamMembers);

  if (config.provider === 'apps_script') {
    const current = await fetchMissionData(config);
    const data = await callAppsScript(config.appsScriptUrl, {
      action: 'SYNC_ALL',
      token,
      pin,
      competitions: current.competitions,
      teamMembers: normalized,
      activityLog: current.activityLog,
    });
    if (!data.ok) {
      if (
        data.unauthorized ||
        String(data.error || '').toLowerCase().includes('invalid team pin')
      ) {
        setStoredSessionToken(null);
        throw new Error('UNAUTHENTICATED');
      }
      throw new Error(
        data.error || 'Failed to update team roster in Google Sheets.'
      );
    }
    return normalized;
  }

  const response = await fetch(`${API_BASE}/api/team`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ teamMembers: normalized }),
  });

  if (response.status === 401) {
    setStoredSessionToken(null);
    throw new Error('UNAUTHENTICATED');
  }

  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || 'Failed to save team member configuration.');
  }

  return normalizeTeamRoster(data.teamMembers);
}

export const GOOGLE_APPS_SCRIPT_TEMPLATE = `/**
 * KRYPTØNIX — STAR COMMAND GOOGLE APPS SCRIPT BACKEND (Code.gs)
 *
 * Supports both Script Property TEAM_PIN and salted SHA-256 PIN_HASH verification.
 * Automatically provisions the 4 official KRYPTØNIX members:
 * M KRISHNA · V JEYSHREE · SUBHA SHREE R · LAKSHMANAN G
 */

const SHEET_COMPETITIONS = 'Competitions';
const SHEET_TEAM = 'TeamMembers';
const SHEET_ACTIVITY = 'ActivityLog';

const OFFICIAL_MEMBERS = [
  { id: 'KRYP-M01', slotLabel: 'OPERATOR 01', name: 'M KRISHNA', role: '', focusArea: '', profileUrl: '' },
  { id: 'KRYP-M02', slotLabel: 'OPERATOR 02', name: 'V JEYSHREE', role: '', focusArea: '', profileUrl: '' },
  { id: 'KRYP-M03', slotLabel: 'OPERATOR 03', name: 'SUBHA SHREE R', role: '', focusArea: '', profileUrl: '' },
  { id: 'KRYP-M04', slotLabel: 'OPERATOR 04', name: 'LAKSHMANAN G', role: '', focusArea: '', profileUrl: '' }
];

function ensureSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  let compSheet = ss.getSheetByName(SHEET_COMPETITIONS);
  if (!compSheet) {
    compSheet = ss.insertSheet(SHEET_COMPETITIONS);
    compSheet.appendRow([
      'id', 'name', 'organiser', 'competitionUrl', 'deadline',
      'status', 'progressDocUrl', 'notes', 'createdAt', 'updatedAt', 'archived'
    ]);
  }

  let teamSheet = ss.getSheetByName(SHEET_TEAM);
  if (!teamSheet) {
    teamSheet = ss.insertSheet(SHEET_TEAM);
    teamSheet.appendRow(['id', 'slotLabel', 'name', 'role', 'focusArea', 'profileUrl']);
    OFFICIAL_MEMBERS.forEach(function(m) {
      teamSheet.appendRow([m.id, m.slotLabel, m.name, m.role, m.focusArea, m.profileUrl]);
    });
  }

  let actSheet = ss.getSheetByName(SHEET_ACTIVITY);
  if (!actSheet) {
    actSheet = ss.insertSheet(SHEET_ACTIVITY);
    actSheet.appendRow(['id', 'competitionId', 'competitionName', 'action', 'summary', 'timestamp']);
  }

  return { compSheet: compSheet, teamSheet: teamSheet, actSheet: actSheet };
}

function verifyPin(inputPin) {
  const props = PropertiesService.getScriptProperties();
  const expectedPin = props.getProperty('TEAM_PIN');
  if (!expectedPin) {
    // If TEAM_PIN is not set yet in Script Properties, set it on first login
    if (inputPin && String(inputPin).trim().length >= 4) {
      props.setProperty('TEAM_PIN', String(inputPin).trim());
      return true;
    }
    return false;
  }
  return String(inputPin || '').trim() === String(expectedPin).trim();
}

function sheetToObjects(sheet) {
  const rows = sheet.getDataRange().getValues();
  if (rows.length <= 1) return [];
  const headers = rows[0];
  return rows.slice(1).map(function(row) {
    const obj = {};
    headers.forEach(function(h, i) {
      if (h === 'archived') {
        obj[h] = row[i] === true || String(row[i]).toLowerCase() === 'true';
      } else if (h === 'deadline' && row[i] instanceof Date) {
        obj[h] = Utilities.formatDate(row[i], Session.getScriptTimeZone(), 'yyyy-MM-dd');
      } else {
        obj[h] = row[i] !== undefined && row[i] !== null ? String(row[i]) : '';
      }
    });
    return obj;
  });
}

function writeObjectsToSheet(sheet, headers, items) {
  sheet.clearContents();
  const matrix = [headers];
  items.forEach(function(item) {
    matrix.push(headers.map(function(h) { return item[h] !== undefined ? item[h] : ''; }));
  });
  sheet.getRange(1, 1, matrix.length, headers.length).setValues(matrix);
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.tryLock(10000);
  try {
    const payload = JSON.parse(e.postData.contents || '{}');
    const action = payload.action;

    if (action === 'AUTH_STATUS') {
      const props = PropertiesService.getScriptProperties();
      const hasPin = Boolean(props.getProperty('TEAM_PIN'));
      const isAuth = hasPin && Boolean(payload.pin) && verifyPin(payload.pin);
      return jsonResponse({ ok: true, pinConfigured: hasPin || true, authenticated: isAuth });
    }

    if (!verifyPin(payload.pin)) {
      return jsonResponse({ ok: false, error: 'Invalid Team PIN. Access denied by Star Command Apps Script.' });
    }

    const sheets = ensureSheets();

    if (action === 'VERIFY_PIN' || action === 'LOGIN') {
      return jsonResponse({ ok: true, token: Utilities.getUuid() });
    }

    if (action === 'GET_ALL') {
      return jsonResponse({
        ok: true,
        competitions: sheetToObjects(sheets.compSheet),
        teamMembers: sheetToObjects(sheets.teamSheet),
        activityLog: sheetToObjects(sheets.actSheet)
      });
    }

    if (action === 'SYNC_ALL') {
      const compHeaders = ['id', 'name', 'organiser', 'competitionUrl', 'deadline', 'status', 'progressDocUrl', 'notes', 'createdAt', 'updatedAt', 'archived'];
      const teamHeaders = ['id', 'slotLabel', 'name', 'role', 'focusArea', 'profileUrl'];
      const actHeaders = ['id', 'competitionId', 'competitionName', 'action', 'summary', 'timestamp'];

      if (Array.isArray(payload.competitions)) {
        writeObjectsToSheet(sheets.compSheet, compHeaders, payload.competitions);
      }
      if (Array.isArray(payload.teamMembers)) {
        writeObjectsToSheet(sheets.teamSheet, teamHeaders, payload.teamMembers);
      }
      if (Array.isArray(payload.activityLog)) {
        writeObjectsToSheet(sheets.actSheet, actHeaders, payload.activityLog);
      }
      return jsonResponse({ ok: true, updatedAt: new Date().toISOString() });
    }

    return jsonResponse({ ok: false, error: 'Unknown action: ' + action });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
`;
