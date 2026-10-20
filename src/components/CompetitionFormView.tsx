import React, { useState } from 'react';
import {
  ArrowLeft,
  Save,
  AlertCircle,
  ExternalLink,
  Check,
} from 'lucide-react';
import { Competition, MissionStatus } from '../types/mission';
import {
  formatTimestamp,
  isValidHttpUrl,
  parseLocalDate,
} from '../utils/deadline';

interface CompetitionFormViewProps {
  mode: 'add' | 'edit';
  initialCompetition?: Competition | null;
  existingCompetitions: Competition[];
  onSave: (data: {
    name: string;
    organiser: string;
    competitionUrl: string;
    deadline: string;
    status: MissionStatus;
    progressDocUrl: string;
    notes: string;
  }) => Promise<void>;
  onCancel: () => void;
}

interface FormErrors {
  name?: string;
  competitionUrl?: string;
  deadline?: string;
  progressDocUrl?: string;
  duplicate?: string;
  server?: string;
}

export const CompetitionFormView: React.FC<CompetitionFormViewProps> = ({
  mode,
  initialCompetition,
  existingCompetitions,
  onSave,
  onCancel,
}) => {
  const [name, setName] = useState(initialCompetition?.name || '');
  const [organiser, setOrganiser] = useState(initialCompetition?.organiser || '');
  const [competitionUrl, setCompetitionUrl] = useState(
    initialCompetition?.competitionUrl || ''
  );
  const [deadline, setDeadline] = useState(initialCompetition?.deadline || '');
  const [status, setStatus] = useState<MissionStatus>(
    initialCompetition?.status || 'ONGOING'
  );
  const [progressDocUrl, setProgressDocUrl] = useState(
    initialCompetition?.progressDocUrl || ''
  );
  const [notes, setNotes] = useState(initialCompetition?.notes || '');

  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = (): FormErrors => {
    const nextErrors: FormErrors = {};
    const trimmedName = name.trim();

    if (!trimmedName) {
      nextErrors.name = 'Competition name is required.';
    } else if (trimmedName.length < 2) {
      nextErrors.name = 'Competition name must be at least 2 characters.';
    }

    // Check accidental duplicate competition name
    if (trimmedName) {
      const duplicateMatch = existingCompetitions.find(
        (c) =>
          c.id !== initialCompetition?.id &&
          !c.archived &&
          c.name.trim().toLowerCase() === trimmedName.toLowerCase()
      );
      if (duplicateMatch) {
        nextErrors.duplicate = `An active competition named "${duplicateMatch.name}" (${duplicateMatch.id}) already exists.`;
      }
    }

    if (competitionUrl.trim() && !isValidHttpUrl(competitionUrl.trim())) {
      nextErrors.competitionUrl =
        'Enter a valid URL starting with https:// or http://';
    }

    if (deadline.trim()) {
      const parsed = parseLocalDate(deadline.trim());
      if (!parsed) {
        nextErrors.deadline = 'Enter a valid calendar date in YYYY-MM-DD format.';
      }
    }

    if (progressDocUrl.trim() && !isValidHttpUrl(progressDocUrl.trim())) {
      nextErrors.progressDocUrl =
        'Enter a valid document URL starting with https:// or http:// (e.g., Google Docs, Drive, GitHub).';
    }

    return nextErrors;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setIsSubmitting(true);
    try {
      await onSave({
        name: name.trim(),
        organiser: organiser.trim(),
        competitionUrl: competitionUrl.trim(),
        deadline: deadline.trim(),
        status,
        progressDocUrl: progressDocUrl.trim(),
        notes: notes.trim(),
      });
    } catch (err) {
      // Preserve form state and show server/network error
      setErrors({
        server:
          err instanceof Error
            ? err.message
            : 'Failed to save competition to data store. Your entered values have been preserved.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const statusOptions: {
    value: MissionStatus;
    label: string;
    desc: string;
    glyph: string;
    activeClass: string;
  }[] = [
    {
      value: 'ONGOING',
      label: 'ONGOING',
      desc: 'Active preparation, research, or engineering in progress',
      glyph: '◆',
      activeClass: 'border-[#57DDF5] bg-[#57DDF5]/15 text-[#F3F5FC]',
    },
    {
      value: 'SUBMITTED',
      label: 'SUBMITTED',
      desc: 'Deliverables transmitted; awaiting jury evaluation',
      glyph: '▲',
      activeClass: 'border-[#9B7CFF] bg-[#9B7CFF]/15 text-[#F3F5FC]',
    },
    {
      value: 'COMPLETED',
      label: 'COMPLETED',
      desc: 'Concluded mission ready for review or archive',
      glyph: '✓',
      activeClass: 'border-[#A6FF4D] bg-[#A6FF4D]/15 text-[#F3F5FC]',
    },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Top Back Action & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-2 text-xs font-medium text-[#929DB7] hover:text-[#F3F5FC] mb-2 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to previous screen</span>
          </button>
          <h1 className="font-display text-2xl font-bold tracking-wide text-[#F3F5FC]">
            {mode === 'add'
              ? 'Register New Competition Mission'
              : `Edit Mission · ${initialCompetition?.id}`}
          </h1>
          <p className="text-sm text-[#929DB7] mt-0.5">
            {mode === 'add'
              ? 'Log a new student technology competition, deadline, and progress document link for KRYPTØNIX.'
              : 'Update competition metadata, submission status, deadline, or progress links.'}
          </p>
        </div>

        {mode === 'edit' && initialCompetition && (
          <div className="text-xs font-mono text-[#929DB7] bg-[#151D32] border border-[#929DB7]/20 rounded-md px-3.5 py-2 shrink-0">
            <div>Created: {formatTimestamp(initialCompetition.createdAt)}</div>
            <div>Updated: {formatTimestamp(initialCompetition.updatedAt)}</div>
          </div>
        )}
      </div>

      {/* Form Panel */}
      <form
        onSubmit={handleSubmit}
        noValidate
        className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-6 sm:p-8 space-y-6"
      >
        {(errors.duplicate || errors.server) && (
          <div
            role="alert"
            className="p-3.5 rounded-md bg-[#FF5C70]/10 border border-[#FF5C70]/40 text-xs text-[#FF5C70] flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errors.server || errors.duplicate}</span>
          </div>
        )}

        {/* Competition Name & Organiser */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label
              htmlFor="comp-name"
              className="block text-xs font-semibold text-[#F3F5FC] mb-1.5"
            >
              Competition Name <span className="text-[#FF5C70]">*</span>
            </label>
            <input
              id="comp-name"
              type="text"
              required
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (errors.name || errors.duplicate) {
                  setErrors((prev) => ({
                    ...prev,
                    name: undefined,
                    duplicate: undefined,
                  }));
                }
              }}
              placeholder="e.g., Global Autonomous Rover Challenge 2026"
              className={`w-full px-3.5 py-2.5 bg-[#080B16] border rounded-md text-sm text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:ring-1 ${
                errors.name
                  ? 'border-[#FF5C70] focus:border-[#FF5C70] focus:ring-[#FF5C70]'
                  : 'border-[#929DB7]/30 focus:border-[#57DDF5] focus:ring-[#57DDF5]'
              }`}
            />
            {errors.name && (
              <p className="mt-1.5 text-xs text-[#FF5C70] flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errors.name}</span>
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="comp-organiser"
              className="block text-xs font-semibold text-[#F3F5FC] mb-1.5"
            >
              Organiser / Host Institution
            </label>
            <input
              id="comp-organiser"
              type="text"
              value={organiser}
              onChange={(e) => setOrganiser(e.target.value)}
              placeholder="e.g., IEEE / NASA / Major League Hacking"
              className="w-full px-3.5 py-2.5 bg-[#080B16] border border-[#929DB7]/30 rounded-md text-sm text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:border-[#57DDF5] focus:ring-1 focus:ring-[#57DDF5]"
            />
          </div>
        </div>

        {/* Mission Status Selection */}
        <div>
          <span className="block text-xs font-semibold text-[#F3F5FC] mb-2">
            Mission Status <span className="text-[#FF5C70]">*</span>
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {statusOptions.map((opt) => {
              const isSelected = status === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setStatus(opt.value)}
                  className={`p-3.5 rounded-md border text-left transition-colors cursor-pointer ${
                    isSelected
                      ? opt.activeClass
                      : 'bg-[#101629] border-[#929DB7]/20 text-[#929DB7] hover:text-[#F3F5FC] hover:border-[#929DB7]/40'
                  }`}
                >
                  <div className="flex items-center justify-between font-mono text-xs font-bold mb-1">
                    <span>
                      {opt.glyph} {opt.label}
                    </span>
                    {isSelected && <Check className="w-3.5 h-3.5" />}
                  </div>
                  <p className="text-[11px] leading-snug opacity-85">
                    {opt.desc}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Deadline & Official Competition URL */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label
              htmlFor="comp-deadline"
              className="block text-xs font-semibold text-[#F3F5FC] mb-1.5"
            >
              Registration or Submission Deadline
            </label>
            <input
              id="comp-deadline"
              type="date"
              value={deadline}
              onChange={(e) => {
                setDeadline(e.target.value);
                if (errors.deadline) {
                  setErrors((prev) => ({ ...prev, deadline: undefined }));
                }
              }}
              className={`w-full px-3.5 py-2.5 bg-[#080B16] border rounded-md font-mono text-sm text-[#F3F5FC] focus:outline-none focus:ring-1 ${
                errors.deadline
                  ? 'border-[#FF5C70] focus:border-[#FF5C70] focus:ring-[#FF5C70]'
                  : 'border-[#929DB7]/30 focus:border-[#57DDF5] focus:ring-[#57DDF5]'
              }`}
            />
            <p className="mt-1 text-[11px] text-[#929DB7]">
              Evaluated in your local timezone. Leave blank if no fixed deadline exists.
            </p>
            {errors.deadline && (
              <p className="mt-1 text-xs text-[#FF5C70] flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errors.deadline}</span>
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="comp-url"
              className="block text-xs font-semibold text-[#F3F5FC] mb-1.5"
            >
              Official Competition URL
            </label>
            <input
              id="comp-url"
              type="url"
              value={competitionUrl}
              onChange={(e) => {
                setCompetitionUrl(e.target.value);
                if (errors.competitionUrl) {
                  setErrors((prev) => ({ ...prev, competitionUrl: undefined }));
                }
              }}
              placeholder="https://example.org/competition"
              className={`w-full px-3.5 py-2.5 bg-[#080B16] border rounded-md font-mono text-xs text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:ring-1 ${
                errors.competitionUrl
                  ? 'border-[#FF5C70] focus:border-[#FF5C70] focus:ring-[#FF5C70]'
                  : 'border-[#929DB7]/30 focus:border-[#57DDF5] focus:ring-[#57DDF5]'
              }`}
            />
            {errors.competitionUrl && (
              <p className="mt-1.5 text-xs text-[#FF5C70] flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errors.competitionUrl}</span>
              </p>
            )}
          </div>
        </div>

        {/* Progress Document URL */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label
              htmlFor="comp-progress-url"
              className="block text-xs font-semibold text-[#F3F5FC]"
            >
              Progress Document / Repository URL
            </label>
            {progressDocUrl.trim() && isValidHttpUrl(progressDocUrl.trim()) && (
              <a
                href={progressDocUrl.trim()}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-[#57DDF5] hover:underline"
              >
                <span>Test Link</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
          <input
            id="comp-progress-url"
            type="url"
            value={progressDocUrl}
            onChange={(e) => {
              setProgressDocUrl(e.target.value);
              if (errors.progressDocUrl) {
                setErrors((prev) => ({ ...prev, progressDocUrl: undefined }));
              }
            }}
            placeholder="https://docs.google.com/document/d/... or https://github.com/..."
            className={`w-full px-3.5 py-2.5 bg-[#080B16] border rounded-md font-mono text-xs text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:ring-1 ${
              errors.progressDocUrl
                ? 'border-[#FF5C70] focus:border-[#FF5C70] focus:ring-[#FF5C70]'
                : 'border-[#929DB7]/30 focus:border-[#57DDF5] focus:ring-[#57DDF5]'
            }`}
          />
          <p className="mt-1 text-[11px] text-[#929DB7]">
            Supports Google Docs, Google Drive folders, GitHub repositories, Figma decks, or Notion pages.
          </p>
          {errors.progressDocUrl && (
            <p className="mt-1.5 text-xs text-[#FF5C70] flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{errors.progressDocUrl}</span>
            </p>
          )}
        </div>

        {/* Mission Notes */}
        <div>
          <label
            htmlFor="comp-notes"
            className="block text-xs font-semibold text-[#F3F5FC] mb-1.5"
          >
            Mission Notes & Deliverables Checklist (Optional)
          </label>
          <textarea
            id="comp-notes"
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Record deliverable requirements, pitch constraints, team member assignments, or submission portal instructions..."
            className="w-full px-3.5 py-2.5 bg-[#080B16] border border-[#929DB7]/30 rounded-md text-sm text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:border-[#57DDF5] focus:ring-1 focus:ring-[#57DDF5]"
          />
        </div>

        {/* Form Actions */}
        <div className="pt-4 border-t border-[#929DB7]/20 flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 text-xs font-medium text-[#F3F5FC] bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 rounded-md transition-colors cursor-pointer whitespace-nowrap"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 px-5 py-2 text-xs font-display font-bold tracking-wide text-[#080B16] bg-[#A6FF4D] hover:bg-[#b8ff6e] rounded-md transition-colors disabled:opacity-50 cursor-pointer whitespace-nowrap"
          >
            <Save className="w-3.5 h-3.5" />
            <span>
              {isSubmitting
                ? 'Saving Mission...'
                : mode === 'add'
                ? 'Add Competition'
                : 'Save Changes'}
            </span>
          </button>
        </div>
      </form>
    </div>
  );
};
