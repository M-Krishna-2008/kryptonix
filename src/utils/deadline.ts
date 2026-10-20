import { Competition, DeadlineCategory } from '../types/mission';

export interface DeadlineInfo {
  category: DeadlineCategory;
  label: string;
  countdownText: string;
  daysDiff: number | null;
  formattedDate: string;
  isHistorical: boolean;
  isUrgentWarning: boolean;
}

/**
 * Parses a YYYY-MM-DD string strictly in the user's local timezone at midnight (00:00:00)
 * to prevent UTC-to-local off-by-one-day shifts.
 */
export function parseLocalDate(dateStr: string): Date | null {
  if (!dateStr || typeof dateStr !== 'string') return null;
  const trimmed = dateStr.trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (!match) {
    const fallback = new Date(trimmed);
    if (isNaN(fallback.getTime())) return null;
    return new Date(fallback.getFullYear(), fallback.getMonth(), fallback.getDate());
  }
  const year = Number(match[1]);
  const month = Number(match[2]) - 1;
  const day = Number(match[3]);
  const date = new Date(year, month, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month ||
    date.getDate() !== day
  ) {
    return null;
  }
  return date;
}

/**
 * Returns today's date at local midnight (00:00:00).
 */
export function getLocalToday(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/**
 * Formats a YYYY-MM-DD string into a readable date (e.g. "24 Nov 2026")
 */
export function formatLocalDate(dateStr: string): string {
  const parsed = parseLocalDate(dateStr);
  if (!parsed) return 'No deadline set';
  return parsed.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Formats an ISO timestamp for audit logs and metadata
 */
export function formatTimestamp(isoStr: string): string {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Classifies a competition's deadline accurately using the user's local date.
 * - Completed and Submitted competitions are never flagged as Overdue active work.
 * - Due soon is defined as 1 to 7 days from today.
 */
export function classifyDeadline(
  competition: Pick<Competition, 'deadline' | 'status' | 'archived'>
): DeadlineInfo {
  const parsed = parseLocalDate(competition.deadline);
  const isFinished =
    competition.status === 'COMPLETED' ||
    competition.status === 'SUBMITTED' ||
    competition.archived;

  if (!parsed) {
    return {
      category: 'NO_DEADLINE',
      label: 'No deadline set',
      countdownText: 'Unscheduled',
      daysDiff: null,
      formattedDate: 'No deadline set',
      isHistorical: isFinished,
      isUrgentWarning: false,
    };
  }

  const today = getLocalToday();
  const msPerDay = 1000 * 60 * 60 * 24;
  const daysDiff = Math.round((parsed.getTime() - today.getTime()) / msPerDay);
  const formattedDate = formatLocalDate(competition.deadline);

  // Completed or Submitted competitions do not trigger overdue or urgent unfinished warnings
  if (isFinished) {
    let historicalText = 'Submitted / Closed';
    if (daysDiff === 0) {
      historicalText = 'Target date today';
    } else if (daysDiff > 0) {
      historicalText = `${daysDiff}d until target date`;
    } else {
      historicalText = `Closed ${Math.abs(daysDiff)}d ago`;
    }

    return {
      category: daysDiff > 0 ? 'UPCOMING' : 'NO_DEADLINE',
      label: competition.status === 'COMPLETED' ? 'Mission Completed' : 'Submission Logged',
      countdownText: historicalText,
      daysDiff,
      formattedDate,
      isHistorical: true,
      isUrgentWarning: false,
    };
  }

  if (daysDiff < 0) {
    const overdueDays = Math.abs(daysDiff);
    return {
      category: 'OVERDUE',
      label: 'Overdue',
      countdownText:
        overdueDays === 1 ? 'Overdue by 1 day' : `Overdue by ${overdueDays} days`,
      daysDiff,
      formattedDate,
      isHistorical: false,
      isUrgentWarning: true,
    };
  }

  if (daysDiff === 0) {
    return {
      category: 'DUE_TODAY',
      label: 'Due today',
      countdownText: 'Due today (23:59 local)',
      daysDiff: 0,
      formattedDate,
      isHistorical: false,
      isUrgentWarning: true,
    };
  }

  if (daysDiff <= 7) {
    return {
      category: 'DUE_SOON',
      label: 'Due soon',
      countdownText: daysDiff === 1 ? 'Due in 1 day' : `Due in ${daysDiff} days`,
      daysDiff,
      formattedDate,
      isHistorical: false,
      isUrgentWarning: true,
    };
  }

  return {
    category: 'UPCOMING',
    label: 'Upcoming',
    countdownText: `Due in ${daysDiff} days`,
    daysDiff,
    formattedDate,
    isHistorical: false,
    isUrgentWarning: false,
  };
}

/**
 * Validates whether a string is a safe, well-formed HTTP/HTTPS URL.
 */
export function isValidHttpUrl(value: string): boolean {
  if (!value || !value.trim()) return false;
  try {
    const url = new URL(value.trim());
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Generates a Google Calendar Event Template link for a competition with a valid deadline.
 * Uses all-day YYYYMMDD/YYYYMMDD(+1 day) formatting so date-only deadlines never shift across timezones.
 */
export function generateGoogleCalendarUrl(competition: Competition): string | null {
  const parsed = parseLocalDate(competition.deadline);
  if (!parsed) return null;

  const nextDay = new Date(
    parsed.getFullYear(),
    parsed.getMonth(),
    parsed.getDate() + 1
  );

  const toGCalDate = (d: Date) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}${mm}${dd}`;
  };

  const datesParam = `${toGCalDate(parsed)}/${toGCalDate(nextDay)}`;
  const title = `[KRYPTØNIX] ${competition.name} — Deadline`;

  const descriptionLines: string[] = [
    `KRYPTØNIX Star Command Mission Reminder`,
    `Mission ID: ${competition.id}`,
    `Status: ${competition.status}`,
  ];

  if (competition.organiser) {
    descriptionLines.push(`Organiser: ${competition.organiser}`);
  }
  if (competition.competitionUrl && isValidHttpUrl(competition.competitionUrl)) {
    descriptionLines.push(`Competition Link: ${competition.competitionUrl}`);
  }
  if (competition.progressDocUrl && isValidHttpUrl(competition.progressDocUrl)) {
    descriptionLines.push(`Progress Document: ${competition.progressDocUrl}`);
  }
  if (competition.notes) {
    descriptionLines.push(`\nMission Notes:\n${competition.notes}`);
  }

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: title,
    dates: datesParam,
    details: descriptionLines.join('\n'),
  });

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}
