/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  LayoutDashboard,
  ListChecks,
  PlusCircle,
  Archive,
  Users,
  Search,
  LogOut,
  Menu,
  X,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
} from 'lucide-react';
import { getDefaultTeamRoster, TEAM_NAME } from './config/teamConfig';
import {
  ActivityEvent,
  Competition,
  MissionStatus,
  ScreenId,
  StorageConfig,
  TeamMember,
} from './types/mission';
import {
  createCompetitionRecord,
  fetchMissionData,
  getStorageConfig,
  getStoredSessionToken,
  logoutSession,
  saveStorageConfig,
  toggleCompetitionArchiveRecord,
  updateCompetitionRecord,
  updateCompetitionStatusRecord,
  updateTeamRosterRecord,
} from './services/storageService';
import { StarCommandInsignia } from './components/StarCommandInsignia';
import { BootSequenceAndLogin } from './components/BootSequenceAndLogin';
import { MissionControlDashboard } from './components/MissionControlDashboard';
import { CompetitionsCommandView } from './components/CompetitionsCommandView';
import { CompetitionFormView } from './components/CompetitionFormView';
import { CompetitionDetailView } from './components/CompetitionDetailView';
import { ArchiveView } from './components/ArchiveView';
import { TeamProfileView } from './components/TeamProfileView';

function parseHashRoute(hash: string): {
  screen: ScreenId;
  targetId: string | null;
} {
  const cleaned = hash.replace(/^#\/?/, '').trim();
  if (!cleaned || cleaned === 'dashboard') {
    return { screen: 'dashboard', targetId: null };
  }
  const parts = cleaned.split('/');
  const route = parts[0];
  const param = parts[1] ? decodeURIComponent(parts[1]) : null;

  if (route === 'competitions')
    return { screen: 'competitions', targetId: null };
  if (route === 'add') return { screen: 'add', targetId: null };
  if (route === 'edit' && param) return { screen: 'edit', targetId: param };
  if (route === 'detail' && param) return { screen: 'detail', targetId: param };
  if (route === 'archive') return { screen: 'archive', targetId: null };
  if (route === 'team') return { screen: 'team', targetId: null };

  return { screen: 'dashboard', targetId: null };
}

export default function App() {
  const [storageConfig, setStorageConfig] = useState<StorageConfig>(() =>
    getStorageConfig()
  );
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() =>
    Boolean(getStoredSessionToken())
  );

  // Hash-based routing for static GitHub Pages compatibility
  const [currentRoute, setCurrentRoute] = useState<{
    screen: ScreenId;
    targetId: string | null;
  }>(() =>
    typeof window !== 'undefined'
      ? parseHashRoute(window.location.hash)
      : { screen: 'dashboard', targetId: null }
  );

  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>(() =>
    getDefaultTeamRoster()
  );
  const [activityLog, setActivityLog] = useState<ActivityEvent[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [backendLoadError, setBackendLoadError] = useState<string | null>(null);

  const [toastBanner, setToastBanner] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  const [globalSearch, setGlobalSearch] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navigateTo = useCallback(
    (screen: ScreenId, targetId: string | null = null) => {
      setMobileMenuOpen(false);
      const nextHash = targetId
        ? `#/${screen}/${encodeURIComponent(targetId)}`
        : `#/${screen}`;
      if (typeof window !== 'undefined' && window.location.hash !== nextHash) {
        window.location.hash = nextHash;
      }
      setCurrentRoute({ screen, targetId });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    []
  );

  useEffect(() => {
    const onHashChange = () => {
      setCurrentRoute(parseHashRoute(window.location.hash));
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const showToast = useCallback(
    (type: 'success' | 'error', message: string) => {
      setToastBanner({ type, message });
      setTimeout(() => {
        setToastBanner((prev) => (prev?.message === message ? null : prev));
      }, 4500);
    },
    []
  );

  const loadFromBackend = useCallback(
    async (cfg: StorageConfig) => {
      setIsLoadingData(true);
      setBackendLoadError(null);
      try {
        const res = await fetchMissionData(cfg);
        setCompetitions(res.competitions);
        setTeamMembers(res.teamMembers);
        setActivityLog(res.activityLog);
      } catch (err) {
        if (err instanceof Error && err.message === 'UNAUTHENTICATED') {
          setIsAuthenticated(false);
          return;
        }
        setBackendLoadError(
          err instanceof Error
            ? err.message
            : 'Unable to retrieve competition records from the backend data store.'
        );
      } finally {
        setIsLoadingData(false);
      }
    },
    []
  );

  useEffect(() => {
    if (isAuthenticated) {
      loadFromBackend(storageConfig);
    }
  }, [isAuthenticated, storageConfig, loadFromBackend]);

  const handleUpdateStorageConfig = (nextConfig: StorageConfig) => {
    saveStorageConfig(nextConfig);
    setStorageConfig(nextConfig);
    if (isAuthenticated) {
      loadFromBackend(nextConfig);
    }
  };

  const handleAuthenticated = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = async () => {
    await logoutSession(storageConfig);
    setIsAuthenticated(false);
    setCompetitions([]);
    setActivityLog([]);
    setMobileMenuOpen(false);
  };

  // Real Backend CRUD Handlers — never claim success unless server confirms
  const handleCreateCompetition = async (formData: {
    name: string;
    organiser: string;
    competitionUrl: string;
    deadline: string;
    status: MissionStatus;
    progressDocUrl: string;
    notes: string;
  }) => {
    try {
      const result = await createCompetitionRecord(storageConfig, formData);
      setCompetitions(result.competitions);
      setActivityLog(result.activityLog);
      showToast(
        'success',
        `Mission ${result.competition.id} (${result.competition.name}) saved to server.`
      );
      navigateTo('detail', result.competition.id);
    } catch (err) {
      if (err instanceof Error && err.message === 'UNAUTHENTICATED') {
        setIsAuthenticated(false);
        return;
      }
      throw err;
    }
  };

  const handleEditCompetition = async (
    id: string,
    formData: {
      name: string;
      organiser: string;
      competitionUrl: string;
      deadline: string;
      status: MissionStatus;
      progressDocUrl: string;
      notes: string;
    }
  ) => {
    try {
      const result = await updateCompetitionRecord(storageConfig, id, formData);
      setCompetitions(result.competitions);
      setActivityLog(result.activityLog);
      showToast('success', `Mission ${id} updated in data store.`);
      navigateTo('detail', id);
    } catch (err) {
      if (err instanceof Error && err.message === 'UNAUTHENTICATED') {
        setIsAuthenticated(false);
        return;
      }
      throw err;
    }
  };

  const handleStatusChange = async (id: string, nextStatus: MissionStatus) => {
    try {
      const result = await updateCompetitionStatusRecord(
        storageConfig,
        id,
        nextStatus
      );
      setCompetitions(result.competitions);
      setActivityLog(result.activityLog);
      showToast(
        'success',
        `${result.competition.name} status updated to ${nextStatus}.`
      );
    } catch (err) {
      if (err instanceof Error && err.message === 'UNAUTHENTICATED') {
        setIsAuthenticated(false);
        return;
      }
      showToast(
        'error',
        err instanceof Error
          ? err.message
          : 'Failed to update competition status.'
      );
    }
  };

  const handleToggleArchive = async (id: string, archive: boolean) => {
    try {
      const result = await toggleCompetitionArchiveRecord(
        storageConfig,
        id,
        archive
      );
      setCompetitions(result.competitions);
      setActivityLog(result.activityLog);
      showToast(
        'success',
        archive
          ? `${result.competition.name} archived.`
          : `${result.competition.name} restored to active competitions.`
      );
      if (archive && currentRoute.screen === 'detail') {
        navigateTo('archive');
      }
    } catch (err) {
      if (err instanceof Error && err.message === 'UNAUTHENTICATED') {
        setIsAuthenticated(false);
        return;
      }
      showToast(
        'error',
        err instanceof Error
          ? err.message
          : 'Failed to update archive state.'
      );
    }
  };

  const handleUpdateTeamMembers = async (nextMembers: TeamMember[]) => {
    try {
      const savedRoster = await updateTeamRosterRecord(
        storageConfig,
        nextMembers
      );
      setTeamMembers(savedRoster);
      showToast('success', 'KRYPTØNIX team member configuration saved.');
    } catch (err) {
      if (err instanceof Error && err.message === 'UNAUTHENTICATED') {
        setIsAuthenticated(false);
        return;
      }
      throw err;
    }
  };

  const activeCount = useMemo(
    () => competitions.filter((c) => !c.archived).length,
    [competitions]
  );
  const archivedCount = useMemo(
    () => competitions.filter((c) => c.archived).length,
    [competitions]
  );

  // Screen 1: Server-Verified Team PIN Login
  if (!isAuthenticated) {
    return (
      <BootSequenceAndLogin
        storageConfig={storageConfig}
        onUpdateStorageConfig={handleUpdateStorageConfig}
        onAuthenticated={handleAuthenticated}
      />
    );
  }

  const navItems: {
    id: ScreenId;
    label: string;
    icon: React.FC<{ className?: string }>;
    count?: number;
  }[] = [
    {
      id: 'dashboard',
      label: 'Mission Control',
      icon: LayoutDashboard,
    },
    {
      id: 'competitions',
      label: 'All Competitions',
      icon: ListChecks,
      count: activeCount,
    },
    {
      id: 'add',
      label: 'Add Competition',
      icon: PlusCircle,
    },
    {
      id: 'archive',
      label: 'Completed Archive',
      icon: Archive,
      count: archivedCount,
    },
    {
      id: 'team',
      label: 'Team Profile',
      icon: Users,
    },
  ];

  const screenTitles: Record<ScreenId, string> = {
    dashboard: 'Mission Control Dashboard',
    competitions: 'Competition Command',
    add: 'Add Competition',
    edit: 'Edit Competition',
    detail: 'Mission Dossier',
    archive: 'Completed Missions Archive',
    team: 'Team Profile & Uplink',
  };

  const selectedCompetition = currentRoute.targetId
    ? competitions.find((c) => c.id === currentRoute.targetId) || null
    : null;

  const todayFormatted = new Date().toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen star-command-bg text-[#F3F5FC] flex">
      {/* Desktop Command Sidebar */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:fixed lg:inset-y-0 bg-[#101629] border-r border-[#929DB7]/20 z-30 justify-between">
        <div>
          {/* Brand Header */}
          <div className="h-16 px-5 flex items-center gap-3 border-b border-[#929DB7]/20">
            <StarCommandInsignia size="sm" />
            <div className="min-w-0">
              <div className="font-display text-base font-bold tracking-wider text-[#F3F5FC] truncate">
                {TEAM_NAME}
              </div>
              <div className="font-mono text-[10px] text-[#A6FF4D] tracking-widest">
                STAR COMMAND
              </div>
            </div>
          </div>

          {/* Primary Navigation */}
          <nav
            aria-label="Primary Star Command Navigation"
            className="p-3 space-y-1"
          >
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                currentRoute.screen === item.id ||
                (item.id === 'competitions' &&
                  (currentRoute.screen === 'detail' ||
                    currentRoute.screen === 'edit'));

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigateTo(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-md text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                    isActive
                      ? 'bg-[#151D32] text-[#A6FF4D] border border-[#A6FF4D]/35 font-semibold'
                      : 'text-[#929DB7] hover:text-[#F3F5FC] hover:bg-[#151D32]/60 border border-transparent'
                  }`}
                >
                  <span className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </span>
                  {item.count !== undefined && (
                    <span className="font-mono text-[11px] tabular-nums opacity-85">
                      {item.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Compact System-Status & Session Area */}
        <div className="p-4 border-t border-[#929DB7]/20 space-y-3 text-xs">
          <div className="p-3 rounded bg-[#080B16] border border-[#929DB7]/20 space-y-1.5">
            <div className="flex items-center justify-between font-mono text-[11px]">
              <span className="text-[#929DB7]">DATA STORE</span>
              <span className="text-[#A6FF4D] font-semibold">
                {storageConfig.provider === 'apps_script'
                  ? 'GOOGLE SHEETS'
                  : 'SERVER API'}
              </span>
            </div>
            <p className="text-[11px] text-[#929DB7] leading-snug">
              {storageConfig.provider === 'apps_script'
                ? 'Connected to Google Sheets via Apps Script Web App.'
                : 'Connected to authenticated Star Command persistent server store.'}
            </p>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded bg-[#151D32] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs font-medium text-[#FF5C70] transition-colors cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Lock Terminal (Logout)</span>
          </button>
        </div>
      </aside>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-50 lg:hidden bg-[#080B16]/80 flex"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-72 max-w-[82vw] bg-[#101629] border-r border-[#929DB7]/25 h-full flex flex-col justify-between p-4">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-[#929DB7]/20">
                <div className="flex items-center gap-2.5">
                  <StarCommandInsignia size="sm" />
                  <span className="font-display font-bold text-base text-[#F3F5FC]">
                    {TEAM_NAME}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  aria-label="Close navigation menu"
                  className="p-1.5 text-[#929DB7] hover:text-[#F3F5FC]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <nav className="mt-4 space-y-1.5">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = currentRoute.screen === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => navigateTo(item.id)}
                      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-md text-xs font-medium ${
                        isActive
                          ? 'bg-[#151D32] text-[#A6FF4D] border border-[#A6FF4D]/35 font-semibold'
                          : 'text-[#929DB7] hover:text-[#F3F5FC]'
                      }`}
                    >
                      <span className="flex items-center gap-2.5">
                        <Icon className="w-4 h-4" />
                        <span>{item.label}</span>
                      </span>
                      {item.count !== undefined && (
                        <span className="font-mono text-xs tabular-nums">
                          {item.count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded bg-[#151D32] border border-[#929DB7]/25 text-xs font-medium text-[#FF5C70]"
            >
              <LogOut className="w-4 h-4" />
              <span>Lock Terminal (Logout)</span>
            </button>
          </div>
          <div
            className="flex-1"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
        </div>
      )}

      {/* Main Content Column */}
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0">
        {/* Top Command Bar */}
        <header className="sticky top-0 z-20 h-16 bg-[#101629]/95 border-b border-[#929DB7]/20 px-4 sm:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className="lg:hidden p-2 rounded bg-[#151D32] border border-[#929DB7]/25 text-[#F3F5FC]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <span className="font-display text-sm sm:text-base font-bold tracking-wide text-[#F3F5FC] truncate">
              {screenTitles[currentRoute.screen]}
            </span>
          </div>

          <div className="hidden md:flex items-center gap-5">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (currentRoute.screen !== 'competitions') {
                  navigateTo('competitions');
                }
              }}
              className="relative w-64"
            >
              <Search className="w-3.5 h-3.5 text-[#929DB7] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="search"
                aria-label="Search competitions across Star Command"
                value={globalSearch}
                onChange={(e) => {
                  setGlobalSearch(e.target.value);
                  if (currentRoute.screen !== 'competitions') {
                    navigateTo('competitions');
                  }
                }}
                placeholder="Search missions or organisers..."
                className="w-full pl-8 pr-3 py-1.5 bg-[#080B16] border border-[#929DB7]/30 rounded text-xs text-[#F3F5FC] placeholder-[#929DB7]/60 focus:outline-none focus:border-[#57DDF5]"
              />
            </form>

            <span className="font-mono text-xs text-[#929DB7] tabular-nums whitespace-nowrap shrink-0">
              {todayFormatted}
            </span>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={() => loadFromBackend(storageConfig)}
              title="Refresh Data from Server"
              aria-label="Refresh mission data from server"
              className="p-2 rounded bg-[#151D32] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#929DB7] hover:text-[#F3F5FC] cursor-pointer"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${isLoadingData ? 'animate-spin' : ''}`}
              />
            </button>

            <button
              type="button"
              onClick={() => navigateTo('add')}
              className="px-3.5 py-2 rounded bg-[#A6FF4D] hover:bg-[#b8ff6e] text-[#080B16] font-display font-bold text-xs tracking-wide transition-colors cursor-pointer whitespace-nowrap shrink-0"
            >
              + Add Mission
            </button>
          </div>
        </header>

        {/* Feedback Toast Banner */}
        {toastBanner && (
          <div className="px-4 sm:px-8 pt-4">
            <div
              role="status"
              className={`p-3 rounded-md border text-xs flex items-center justify-between gap-3 ${
                toastBanner.type === 'success'
                  ? 'bg-[#A6FF4D]/10 border-[#A6FF4D]/40 text-[#A6FF4D]'
                  : 'bg-[#FF5C70]/10 border-[#FF5C70]/40 text-[#FF5C70]'
              }`}
            >
              <div className="flex items-center gap-2">
                {toastBanner.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0" />
                )}
                <span>{toastBanner.message}</span>
              </div>
              <button
                type="button"
                onClick={() => setToastBanner(null)}
                className="text-xs underline opacity-80 hover:opacity-100 cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Explicit Backend Error Banner with Retry Option (Never silently falls back to demo data) */}
        {backendLoadError && (
          <div className="px-4 sm:px-8 pt-4">
            <div
              role="alert"
              className="p-4 rounded-lg bg-[#FF5C70]/10 border border-[#FF5C70]/45 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="flex items-start gap-2.5 text-[#FF5C70]">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold">
                    Data Store Connection Error
                  </div>
                  <p className="text-[#F3F5FC]/90 mt-0.5">
                    {backendLoadError}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => loadFromBackend(storageConfig)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded bg-[#57DDF5] text-[#080B16] font-semibold cursor-pointer whitespace-nowrap"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Connection</span>
                </button>
                <button
                  type="button"
                  onClick={() => navigateTo('team')}
                  className="px-3.5 py-2 rounded bg-[#151D32] border border-[#929DB7]/30 text-[#F3F5FC] cursor-pointer whitespace-nowrap"
                >
                  Check Uplink Settings
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Active Screen Viewport */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto">
          {currentRoute.screen === 'dashboard' && (
            <MissionControlDashboard
              competitions={competitions}
              activityLog={activityLog}
              storageConfig={storageConfig}
              onNavigate={(scr) => navigateTo(scr)}
              onSelectCompetition={(id) => navigateTo('detail', id)}
              onAddCompetition={() => navigateTo('add')}
              onStatusChange={handleStatusChange}
            />
          )}

          {currentRoute.screen === 'competitions' && (
            <CompetitionsCommandView
              competitions={competitions}
              globalSearchQuery={globalSearch}
              onChangeGlobalSearch={setGlobalSearch}
              onSelectCompetition={(id) => navigateTo('detail', id)}
              onAddCompetition={() => navigateTo('add')}
              onEditCompetition={(id) => navigateTo('edit', id)}
              onStatusChange={handleStatusChange}
              onArchiveCompetition={(id) => handleToggleArchive(id, true)}
            />
          )}

          {currentRoute.screen === 'add' && (
            <CompetitionFormView
              mode="add"
              existingCompetitions={competitions}
              onSave={handleCreateCompetition}
              onCancel={() => navigateTo('competitions')}
            />
          )}

          {currentRoute.screen === 'edit' && (
            selectedCompetition ? (
              <CompetitionFormView
                mode="edit"
                initialCompetition={selectedCompetition}
                existingCompetitions={competitions}
                onSave={(data) =>
                  handleEditCompetition(selectedCompetition.id, data)
                }
                onCancel={() => navigateTo('detail', selectedCompetition.id)}
              />
            ) : (
              <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-8 text-center space-y-3">
                <p className="text-sm text-[#F3F5FC]">
                  Competition record not found.
                </p>
                <button
                  type="button"
                  onClick={() => navigateTo('competitions')}
                  className="px-4 py-2 text-xs font-medium text-[#080B16] bg-[#57DDF5] rounded cursor-pointer"
                >
                  Back to Competitions
                </button>
              </div>
            )
          )}

          {currentRoute.screen === 'detail' && (
            selectedCompetition ? (
              <CompetitionDetailView
                competition={selectedCompetition}
                onBack={() => navigateTo('competitions')}
                onEdit={(id) => navigateTo('edit', id)}
                onStatusChange={handleStatusChange}
                onToggleArchive={handleToggleArchive}
              />
            ) : (
              <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-8 text-center space-y-3">
                <p className="text-sm text-[#F3F5FC]">
                  Competition dossier not found.
                </p>
                <button
                  type="button"
                  onClick={() => navigateTo('competitions')}
                  className="px-4 py-2 text-xs font-medium text-[#080B16] bg-[#57DDF5] rounded cursor-pointer"
                >
                  Return to All Competitions
                </button>
              </div>
            )
          )}

          {currentRoute.screen === 'archive' && (
            <ArchiveView
              competitions={competitions}
              onSelectCompetition={(id) => navigateTo('detail', id)}
              onRestoreCompetition={(id) => handleToggleArchive(id, false)}
              onArchiveCompletedCompetition={(id) =>
                handleToggleArchive(id, true)
              }
            />
          )}

          {currentRoute.screen === 'team' && (
            <TeamProfileView
              teamMembers={teamMembers}
              storageConfig={storageConfig}
              onUpdateTeamMembers={handleUpdateTeamMembers}
              onUpdateStorageConfig={handleUpdateStorageConfig}
            />
          )}
        </main>

        {/* Quiet Functional Footer */}
        <footer className="px-4 sm:px-8 py-4 border-t border-[#929DB7]/15 text-xs text-[#929DB7] flex flex-wrap items-center justify-between gap-4">
          <span>
            {TEAM_NAME} — Star Command Operations Centre · M KRISHNA · V JEYSHREE · SUBHA SHREE R · LAKSHMANAN G
          </span>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={() => navigateTo('team')}
              className="hover:text-[#F3F5FC] cursor-pointer"
            >
              Data Store & PIN Settings
            </button>
            <span aria-hidden="true">·</span>
            <button
              type="button"
              onClick={handleLogout}
              className="hover:text-[#FF5C70] cursor-pointer"
            >
              Lock Session
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
