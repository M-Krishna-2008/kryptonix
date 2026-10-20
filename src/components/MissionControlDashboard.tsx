import React, { useEffect, useMemo, useState } from 'react';
import {
  Plus,
  AlertTriangle,
  Calendar,
  ExternalLink,
  FileText,
  Search,
  ArrowRight,
  Archive,
  Clock,
  Activity,
} from 'lucide-react';
import {
  ActivityEvent,
  Competition,
  MissionStatus,
  ScreenId,
  StorageConfig,
} from '../types/mission';
import {
  classifyDeadline,
  formatTimestamp,
  generateGoogleCalendarUrl,
  isValidHttpUrl,
  parseLocalDate,
} from '../utils/deadline';
import { OrbitalRadarViz } from './OrbitalRadarViz';
import {
  DeadlineReadout,
  StarCommandInsignia,
  StatusReadout,
} from './StarCommandInsignia';

interface MissionControlDashboardProps {
  competitions: Competition[];
  activityLog: ActivityEvent[];
  storageConfig: StorageConfig;
  onNavigate: (screen: ScreenId) => void;
  onSelectCompetition: (id: string) => void;
  onAddCompetition: () => void;
  onStatusChange: (id: string, status: MissionStatus) => Promise<void>;
}

export const MissionControlDashboard: React.FC<
  MissionControlDashboardProps
> = ({
  competitions,
  activityLog,
  storageConfig,
  onNavigate,
  onSelectCompetition,
  onAddCompetition,
  onStatusChange,
}) => {
  const [now, setNow] = useState(() => new Date());
  const [quickSearch, setQuickSearch] = useState('');

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const activeCompetitions = useMemo(
    () => competitions.filter((c) => !c.archived),
    [competitions]
  );

  const archivedCompetitions = useMemo(
    () => competitions.filter((c) => c.archived),
    [competitions]
  );

  // Dynamic statistics strictly derived from real active records
  const stats = useMemo(() => {
    const totalActive = activeCompetitions.length;
    const ongoing = activeCompetitions.filter(
      (c) => c.status === 'ONGOING'
    ).length;
    const submitted = activeCompetitions.filter(
      (c) => c.status === 'SUBMITTED'
    ).length;
    const completed = activeCompetitions.filter(
      (c) => c.status === 'COMPLETED'
    ).length;

    let upcomingDeadlines = 0;
    let overdueActive = 0;

    activeCompetitions.forEach((comp) => {
      // Completed and Submitted competitions are never counted as overdue or unfinished deadlines
      if (comp.status !== 'ONGOING') return;
      const dInfo = classifyDeadline(comp);
      if (dInfo.category === 'OVERDUE') {
        overdueActive += 1;
      } else if (
        dInfo.category === 'DUE_TODAY' ||
        dInfo.category === 'DUE_SOON' ||
        dInfo.category === 'UPCOMING'
      ) {
        upcomingDeadlines += 1;
      }
    });

    return {
      totalActive,
      ongoing,
      submitted,
      completed,
      upcomingDeadlines,
      overdueActive,
    };
  }, [activeCompetitions]);

  // Urgent missions: Overdue, Due Today, or Due Soon (only active ONGOING missions)
  const urgentMissions = useMemo(() => {
    return activeCompetitions
      .filter((c) => {
        if (c.status !== 'ONGOING') return false;
        const info = classifyDeadline(c);
        return (
          info.category === 'OVERDUE' ||
          info.category === 'DUE_TODAY' ||
          info.category === 'DUE_SOON'
        );
      })
      .sort((a, b) => {
        const da = parseLocalDate(a.deadline)?.getTime() ?? Infinity;
        const db = parseLocalDate(b.deadline)?.getTime() ?? Infinity;
        return da - db;
      });
  }, [activeCompetitions]);

  // Chronological Deadline Timeline (all active ONGOING & SUBMITTED missions with a valid deadline)
  const timelineMissions = useMemo(() => {
    return activeCompetitions
      .filter((c) => parseLocalDate(c.deadline) !== null)
      .sort((a, b) => {
        const da = parseLocalDate(a.deadline)?.getTime() ?? Infinity;
        const db = parseLocalDate(b.deadline)?.getTime() ?? Infinity;
        return da - db;
      })
      .slice(0, 6);
  }, [activeCompetitions]);

  // Quick searchable active overview
  const filteredOverview = useMemo(() => {
    const q = quickSearch.trim().toLowerCase();
    if (!q) return activeCompetitions.slice(0, 6);
    return activeCompetitions.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.organiser.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q)
    );
  }, [activeCompetitions, quickSearch]);

  const formattedLocalDate = now.toLocaleDateString(undefined, {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  const formattedLocalTime = now.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <div className="space-y-6">
      {/* Top Command Hero Banner */}
      <section className="bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-6 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div className="flex items-start sm:items-center gap-4">
          <StarCommandInsignia size="lg" className="hidden sm:block" />
          <div className="space-y-1">
            <div className="font-mono text-xs tracking-widest text-[#A6FF4D] font-semibold">
              WELCOME TO STAR COMMAND
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-wide text-[#F3F5FC]">
              KRYPTØNIX OPERATIONS CENTRE
            </h1>
            <p className="font-mono text-xs text-[#929DB7]">
              M KRISHNA · V JEYSHREE · SUBHA SHREE R · LAKSHMANAN G
            </p>
          </div>
        </div>

        {/* Compact Command-Console Identity & Live Local Clock + Primary CTA */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="bg-[#101629] border border-[#929DB7]/20 rounded-md px-4 py-2.5 font-mono text-xs">
            <div className="text-[#929DB7] text-[11px]">
              LOCAL MISSION CLOCK ·{' '}
              <span className="text-[#57DDF5]">
                {storageConfig.provider === 'apps_script'
                  ? 'SHEETS UPLINK'
                  : 'SERVER STORE'}
              </span>
            </div>
            <div className="text-sm font-bold text-[#F3F5FC] tabular-nums mt-0.5">
              {formattedLocalDate} ·{' '}
              <span className="text-[#A6FF4D]">{formattedLocalTime}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onAddCompetition}
            className="inline-flex items-center gap-2 px-5 py-3 text-xs font-display font-bold tracking-wide text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded-md transition-colors cursor-pointer whitespace-nowrap shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Add Competition</span>
          </button>
        </div>
      </section>

      {/* Urgent Deadline Warning Area (shown whenever active ongoing missions are Overdue, Due Today, or Due Soon) */}
      {urgentMissions.length > 0 && (
        <section
          aria-label="Urgent deadline warnings"
          className="bg-[#151D32] border border-[#FFBE55]/45 rounded-lg p-4 sm:p-5 space-y-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#FFBE55]">
              <AlertTriangle className="w-4 h-4 text-[#FF5C70] shrink-0" />
              <span>
                PRIORITY DEADLINE ALERT · {urgentMissions.length} ACTIVE ONGOING MISSION
                {urgentMissions.length > 1 ? 'S' : ''} REQUIRE ATTENTION
              </span>
            </div>
            <span className="text-xs text-[#929DB7]">
              Completed and submitted missions are excluded from urgent alerts
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {urgentMissions.map((comp) => {
              const info = classifyDeadline(comp);
              const isOverdue = info.category === 'OVERDUE';
              const gcal = generateGoogleCalendarUrl(comp);

              return (
                <div
                  key={comp.id}
                  className={`p-3.5 rounded-md bg-[#101629] border flex flex-col justify-between gap-3 ${
                    isOverdue ? 'border-[#FF5C70]/50' : 'border-[#FFBE55]/40'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 text-xs font-mono">
                      <span className="text-[#57DDF5] font-semibold">
                        {comp.id}
                      </span>
                      <span
                        className={
                          isOverdue
                            ? 'text-[#FF5C70] font-bold'
                            : 'text-[#FFBE55] font-semibold'
                        }
                      >
                        {info.category === 'OVERDUE'
                          ? '✖ OVERDUE'
                          : info.category === 'DUE_TODAY'
                          ? '▲ DUE TODAY'
                          : '▲ DUE SOON'}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => onSelectCompetition(comp.id)}
                      className="text-left font-display text-sm font-bold text-[#F3F5FC] hover:text-[#A6FF4D] mt-1 block truncate w-full cursor-pointer"
                    >
                      {comp.name}
                    </button>
                    <p className="font-mono text-xs text-[#929DB7] tabular-nums mt-0.5">
                      {info.formattedDate} · {info.countdownText}
                    </p>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-[#929DB7]/15 text-xs">
                    <button
                      type="button"
                      onClick={() => onSelectCompetition(comp.id)}
                      className="text-[#F3F5FC] hover:text-[#A6FF4D] font-medium cursor-pointer"
                    >
                      Open Dossier →
                    </button>
                    {gcal && (
                      <a
                        href={gcal}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[#57DDF5] hover:underline whitespace-nowrap"
                      >
                        <Calendar className="w-3 h-3" />
                        <span>Add to Calendar</span>
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* 6 Dynamic Telemetry Stat Readouts */}
      <section
        aria-label="Mission telemetry statistics"
        className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3"
      >
        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4">
          <div className="text-xs text-[#929DB7]">Total Active</div>
          <div className="font-mono text-2xl font-bold text-[#F3F5FC] tabular-nums mt-1">
            {stats.totalActive}
          </div>
          <div className="text-[11px] font-mono text-[#929DB7] mt-1">
            Excludes archived
          </div>
        </div>

        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4">
          <div className="text-xs text-[#929DB7]">Ongoing</div>
          <div className="font-mono text-2xl font-bold text-[#57DDF5] tabular-nums mt-1">
            ◆ {stats.ongoing}
          </div>
          <div className="text-[11px] font-mono text-[#929DB7] mt-1">
            In active preparation
          </div>
        </div>

        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4">
          <div className="text-xs text-[#929DB7]">Submitted</div>
          <div className="font-mono text-2xl font-bold text-[#9B7CFF] tabular-nums mt-1">
            ▲ {stats.submitted}
          </div>
          <div className="text-[11px] font-mono text-[#929DB7] mt-1">
            Awaiting results
          </div>
        </div>

        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4">
          <div className="text-xs text-[#929DB7]">Completed</div>
          <div className="font-mono text-2xl font-bold text-[#A6FF4D] tabular-nums mt-1">
            ✓ {stats.completed}
          </div>
          <div className="text-[11px] font-mono text-[#929DB7] mt-1">
            Active concluded
          </div>
        </div>

        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4">
          <div className="text-xs text-[#929DB7]">Upcoming Deadlines</div>
          <div className="font-mono text-2xl font-bold text-[#FFBE55] tabular-nums mt-1">
            {stats.upcomingDeadlines}
          </div>
          <div className="text-[11px] font-mono text-[#929DB7] mt-1">
            Ongoing scheduled
          </div>
        </div>

        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4">
          <div className="text-xs text-[#929DB7]">Overdue Active</div>
          <div
            className={`font-mono text-2xl font-bold tabular-nums mt-1 ${
              stats.overdueActive > 0 ? 'text-[#FF5C70]' : 'text-[#F3F5FC]'
            }`}
          >
            {stats.overdueActive}
          </div>
          <div className="text-[11px] font-mono text-[#929DB7] mt-1">
            Unfinished past due
          </div>
        </div>
      </section>

      {/* Middle Row: Circular SVG Orbital Radar + Deadline Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        <div className="lg:col-span-5 flex flex-col">
          <OrbitalRadarViz
            competitions={competitions}
            onSelectCompetition={onSelectCompetition}
          />
        </div>

        {/* Chronological Deadline Timeline Panel */}
        <div className="lg:col-span-7 bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-4 mb-4">
              <div>
                <h2 className="font-display text-base font-semibold tracking-wide text-[#F3F5FC]">
                  Mission Deadline Timeline
                </h2>
                <p className="text-xs text-[#929DB7]">
                  Chronological schedule classified in your local timezone
                </p>
              </div>
              <button
                type="button"
                onClick={() => onNavigate('competitions')}
                className="text-xs font-medium text-[#57DDF5] hover:underline whitespace-nowrap shrink-0 cursor-pointer"
              >
                View All Missions →
              </button>
            </div>

            {timelineMissions.length === 0 ? (
              <div className="py-12 text-center space-y-2">
                <Clock className="w-6 h-6 text-[#929DB7] mx-auto" />
                <p className="text-xs text-[#929DB7]">
                  No active competitions have a scheduled deadline yet.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-[#929DB7]/15">
                {timelineMissions.map((comp) => {
                  const gcalUrl = generateGoogleCalendarUrl(comp);
                  return (
                    <div
                      key={comp.id}
                      className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-mono text-[#57DDF5] font-semibold">
                            {comp.id}
                          </span>
                          <span aria-hidden="true" className="text-[#929DB7]">
                            ·
                          </span>
                          <StatusReadout status={comp.status} compact />
                        </div>
                        <button
                          type="button"
                          onClick={() => onSelectCompetition(comp.id)}
                          className="text-left font-medium text-sm text-[#F3F5FC] hover:text-[#A6FF4D] truncate block w-full mt-0.5 cursor-pointer"
                        >
                          {comp.name}
                        </button>
                      </div>

                      <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0">
                        <DeadlineReadout competition={comp} />
                        {gcalUrl && (
                          <a
                            href={gcalUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#57DDF5]/30 text-[#57DDF5]"
                            title="Add Deadline to Google Calendar (opens template in new tab)"
                            aria-label={`Add ${comp.name} deadline to Google Calendar`}
                          >
                            <Calendar className="w-3.5 h-3.5" />
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-[#929DB7]/15 flex items-center justify-between text-xs text-[#929DB7]">
            <span>
              Calendar icon opens Google Calendar event template in a new tab
            </span>
            <span className="font-mono">LOCAL TZ</span>
          </div>
        </div>
      </div>

      {/* Bottom Row: Searchable Active Competition Overview + Recent Activity & Quick Archive */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Searchable Active Competition Overview */}
        <div className="lg:col-span-8 bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-base font-semibold tracking-wide text-[#F3F5FC]">
                Active Competition Overview
              </h2>
              <p className="text-xs text-[#929DB7]">
                Quick-filter active missions, change status, or open progress documents
              </p>
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-[#929DB7] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="search"
                aria-label="Quick search active competitions"
                value={quickSearch}
                onChange={(e) => setQuickSearch(e.target.value)}
                placeholder="Filter active missions..."
                className="w-full pl-8 pr-3 py-1.5 bg-[#080B16] border border-[#929DB7]/30 rounded text-xs text-[#F3F5FC] placeholder-[#929DB7]/60 focus:outline-none focus:border-[#57DDF5]"
              />
            </div>
          </div>

          {activeCompetitions.length === 0 ? (
            <div className="py-10 text-center space-y-3">
              <p className="text-xs text-[#929DB7]">
                No active competitions registered yet.
              </p>
              <button
                type="button"
                onClick={onAddCompetition}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-display font-bold text-[#080B16] bg-[#A6FF4D] rounded cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add First Competition</span>
              </button>
            </div>
          ) : filteredOverview.length === 0 ? (
            <div className="py-8 text-center space-y-2">
              <p className="text-xs text-[#929DB7]">
                No active missions match "{quickSearch}".
              </p>
              <button
                type="button"
                onClick={() => setQuickSearch('')}
                className="text-xs text-[#57DDF5] hover:underline cursor-pointer"
              >
                Reset quick search
              </button>
            </div>
          ) : (
            <div className="divide-y divide-[#929DB7]/15">
              {filteredOverview.map((comp) => {
                const hasDoc = isValidHttpUrl(comp.progressDocUrl);
                return (
                  <div
                    key={comp.id}
                    className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <button
                        type="button"
                        onClick={() => onSelectCompetition(comp.id)}
                        className="text-left font-semibold text-sm text-[#F3F5FC] hover:text-[#A6FF4D] truncate block w-full cursor-pointer"
                      >
                        {comp.name}
                      </button>
                      <div className="text-xs text-[#929DB7] truncate mt-0.5">
                        <span className="font-mono text-[#57DDF5]">
                          {comp.id}
                        </span>
                        <span aria-hidden="true"> · </span>
                        <span>{comp.organiser || 'Unspecified Organiser'}</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                      <select
                        aria-label={`Change status for ${comp.name}`}
                        value={comp.status}
                        onChange={(e) =>
                          onStatusChange(
                            comp.id,
                            e.target.value as MissionStatus
                          )
                        }
                        className="px-2.5 py-1 rounded bg-[#080B16] border border-[#929DB7]/30 font-mono text-xs text-[#F3F5FC] cursor-pointer"
                      >
                        <option value="ONGOING">◆ ONGOING</option>
                        <option value="SUBMITTED">▲ SUBMITTED</option>
                        <option value="COMPLETED">✓ COMPLETED</option>
                      </select>

                      {hasDoc ? (
                        <a
                          href={comp.progressDocUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#A6FF4D]/30 text-xs text-[#A6FF4D] font-medium whitespace-nowrap"
                        >
                          <FileText className="w-3 h-3" />
                          <span>Progress</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span className="text-[11px] text-[#929DB7] px-2">
                          No Doc
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => onSelectCompetition(comp.id)}
                        className="px-2.5 py-1 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs text-[#F3F5FC] cursor-pointer whitespace-nowrap"
                      >
                        Details
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="pt-2 border-t border-[#929DB7]/15 flex items-center justify-between text-xs">
            <span className="text-[#929DB7] font-mono tabular-nums">
              Showing {filteredOverview.length} of {activeCompetitions.length}{' '}
              active competitions
            </span>
            <button
              type="button"
              onClick={() => onNavigate('competitions')}
              className="inline-flex items-center gap-1 text-[#57DDF5] hover:underline font-medium cursor-pointer"
            >
              <span>Open Full Competition Command</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Right Column: Recent Activity & Quick-Access Archive Panel */}
        <div className="lg:col-span-4 space-y-6">
          {/* Recent Activity Log (Strictly real application events) */}
          <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-base font-semibold tracking-wide text-[#F3F5FC]">
                Recent Mission Activity
              </h2>
              <Activity className="w-4 h-4 text-[#9B7CFF]" />
            </div>

            {activityLog.length === 0 ? (
              <p className="text-xs text-[#929DB7] py-4">
                No mission activity logged yet.
              </p>
            ) : (
              <div className="divide-y divide-[#929DB7]/15 max-h-[220px] overflow-y-auto pr-1">
                {activityLog.slice(0, 6).map((act) => (
                  <div key={act.id} className="py-2.5 text-xs space-y-0.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-[#F3F5FC] truncate">
                        {act.competitionName}
                      </span>
                      <span className="font-mono text-[10px] text-[#57DDF5] shrink-0">
                        {act.action}
                      </span>
                    </div>
                    <p className="text-[#929DB7] text-[11px]">{act.summary}</p>
                    <div className="font-mono text-[10px] text-[#929DB7]/80 tabular-nums">
                      {formatTimestamp(act.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick-Access Archive Panel */}
          <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-display text-base font-semibold tracking-wide text-[#F3F5FC]">
                  Completed Archive Vault
                </h2>
                <p className="text-xs text-[#929DB7]">
                  {archivedCompetitions.length} archived mission
                  {archivedCompetitions.length === 1 ? '' : 's'} preserved
                </p>
              </div>
              <Archive className="w-4 h-4 text-[#A6FF4D]" />
            </div>

            {archivedCompetitions.length > 0 && (
              <div className="space-y-2 pt-1">
                {archivedCompetitions.slice(0, 2).map((arch) => (
                  <button
                    key={arch.id}
                    type="button"
                    onClick={() => onSelectCompetition(arch.id)}
                    className="w-full text-left p-2.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/15 text-xs cursor-pointer block"
                  >
                    <div className="font-medium text-[#F3F5FC] truncate">
                      {arch.name}
                    </div>
                    <div className="font-mono text-[11px] text-[#929DB7] truncate">
                      {arch.id} · {arch.organiser}
                    </div>
                  </button>
                ))}
              </div>
            )}

            <button
              type="button"
              onClick={() => onNavigate('archive')}
              className="w-full py-2 px-3 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs font-medium text-[#F3F5FC] inline-flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <span>Open Completed Missions Archive</span>
              <ArrowRight className="w-3.5 h-3.5 text-[#A6FF4D]" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
