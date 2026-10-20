import React, { useMemo, useState } from 'react';
import {
  Archive,
  RotateCcw,
  Search,
  ExternalLink,
  FileText,
  Eye,
  CheckCircle2,
} from 'lucide-react';
import { Competition } from '../types/mission';
import {
  formatLocalDate,
  formatTimestamp,
  isValidHttpUrl,
} from '../utils/deadline';
import { StatusReadout } from './StarCommandInsignia';

interface ArchiveViewProps {
  competitions: Competition[];
  onSelectCompetition: (id: string) => void;
  onRestoreCompetition: (id: string) => Promise<void>;
  onArchiveCompletedCompetition: (id: string) => Promise<void>;
}

export const ArchiveView: React.FC<ArchiveViewProps> = ({
  competitions,
  onSelectCompetition,
  onRestoreCompetition,
  onArchiveCompletedCompetition,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [restoringId, setRestoringId] = useState<string | null>(null);

  const archivedCompetitions = useMemo(
    () => competitions.filter((c) => c.archived),
    [competitions]
  );

  const activeCompletedCandidates = useMemo(
    () =>
      competitions.filter((c) => !c.archived && c.status === 'COMPLETED'),
    [competitions]
  );

  const activeCount = useMemo(
    () => competitions.filter((c) => !c.archived).length,
    [competitions]
  );

  const filteredArchive = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return archivedCompetitions;
    return archivedCompetitions.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.organiser.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q) ||
        c.notes.toLowerCase().includes(q)
    );
  }, [archivedCompetitions, searchQuery]);

  const handleRestore = async (id: string) => {
    if (restoringId) return;
    setRestoringId(id);
    try {
      await onRestoreCompetition(id);
    } finally {
      setRestoringId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Accurate Active/Archived Counts */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-wide text-[#F3F5FC]">
            Completed Missions Archive
          </h1>
          <p className="text-sm text-[#929DB7] mt-0.5">
            Historical vault of archived KRYPTØNIX competitions. All progress links and notes remain intact and can be restored to active tracking at any time.
          </p>
        </div>

        <div className="flex items-center gap-4 bg-[#151D32] border border-[#929DB7]/20 rounded-md px-4 py-2.5 text-xs font-mono shrink-0">
          <div>
            <span className="text-[#929DB7]">ACTIVE: </span>
            <span className="text-[#57DDF5] font-bold tabular-nums">
              {activeCount}
            </span>
          </div>
          <span aria-hidden="true" className="text-[#929DB7]/40">
            ·
          </span>
          <div>
            <span className="text-[#929DB7]">ARCHIVED: </span>
            <span className="text-[#A6FF4D] font-bold tabular-nums">
              {archivedCompetitions.length}
            </span>
          </div>
        </div>
      </div>

      {/* Ready-to-Archive Completed Active Missions Banner */}
      {activeCompletedCandidates.length > 0 && (
        <div className="bg-[#151D32] border border-[#A6FF4D]/30 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#A6FF4D]">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>
                {activeCompletedCandidates.length} Completed Active Mission
                {activeCompletedCandidates.length > 1 ? 's' : ''} Ready for Archive
              </span>
            </div>
            <span className="text-[11px] text-[#929DB7]">
              Archiving removes them from active dashboard counts without deleting data
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {activeCompletedCandidates.map((cand) => (
              <div
                key={cand.id}
                className="p-3 rounded bg-[#101629] border border-[#929DB7]/20 flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-[#F3F5FC] truncate">
                    {cand.name}
                  </div>
                  <div className="text-[11px] font-mono text-[#929DB7] truncate">
                    {cand.id} · {cand.organiser || 'Unspecified Organiser'}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onArchiveCompletedCompetition(cand.id)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#A6FF4D] hover:bg-[#b8ff6e] text-[#080B16] font-display font-bold text-xs whitespace-nowrap shrink-0 cursor-pointer"
                >
                  <Archive className="w-3.5 h-3.5" />
                  <span>Archive Now</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search Archived Missions */}
      <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-[#929DB7] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="search"
            aria-label="Search archived competitions"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search archived missions by name, organiser, ID, or notes..."
            className="w-full pl-10 pr-4 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded-md text-xs text-[#F3F5FC] placeholder-[#929DB7]/60 focus:outline-none focus:border-[#57DDF5]"
          />
        </div>
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="px-3 py-2 text-xs font-medium text-[#57DDF5] bg-[#101629] rounded-md cursor-pointer whitespace-nowrap"
          >
            Clear Search
          </button>
        )}
      </div>

      {/* Archived List */}
      {archivedCompetitions.length === 0 ? (
        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-10 text-center space-y-2">
          <Archive className="w-8 h-8 text-[#929DB7] mx-auto mb-2" />
          <h2 className="font-display text-lg font-bold text-[#F3F5FC]">
            Archive Vault is Empty
          </h2>
          <p className="text-xs text-[#929DB7] max-w-md mx-auto">
            Completed competitions that you archive will be stored here with their full progress documents and notes preserved.
          </p>
        </div>
      ) : filteredArchive.length === 0 ? (
        <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-8 text-center space-y-3">
          <p className="text-sm text-[#F3F5FC] font-medium">
            No archived records match "{searchQuery}"
          </p>
          <button
            type="button"
            onClick={() => setSearchQuery('')}
            className="px-3.5 py-1.5 text-xs font-medium text-[#080B16] bg-[#57DDF5] rounded cursor-pointer"
          >
            Reset Search
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredArchive.map((comp) => {
            const hasDoc = isValidHttpUrl(comp.progressDocUrl);
            const hasPortal = isValidHttpUrl(comp.competitionUrl);

            return (
              <div
                key={comp.id}
                className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-5 flex flex-col justify-between space-y-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2 text-xs font-mono text-[#929DB7]">
                    <span>
                      <strong className="text-[#57DDF5]">{comp.id}</strong> ·{' '}
                      {comp.organiser || 'Unspecified Organiser'}
                    </span>
                    <StatusReadout status={comp.status} compact />
                  </div>

                  <button
                    type="button"
                    onClick={() => onSelectCompetition(comp.id)}
                    className="text-left block w-full cursor-pointer"
                  >
                    <h3 className="font-display text-lg font-bold text-[#F3F5FC] hover:text-[#A6FF4D] transition-colors">
                      {comp.name}
                    </h3>
                  </button>

                  <div className="text-xs font-mono text-[#929DB7] tabular-nums">
                    Historical Deadline: {formatLocalDate(comp.deadline)} · Last Updated:{' '}
                    {formatTimestamp(comp.updatedAt)}
                  </div>

                  {comp.notes && (
                    <p className="text-xs text-[#929DB7] line-clamp-2 pt-1">
                      {comp.notes}
                    </p>
                  )}
                </div>

                <div className="pt-3 border-t border-[#929DB7]/15 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs">
                    {hasDoc && (
                      <a
                        href={comp.progressDocUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#A6FF4D]/30 text-[#A6FF4D] font-medium whitespace-nowrap"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        <span>Progress Doc</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    {hasPortal && (
                      <a
                        href={comp.competitionUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#F3F5FC] whitespace-nowrap"
                      >
                        <span>Portal</span>
                        <ExternalLink className="w-3 h-3 text-[#9B7CFF]" />
                      </a>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onSelectCompetition(comp.id)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-xs font-medium text-[#F3F5FC] cursor-pointer whitespace-nowrap"
                    >
                      <Eye className="w-3.5 h-3.5 text-[#57DDF5]" />
                      <span>Inspect</span>
                    </button>
                    <button
                      type="button"
                      disabled={restoringId === comp.id}
                      onClick={() => handleRestore(comp.id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#A6FF4D] hover:bg-[#b8ff6e] text-[#080B16] font-display font-bold text-xs cursor-pointer whitespace-nowrap disabled:opacity-50"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>
                        {restoringId === comp.id ? 'Restoring...' : 'Restore'}
                      </span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
