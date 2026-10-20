export type MissionStatus = 'ONGOING' | 'SUBMITTED' | 'COMPLETED';

export type DeadlineCategory =
  | 'OVERDUE'
  | 'DUE_TODAY'
  | 'DUE_SOON'
  | 'UPCOMING'
  | 'NO_DEADLINE';

export interface Competition {
  id: string;
  name: string;
  organiser: string;
  competitionUrl: string;
  deadline: string; // YYYY-MM-DD or ''
  status: MissionStatus;
  progressDocUrl: string;
  notes: string;
  createdAt: string; // ISO string
  updatedAt: string; // ISO string
  archived: boolean;
}

export interface TeamMember {
  id: string;
  slotLabel: string;
  name: string;
  role: string;
  focusArea: string;
  profileUrl: string;
}

export interface ActivityEvent {
  id: string;
  competitionId: string;
  competitionName: string;
  action: 'CREATED' | 'UPDATED' | 'STATUS_CHANGED' | 'ARCHIVED' | 'RESTORED';
  summary: string;
  timestamp: string; // ISO string
}

export type ScreenId =
  | 'dashboard'
  | 'competitions'
  | 'add'
  | 'edit'
  | 'detail'
  | 'archive'
  | 'team';

export type DeadlineFilter =
  | 'ALL'
  | 'UPCOMING'
  | 'DUE_SOON'
  | 'OVERDUE'
  | 'NO_DEADLINE';

export type SortOption = 'DEADLINE_ASC' | 'NAME_ASC' | 'UPDATED_DESC';

export interface StorageConfig {
  provider: 'express_api' | 'apps_script';
  appsScriptUrl: string;
  lastSyncedAt: string | null;
}

export interface AuthStatusResponse {
  ok: boolean;
  pinConfigured: boolean;
  authenticated: boolean;
  expiresAt?: string;
  storageBackend: 'google_sheets_proxy' | 'server_persistent_store';
  appsScriptConnected: boolean;
}
