import React, { useState } from 'react';
import {
  ArrowLeft,
  Calendar,
  ExternalLink,
  FileText,
  Edit3,
  Archive,
  RotateCcw,
  AlertTriangle,
  Globe,
  Clock,
  Check,
} from 'lucide-react';
import { Competition, MissionStatus } from '../types/mission';
import {
  classifyDeadline,
  formatTimestamp,
  generateGoogleCalendarUrl,
  isValidHttpUrl,
} from '../utils/deadline';
import { DeadlineReadout, StatusReadout } from './StarCommandInsignia';

interface CompetitionDetailViewProps {
  competition: Competition;
  onBack: () => void;
  onEdit: (id: string) => void;
  onStatusChange: (id: string, status: MissionStatus) => Promise<void>;
  onToggleArchive: (id: string, archive: boolean) => Promise<void>;
}

export const CompetitionDetailView: React.FC<CompetitionDetailViewProps> = ({
  competition,
  onBack,
  onEdit,
  onStatusChange,
  onToggleArchive,
}) => {
  const [confirmArchiveModal, setConfirmArchiveModal] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  const deadlineInfo = classifyDeadline(competition);
  const googleCalendarUrl = generateGoogleCalendarUrl(competition);
  const hasValidCompUrl = isValidHttpUrl(competition.competitionUrl);
  const hasValidProgressUrl = isValidHttpUrl(competition.progressDocUrl);

  const handleQuickStatus = async (nextStatus: MissionStatus) => {
    if (isUpdating || competition.status === nextStatus) return;
    setIsUpdating(true);
    try {
      await onStatusChange(competition.id, nextStatus);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleConfirmArchiveToggle = async () => {
    if (isUpdating) return;
    setIsUpdating(true);
    try {
      await onToggleArchive(competition.id, !competition.archived);
      setConfirmArchiveModal(false);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 text-xs font-medium text-[#929DB7] hover:text-[#F3F5FC] cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Mission List</span>
        </button>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => onEdit(competition.id)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-[#F3F5FC] bg-[#151D32] hover:bg-[#1E2942] border border-[#929DB7]/30 rounded-md transition-colors cursor-pointer whitespace-nowrap"
          >
            <Edit3 className="w-3.5 h-3.5 text-[#57DDF5]" />
            <span>Edit Mission</span>
          </button>

          <button
            type="button"
            onClick={() => setConfirmArchiveModal(true)}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-md border transition-colors cursor-pointer whitespace-nowrap ${
              competition.archived
                ? 'bg-[#A6FF4D]/15 border-[#A6FF4D]/40 text-[#A6FF4D] hover:bg-[#A6FF4D]/25'
                : 'bg-[#151D32] border-[#929DB7]/30 text-[#FFBE55] hover:bg-[#1E2942]'
            }`}
          >
            {competition.archived ? (
              <>
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Restore to Active Missions</span>
              </>
            ) : (
              <>
                <Archive className="w-3.5 h-3.5" />
                <span>Archive Mission</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Mission Dossier Panel */}
      <div className="bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-6 sm:p-8 space-y-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-6 border-b border-[#929DB7]/20">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#929DB7]">
              <span className="text-[#57DDF5] font-semibold">
                {competition.id}
              </span>
              <span aria-hidden="true">·</span>
              <span>
                {competition.organiser || 'Independent / Unspecified Organiser'}
              </span>
              {competition.archived && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="text-[#FFBE55] font-semibold">
                    ARCHIVED RECORD
                  </span>
                </>
              )}
            </div>

            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-wide text-[#F3F5FC]">
              {competition.name}
            </h1>
          </div>

          <div className="flex flex-col md:items-end gap-1.5 shrink-0">
            <StatusReadout status={competition.status} />
            <span className="font-mono text-[11px] text-[#929DB7] tabular-nums">
              Updated {formatTimestamp(competition.updatedAt)}
            </span>
          </div>
        </div>

        {/* Status Control Strip */}
        <div className="bg-[#101629] border border-[#929DB7]/15 rounded-md p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xs font-semibold text-[#F3F5FC]">
              Update Mission Status
            </h2>
            <p className="text-xs text-[#929DB7]">
              Changes immediately recalculate Mission Control Dashboard statistics.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {(['ONGOING', 'SUBMITTED', 'COMPLETED'] as MissionStatus[]).map(
              (st) => {
                const active = competition.status === st;
                return (
                  <button
                    key={st}
                    type="button"
                    disabled={isUpdating}
                    onClick={() => handleQuickStatus(st)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded font-mono text-xs font-semibold border transition-colors cursor-pointer whitespace-nowrap ${
                      active
                        ? st === 'ONGOING'
                          ? 'bg-[#57DDF5]/20 border-[#57DDF5] text-[#F3F5FC]'
                          : st === 'SUBMITTED'
                          ? 'bg-[#9B7CFF]/20 border-[#9B7CFF] text-[#F3F5FC]'
                          : 'bg-[#A6FF4D]/20 border-[#A6FF4D] text-[#F3F5FC]'
                        : 'bg-[#080B16] border-[#929DB7]/25 text-[#929DB7] hover:text-[#F3F5FC]'
                    }`}
                  >
                    {active && <Check className="w-3 h-3" />}
                    <span>{st}</span>
                  </button>
                );
              }
            )}
          </div>
        </div>

        {/* Telemetry Grid: Deadline + Calendar + External Resources */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Deadline & Google Calendar Box */}
          <div className="bg-[#101629] border border-[#929DB7]/15 rounded-md p-5 flex flex-col justify-between space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[#929DB7]">
                  Submission / Registration Deadline
                </span>
                <Clock className="w-4 h-4 text-[#57DDF5]" />
              </div>
              <DeadlineReadout competition={competition} />
              {deadlineInfo.isHistorical && (
                <p className="text-xs text-[#929DB7] pt-1">
                  This competition is marked as {competition.status.toLowerCase()}, so its deadline is preserved as historical metadata and does not trigger overdue alerts.
                </p>
              )}
            </div>

            <div className="pt-3 border-t border-[#929DB7]/15">
              {googleCalendarUrl ? (
                <div className="space-y-2">
                  <a
                    href={googleCalendarUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 w-full px-4 py-2 text-xs font-medium text-[#080B16] bg-[#57DDF5] hover:bg-[#7be6f8] rounded-md transition-colors whitespace-nowrap"
                  >
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Add Deadline to Google Calendar</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                  <p className="text-[11px] text-[#929DB7]">
                    Opens Google Calendar template in a new tab. Review and click Save in Google Calendar to confirm the event.
                  </p>
                </div>
              ) : (
                <p className="text-xs text-[#929DB7]">
                  Set a valid deadline date on this mission to enable Google Calendar event template generation.
                </p>
              )}
            </div>
          </div>

          {/* Progress Document & Competition Portal Box */}
          <div className="bg-[#101629] border border-[#929DB7]/15 rounded-md p-5 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <span className="text-xs font-semibold text-[#929DB7] block">
                External Mission Links & Progress Dossier
              </span>

              {/* Progress Document Link */}
              <div className="p-3 rounded bg-[#080B16] border border-[#929DB7]/20">
                <div className="text-xs font-medium text-[#F3F5FC] mb-1">
                  Team Progress Document
                </div>
                {hasValidProgressUrl ? (
                  <div className="space-y-2">
                    <p className="font-mono text-[11px] text-[#929DB7] truncate">
                      {competition.progressDocUrl}
                    </p>
                    <a
                      href={competition.progressDocUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded transition-colors whitespace-nowrap"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Open Progress Document</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                ) : (
                  <p className="text-xs text-[#929DB7]">
                    No progress document linked yet. Edit this mission to attach a Google Doc, Drive folder, or GitHub repository.
                  </p>
                )}
              </div>

              {/* Official Competition Website */}
              <div className="p-3 rounded bg-[#080B16] border border-[#929DB7]/20">
                <div className="text-xs font-medium text-[#F3F5FC] mb-1">
                  Official Competition Portal
                </div>
                {hasValidCompUrl ? (
                  <div className="space-y-2">
                    <p className="font-mono text-[11px] text-[#929DB7] truncate">
                      {competition.competitionUrl}
                    </p>
                    <a
                      href={competition.competitionUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#F3F5FC] bg-[#151D32] hover:bg-[#1E2942] border border-[#929DB7]/30 rounded transition-colors whitespace-nowrap"
                    >
                      <Globe className="w-3.5 h-3.5 text-[#9B7CFF]" />
                      <span>Open Competition Link</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                ) : (
                  <p className="text-xs text-[#929DB7]">
                    No external competition portal URL provided.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Mission Notes */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold text-[#929DB7]">
            Mission Briefing & Team Notes
          </h2>
          <div className="p-4 rounded-md bg-[#101629] border border-[#929DB7]/15 text-sm text-[#F3F5FC] whitespace-pre-wrap leading-relaxed">
            {competition.notes ? (
              competition.notes
            ) : (
              <span className="text-[#929DB7] italic">
                No mission notes recorded for this competition yet.
              </span>
            )}
          </div>
        </div>

        {/* Audit Metadata Footer */}
        <div className="pt-4 border-t border-[#929DB7]/15 flex flex-wrap items-center justify-between gap-4 text-xs font-mono text-[#929DB7]">
          <span>MISSION ID: {competition.id}</span>
          <span>
            CREATED: {formatTimestamp(competition.createdAt)} · LAST UPDATED:{' '}
            {formatTimestamp(competition.updatedAt)}
          </span>
        </div>
      </div>

      {/* Confirmation Modal for Archiving / Restoring */}
      {confirmArchiveModal && (
        <div
          className="fixed inset-0 z-50 bg-[#080B16]/80 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="archive-modal-title"
        >
          <div className="max-w-md w-full bg-[#151D32] border border-[#929DB7]/30 rounded-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[#FFBE55] shrink-0 mt-0.5" />
              <div>
                <h3
                  id="archive-modal-title"
                  className="font-display text-lg font-bold text-[#F3F5FC]"
                >
                  {competition.archived
                    ? 'Restore Competition to Active List?'
                    : 'Archive Competition Record?'}
                </h3>
                <p className="text-xs text-[#929DB7] mt-1 leading-relaxed">
                  {competition.archived
                    ? `"${competition.name}" will be moved back to active Mission Control tracking with all original metadata preserved.`
                    : `"${competition.name}" will be moved to the Completed Missions Archive. No data is deleted, and you can restore it at any time.`}
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setConfirmArchiveModal(false)}
                className="px-4 py-2 text-xs font-medium text-[#F3F5FC] bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 rounded-md cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isUpdating}
                onClick={handleConfirmArchiveToggle}
                className="px-4 py-2 text-xs font-display font-bold text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded-md cursor-pointer"
              >
                {competition.archived
                  ? 'Confirm Restore'
                  : 'Confirm Archive'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
