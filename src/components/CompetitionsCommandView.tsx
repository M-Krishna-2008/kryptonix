import React, { useMemo, useState } from 'react';
import {
  Search,
  Plus,
  RotateCcw,
  ExternalLink,
  FileText,
  Calendar,
  Edit3,
  Archive,
  Eye,
  AlertTriangle,
  ArrowUpDown,
} from 'lucide-react';
import {
  Competition,
  DeadlineFilter,
  MissionStatus,
  SortOption,
} from '../types/mission';
import {
  classifyDeadline,
  generateGoogleCalendarUrl,
  isValidHttpUrl,
  parseLocalDate,
} from '../utils/deadline';
import { DeadlineReadout } from './StarCommandInsignia';

interface CompetitionsCommandViewProps {
  competitions: Competition[];
  globalSearchQuery: string;
  onChangeGlobalSearch: (q: string) => void;
  onSelectCompetition: (id: string) => void;
  onAddCompetition: () => void;
  onEditCompetition: (id: string) => void;
  onStatusChange: (id: string, status: MissionStatus) => Promise<void>;
  onArchiveCompetition: (id: string) => Promise<void>;
}

export const CompetitionsCommandView: React.FC<
  CompetitionsCommandViewProps
> = ({
  competitions,
  globalSearchQuery,
  onChangeGlobalSearch,
  onSelectCompetition,
  onAddCompetition,
  onEditCompetition,
  onStatusChange,
  onArchiveCompetition,
}) => {
  const [statusFilter, setStatusFilter] = useState<'ALL' | MissionStatus>('ALL');
  const [deadlineFilter, setDeadlineFilter] = useState<DeadlineFilter>('ALL');
  const [sortBy, setSortBy] = useState<SortOption>('DEADLINE_ASC');
  const [archiveConfirmTarget, setArchiveConfirmTarget] =
    useState<Competition | null>(null);

  const activeCompetitions = useMemo(
    () => competitions.filter((c) => !c.archived),
    [competitions]
  );

  const hasActiveFilters =
    globalSearchQuery.trim() !== '' ||
    statusFilter !== 'ALL' ||
    deadlineFilter !== 'ALL' ||
    sortBy !== 'DEADLINE_ASC';

  const handleResetFilters = () => {
    onChangeGlobalSearch('');
    setStatusFilter('ALL');
    setDeadlineFilter('ALL');
    setSortBy('DEADLINE_ASC');
  };

  const filteredAndSorted = useMemo(() => {
    const query = globalSearchQuery.trim().toLowerCase();

    const filtered = activeCompetitions.filter((comp) => {
      if (query) {
        const matchesName = comp.name.toLowerCase().includes(query);
        const matchesOrg = comp.organiser.toLowerCase().includes(query);
        const matchesId = comp.id.toLowerCase().includes(query);
        if (!matchesName && !matchesOrg && !matchesId) return false;
      }

      if (statusFilter !== 'ALL' && comp.status !== statusFilter) {
        return false;
      }

      if (deadlineFilter !== 'ALL') {
        const dInfo = classifyDeadline(comp);
        if (deadlineFilter === 'NO_DEADLINE') {
          if (parseLocalDate(comp.deadline) !== null) return false;
        } else if (deadlineFilter === 'OVERDUE') {
          if (dInfo.category !== 'OVERDUE') return false;
        } else if (deadlineFilter === 'DUE_SOON') {
          if (dInfo.category !== 'DUE_SOON' && dInfo.category !== 'DUE_TODAY') {
            return false;
          }
        } else if (deadlineFilter === 'UPCOMING') {
          if (
            dInfo.category !== 'UPCOMING' &&
            dInfo.category !== 'DUE_SOON' &&
            dInfo.category !== 'DUE_TODAY'
          ) {
            return false;
          }
        }
      }

      return true;
    });

    return filtered.sort((a, b) => {
      if (sortBy === 'NAME_ASC') {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === 'UPDATED_DESC') {
        return (
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
      }
      // DEADLINE_ASC: valid deadlines first (earliest to latest), then no deadline
      const da = parseLocalDate(a.deadline);
      const db = parseLocalDate(b.deadline);
      if (da && db) return da.getTime() - db.getTime();
      if (da && !db) return -1;
      if (!da && db) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [activeCompetitions, globalSearchQuery, statusFilter, deadlineFilter, sortBy]);

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-wide text-[#F3F5FC]">
            Competition Command Roster
          </h1>
          <p className="text-sm text-[#929DB7] mt-0.5">
            Manage all active KRYPTØNIX competitions, update statuses, launch progress documents, and export deadlines.
          </p>
        </div>

        <button
          type="button"
          onClick={onAddCompetition}
          className="inline-flex items-center gap-2 px-4 py-2.5 text-xs font-display font-bold tracking-wide text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded-md transition-colors cursor-pointer whitespace-nowrap shrink-0 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Add Competition</span>
        </button>
      </div>

      {/* Search, Filter & Sort Command Bar */}
      <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          {/* Search Input */}
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-[#929DB7] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="search"
              aria-label="Search competitions by name or organiser"
              value={globalSearchQuery}
              onChange={(e) => onChangeGlobalSearch(e.target.value)}
              placeholder="Search by competition name, organiser, or ID..."
              className="w-full pl-10 pr-3.5 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded-md text-xs text-[#F3F5FC] placeholder-[#929DB7]/60 focus:outline-none focus:border-[#57DDF5]"
            />
          </div>

          {/* Deadline Urgency Filter */}
          <div className="md:col-span-4">
            <label htmlFor="deadline-filter-select" className="sr-only">
              Filter by Deadline Classification
            </label>
            <select
              id="deadline-filter-select"
              value={deadlineFilter}
              onChange={(e) =>
                setDeadlineFilter(e.target.value as DeadlineFilter)
              }
              className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded-md text-xs text-[#F3F5FC] focus:outline-none focus:border-[#57DDF5]"
            >
              <option value="ALL">All Deadlines</option>
              <option value="OVERDUE">Overdue Active Missions</option>
              <option value="DUE_SOON">Due Today or Due Soon (≤ 7 days)</option>
              <option value="UPCOMING">All Upcoming Scheduled</option>
              <option value="NO_DEADLINE">No Deadline Set</option>
            </select>
          </div>

          {/* Sort Selector */}
          <div className="md:col-span-3 flex items-center gap-2">
            <ArrowUpDown className="w-3.5 h-3.5 text-[#929DB7] shrink-0 hidden sm:block" />
            <label htmlFor="sort-select" className="sr-only">
              Sort competitions
            </label>
            <select
              id="sort-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded-md text-xs text-[#F3F5FC] focus:outline-none focus:border-[#57DDF5]"
            >
              <option value="DEADLINE_ASC">Sort: Earliest Deadline</option>
              <option value="UPDATED_DESC">Sort: Recently Updated</option>
              <option value="NAME_ASC">Sort: Name (A–Z)</option>
            </select>
          </div>
        </div>

        {/* Interactive Status Segmented Controls + Clear Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[#929DB7]/15">
          <div className="flex flex-wrap items-center gap-1.5">
            {(
              [
                { id: 'ALL', label: 'All Statuses' },
                { id: 'ONGOING', label: '◆ Ongoing' },
                { id: 'SUBMITTED', label: '▲ Submitted' },
                { id: 'COMPLETED', label: '✓ Completed' },
              ] as const
            ).map((tab) => {
              const active = statusFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStatusFilter(tab.id)}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors cursor-pointer whitespace-nowrap shrink-0 ${
                    active
                      ? 'bg-[#9B7CFF] text-[#080B16] font-bold'
                      : 'bg-[#101629] text-[#929DB7] hover:text-[#F3F5FC]'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3 text-xs">
            <span className="font-mono text-[#929DB7] tabular-nums">
              Showing {filteredAndSorted.length} of {activeCompetitions.length} active
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#101629] hover:bg-[#1E2942] text-[#57DDF5] border border-[#57DDF5]/30 font-medium cursor-pointer whitespace-nowrap"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset Filters</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Empty States */}
      {activeCompetitions.length === 0 ? (
        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-10 text-center space-y-3">
          <h2 className="font-display text-lg font-bold text-[#F3F5FC]">
            No Active Competitions Logged
          </h2>
          <p className="text-xs text-[#929DB7] max-w-md mx-auto">
            Your active competition roster is currently empty. Register your first technology competition mission to begin tracking deadlines and progress documents.
          </p>
          <button
            type="button"
            onClick={onAddCompetition}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-display font-bold text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded-md cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Competition</span>
          </button>
        </div>
      ) : filteredAndSorted.length === 0 ? (
        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-10 text-center space-y-3">
          <h2 className="font-display text-lg font-bold text-[#F3F5FC]">
            No Missions Match Current Search or Filters
          </h2>
          <p className="text-xs text-[#929DB7] max-w-md mx-auto">
            Try broadening your search terms or clearing the status and deadline filters.
          </p>
          <button
            type="button"
            onClick={handleResetFilters}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-[#080B16] bg-[#57DDF5] hover:bg-[#7be6f8] rounded-md cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Clear All Filters</span>
          </button>
        </div>
      ) : (
        <>
          {/* Desktop High-Density Data Table */}
          <div className="hidden lg:block bg-[#151D32] border border-[#929DB7]/20 rounded-lg overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#101629] border-b border-[#929DB7]/20 text-[11px] font-mono text-[#929DB7]">
                  <th className="py-3 px-4 font-semibold">MISSION / ORGANISER</th>
                  <th className="py-3 px-4 font-semibold">STATUS</th>
                  <th className="py-3 px-4 font-semibold">DEADLINE & COUNTDOWN</th>
                  <th className="py-3 px-4 font-semibold">RESOURCES</th>
                  <th className="py-3 px-4 font-semibold text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#929DB7]/15 text-xs">
                {filteredAndSorted.map((comp) => {
                  const gcalUrl = generateGoogleCalendarUrl(comp);
                  const validCompUrl = isValidHttpUrl(comp.competitionUrl);
                  const validDocUrl = isValidHttpUrl(comp.progressDocUrl);

                  return (
                    <tr
                      key={comp.id}
                      className="hover:bg-[#101629]/70 transition-colors"
                    >
                      <td className="py-3.5 px-4 max-w-[290px]">
                        <button
                          type="button"
                          onClick={() => onSelectCompetition(comp.id)}
                          className="text-left group cursor-pointer block w-full"
                        >
                          <div className="font-semibold text-sm text-[#F3F5FC] group-hover:text-[#A6FF4D] transition-colors truncate">
                            {comp.name}
                          </div>
                          <div className="text-xs text-[#929DB7] truncate mt-0.5">
                            <span className="font-mono text-[#57DDF5]">
                              {comp.id}
                            </span>
                            <span aria-hidden="true"> · </span>
                            <span>{comp.organiser || 'Unspecified Organiser'}</span>
                          </div>
                        </button>
                      </td>

                      {/* Direct Accessible Status Selector */}
                      <td className="py-3.5 px-4">
                        <label
                          htmlFor={`status-select-${comp.id}`}
                          className="sr-only"
                        >
                          Status for {comp.name}
                        </label>
                        <select
                          id={`status-select-${comp.id}`}
                          value={comp.status}
                          onChange={(e) =>
                            onStatusChange(
                              comp.id,
                              e.target.value as MissionStatus
                            )
                          }
                          className={`px-2.5 py-1 rounded bg-[#080B16] border font-mono text-xs font-semibold cursor-pointer focus:outline-none ${
                            comp.status === 'ONGOING'
                              ? 'border-[#57DDF5]/40 text-[#57DDF5]'
                              : comp.status === 'SUBMITTED'
                              ? 'border-[#9B7CFF]/40 text-[#9B7CFF]'
                              : 'border-[#A6FF4D]/40 text-[#A6FF4D]'
                          }`}
                        >
                          <option value="ONGOING">◆ ONGOING</option>
                          <option value="SUBMITTED">▲ SUBMITTED</option>
                          <option value="COMPLETED">✓ COMPLETED</option>
                        </select>
                      </td>

                      <td className="py-3.5 px-4">
                        <DeadlineReadout competition={comp} />
                      </td>

                      <td className="py-3.5 px-4">
                        <div className="flex flex-wrap items-center gap-2">
                          {validDocUrl ? (
                            <a
                              href={comp.progressDocUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#A6FF4D]/30 text-[#A6FF4D] font-medium whitespace-nowrap"
                              title="Open Progress Document in new tab"
                            >
                              <FileText className="w-3 h-3" />
                              <span>Progress Doc</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          ) : (
                            <span className="text-[11px] text-[#929DB7]">
                              No Progress Link
                            </span>
                          )}

                          {validCompUrl && (
                            <a
                              href={comp.competitionUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#F3F5FC] whitespace-nowrap"
                              title="Open Official Competition Website"
                            >
                              <span>Portal</span>
                              <ExternalLink className="w-2.5 h-2.5 text-[#9B7CFF]" />
                            </a>
                          )}

                          {gcalUrl && (
                            <a
                              href={gcalUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#57DDF5]/30 text-[#57DDF5] whitespace-nowrap"
                              title="Add Deadline to Google Calendar (opens template in new tab)"
                            >
                              <Calendar className="w-3 h-3" />
                              <span>Calendar</span>
                            </a>
                          )}
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <div className="inline-flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => onSelectCompetition(comp.id)}
                            className="px-2.5 py-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#F3F5FC] inline-flex items-center gap-1 cursor-pointer whitespace-nowrap"
                            title="View Full Dossier"
                          >
                            <Eye className="w-3.5 h-3.5 text-[#57DDF5]" />
                            <span>View</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => onEditCompetition(comp.id)}
                            className="p-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#929DB7] hover:text-[#F3F5FC] cursor-pointer"
                            aria-label={`Edit ${comp.name}`}
                            title="Edit Competition"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setArchiveConfirmTarget(comp)}
                            className="p-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#929DB7] hover:text-[#FFBE55] cursor-pointer"
                            aria-label={`Archive ${comp.name}`}
                            title="Archive Competition"
                          >
                            <Archive className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile & Tablet Touch-Friendly Cards */}
          <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredAndSorted.map((comp) => {
              const gcalUrl = generateGoogleCalendarUrl(comp);
              const validDocUrl = isValidHttpUrl(comp.progressDocUrl);
              const validCompUrl = isValidHttpUrl(comp.competitionUrl);

              return (
                <div
                  key={comp.id}
                  className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4 flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2 text-xs font-mono text-[#929DB7]">
                      <span className="text-[#57DDF5] font-semibold">
                        {comp.id}
                      </span>
                      <select
                        aria-label={`Status for ${comp.name}`}
                        value={comp.status}
                        onChange={(e) =>
                          onStatusChange(
                            comp.id,
                            e.target.value as MissionStatus
                          )
                        }
                        className="px-2 py-1 rounded bg-[#080B16] border border-[#929DB7]/30 font-mono text-xs text-[#F3F5FC]"
                      >
                        <option value="ONGOING">◆ ONGOING</option>
                        <option value="SUBMITTED">▲ SUBMITTED</option>
                        <option value="COMPLETED">✓ COMPLETED</option>
                      </select>
                    </div>

                    <button
                      type="button"
                      onClick={() => onSelectCompetition(comp.id)}
                      className="text-left block w-full cursor-pointer"
                    >
                      <h3 className="font-display text-base font-bold text-[#F3F5FC] hover:text-[#A6FF4D]">
                        {comp.name}
                      </h3>
                      <p className="text-xs text-[#929DB7] mt-0.5">
                        {comp.organiser || 'Unspecified Organiser'}
                      </p>
                    </button>

                    <div className="pt-2">
                      <DeadlineReadout competition={comp} />
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#929DB7]/15 space-y-2.5">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      {validDocUrl ? (
                        <a
                          href={comp.progressDocUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-[#101629] border border-[#A6FF4D]/30 text-[#A6FF4D] font-medium whitespace-nowrap"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>Open Progress</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-[11px] text-[#929DB7]">
                          No progress link
                        </span>
                      )}

                      {validCompUrl && (
                        <a
                          href={comp.competitionUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-[#101629] border border-[#929DB7]/25 text-[#F3F5FC] whitespace-nowrap"
                        >
                          <span>Portal</span>
                          <ExternalLink className="w-3 h-3 text-[#9B7CFF]" />
                        </a>
                      )}

                      {gcalUrl && (
                        <a
                          href={gcalUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-[#101629] border border-[#57DDF5]/30 text-[#57DDF5] whitespace-nowrap"
                        >
                          <Calendar className="w-3.5 h-3.5" />
                          <span>Calendar</span>
                        </a>
                      )}
                    </div>

                    <div className="flex items-center justify-between gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => onSelectCompetition(comp.id)}
                        className="flex-1 py-2 px-3 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs font-medium text-[#F3F5FC] cursor-pointer"
                      >
                        View Details
                      </button>
                      <button
                        type="button"
                        onClick={() => onEditCompetition(comp.id)}
                        className="py-2 px-3 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs font-medium text-[#57DDF5] cursor-pointer"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setArchiveConfirmTarget(comp)}
                        className="py-2 px-3 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs font-medium text-[#FFBE55] cursor-pointer"
                      >
                        Archive
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Confirmation Dialog before Archiving */}
      {archiveConfirmTarget && (
        <div
          className="fixed inset-0 z-50 bg-[#080B16]/80 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="max-w-md w-full bg-[#151D32] border border-[#929DB7]/30 rounded-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#FFBE55] shrink-0 mt-0.5" />
              <div>
                <h3 className="font-display text-lg font-bold text-[#F3F5FC]">
                  Move Mission to Archive?
                </h3>
                <p className="text-xs text-[#929DB7] mt-1 leading-relaxed">
                  <strong>{archiveConfirmTarget.name}</strong> (
                  {archiveConfirmTarget.id}) will be moved to the Completed Missions Archive. All links and notes are preserved and can be restored anytime.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setArchiveConfirmTarget(null)}
                className="px-4 py-2 text-xs font-medium text-[#F3F5FC] bg-[#101629] border border-[#929DB7]/25 rounded-md cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  const targetId = archiveConfirmTarget.id;
                  setArchiveConfirmTarget(null);
                  await onArchiveCompetition(targetId);
                }}
                className="px-4 py-2 text-xs font-display font-bold text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded-md cursor-pointer"
              >
                Confirm Archive
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
