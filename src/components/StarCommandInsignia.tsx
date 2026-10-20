import React from 'react';
import { Competition, MissionStatus } from '../types/mission';
import { classifyDeadline } from '../utils/deadline';

interface InsigniaProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * Custom original Star Command geometric wing & delta star insignia for KRYPTØNIX.
 */
export const StarCommandInsignia: React.FC<InsigniaProps> = ({
  size = 'md',
  className = '',
}) => {
  const dimensions =
    size === 'sm' ? 'w-7 h-7' : size === 'lg' ? 'w-12 h-12' : 'w-9 h-9';

  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`${dimensions} shrink-0 ${className}`}
      aria-hidden="true"
    >
      {/* Outer technical octagonal ring */}
      <polygon
        points="32,3 53,11 61,32 53,53 32,61 11,53 3,32 11,11"
        stroke="#9B7CFF"
        strokeWidth="1.5"
        strokeOpacity="0.45"
        fill="#101629"
      />
      {/* Orbital arc */}
      <path
        d="M10 36 C 18 20, 46 20, 54 36"
        stroke="#57DDF5"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      {/* Star Command swept wings */}
      <path
        d="M8 38 L25 27 L32 32 L39 27 L56 38 L42 36 L32 42 L22 36 Z"
        fill="#9B7CFF"
        fillOpacity="0.28"
        stroke="#9B7CFF"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Central spacecraft delta spearhead */}
      <path
        d="M32 9 L41 46 L32 39 L23 46 Z"
        fill="#F3F5FC"
        stroke="#A6FF4D"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Command green core beacon */}
      <circle cx="32" cy="28" r="3" fill="#A6FF4D" />
    </svg>
  );
};

/**
 * Accessible text-first status readout with distinct glyph and tone.
 * Never communicates status by color alone.
 */
export const StatusReadout: React.FC<{
  status: MissionStatus;
  compact?: boolean;
}> = ({ status, compact = false }) => {
  if (status === 'ONGOING') {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs font-medium text-[#57DDF5] whitespace-nowrap shrink-0">
        <span aria-hidden="true" className="text-[10px]">
          ◆
        </span>
        <span>{compact ? 'ONGOING' : 'ONGOING MISSION'}</span>
      </span>
    );
  }
  if (status === 'SUBMITTED') {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs font-medium text-[#9B7CFF] whitespace-nowrap shrink-0">
        <span aria-hidden="true" className="text-[10px]">
          ▲
        </span>
        <span>{compact ? 'SUBMITTED' : 'SUBMITTED'}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs font-medium text-[#A6FF4D] whitespace-nowrap shrink-0">
      <span aria-hidden="true" className="text-[10px]">
        ✓
      </span>
      <span>{compact ? 'COMPLETED' : 'COMPLETED'}</span>
    </span>
  );
};

/**
 * Accessible deadline classification & countdown readout.
 */
export const DeadlineReadout: React.FC<{
  competition: Pick<Competition, 'deadline' | 'status' | 'archived'>;
}> = ({ competition }) => {
  const info = classifyDeadline(competition);

  let toneClass = 'text-[#929DB7]';
  let prefixGlyph = '·';

  if (!info.isHistorical) {
    if (info.category === 'OVERDUE') {
      toneClass = 'text-[#FF5C70] font-semibold';
      prefixGlyph = '✖';
    } else if (info.category === 'DUE_TODAY' || info.category === 'DUE_SOON') {
      toneClass = 'text-[#FFBE55] font-medium';
      prefixGlyph = '▲';
    } else if (info.category === 'UPCOMING') {
      toneClass = 'text-[#57DDF5]';
      prefixGlyph = '●';
    }
  }

  return (
    <div className="flex flex-col">
      <span className="font-mono text-xs text-[#F3F5FC] tabular-nums whitespace-nowrap">
        {info.formattedDate}
      </span>
      <span
        className={`font-mono text-[11px] tabular-nums whitespace-nowrap ${toneClass}`}
      >
        <span aria-hidden="true" className="mr-1">
          {prefixGlyph}
        </span>
        {info.countdownText}
      </span>
    </div>
  );
};
