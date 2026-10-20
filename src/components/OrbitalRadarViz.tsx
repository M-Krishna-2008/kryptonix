import React, { useState } from 'react';
import { Competition } from '../types/mission';
import { classifyDeadline } from '../utils/deadline';

interface OrbitalRadarVizProps {
  competitions: Competition[];
  onSelectCompetition: (id: string) => void;
}

/**
 * Circular SVG mission-status radar & orbital distribution visualization.
 * Plots real active competitions across three concentric rings:
 * - Inner Ring: Urgent / Due Soon / Overdue Active Missions
 * - Middle Ring: Ongoing Scheduled Missions
 * - Outer Ring: Submitted & Completed Active Missions
 */
export const OrbitalRadarViz: React.FC<OrbitalRadarVizProps> = ({
  competitions,
  onSelectCompetition,
}) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const activeList = competitions.filter((c) => !c.archived);
  const totalActive = activeList.length;
  const ongoingCount = activeList.filter((c) => c.status === 'ONGOING').length;
  const submittedCount = activeList.filter((c) => c.status === 'SUBMITTED').length;
  const completedCount = activeList.filter((c) => c.status === 'COMPLETED').length;

  // Compute deterministic polar coordinates for each real active competition
  const plottedBlips = activeList.map((comp, index) => {
    const dInfo = classifyDeadline(comp);
    let radius = 78; // middle ring default
    let color = '#57DDF5'; // cyan for ongoing

    if (comp.status === 'COMPLETED') {
      radius = 104;
      color = '#A6FF4D';
    } else if (comp.status === 'SUBMITTED') {
      radius = 96;
      color = '#9B7CFF';
    } else if (dInfo.category === 'OVERDUE') {
      radius = 48;
      color = '#FF5C70';
    } else if (dInfo.category === 'DUE_TODAY' || dInfo.category === 'DUE_SOON') {
      radius = 56;
      color = '#FFBE55';
    }

    // Spread angles evenly with a deterministic golden-angle offset
    const angleDeg = (index * 137.5 + 35) % 360;
    const angleRad = (angleDeg * Math.PI) / 180;
    const cx = 130 + radius * Math.cos(angleRad);
    const cy = 130 + radius * Math.sin(angleRad);

    return {
      comp,
      dInfo,
      cx,
      cy,
      color,
    };
  });

  // Ring segment stroke-dasharray math (circumference = 2 * PI * 116 ≈ 728.8)
  const ringRadius = 116;
  const circumference = 2 * Math.PI * ringRadius;
  const ongoingFrac = totalActive > 0 ? ongoingCount / totalActive : 0;
  const submittedFrac = totalActive > 0 ? submittedCount / totalActive : 0;
  const completedFrac = totalActive > 0 ? completedCount / totalActive : 0;

  const ongoingLen = ongoingFrac * circumference;
  const submittedLen = submittedFrac * circumference;
  const completedLen = completedFrac * circumference;

  const hoveredBlip = plottedBlips.find((b) => b.comp.id === hoveredId);

  return (
    <div className="bg-[#151D32] border border-[#929DB7]/20 rounded-lg p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between gap-4 mb-3">
        <div>
          <h2 className="font-display text-base font-semibold tracking-wide text-[#F3F5FC]">
            Orbital Mission Radar
          </h2>
          <p className="text-xs text-[#929DB7]">
            Live status distribution · Click any vector node to inspect dossier
          </p>
        </div>
        <span className="font-mono text-xs text-[#A6FF4D] tabular-nums whitespace-nowrap shrink-0">
          {totalActive} ACTIVE
        </span>
      </div>

      <div className="relative flex items-center justify-center my-1">
        <svg
          viewBox="0 0 260 260"
          className="w-full max-w-[240px] h-auto select-none"
          role="img"
          aria-label={`Mission status radar showing ${ongoingCount} ongoing, ${submittedCount} submitted, and ${completedCount} completed active competitions.`}
        >
          <defs>
            <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#9B7CFF" stopOpacity="0.16" />
              <stop offset="65%" stopColor="#57DDF5" stopOpacity="0.06" />
              <stop offset="100%" stopColor="#080B16" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="sweepGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#A6FF4D" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#A6FF4D" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Radar background glow */}
          <circle cx="130" cy="130" r="118" fill="url(#radarGlow)" />

          {/* Outer status distribution gauge track */}
          <circle
            cx="130"
            cy="130"
            r={ringRadius}
            fill="none"
            stroke="#101629"
            strokeWidth="6"
          />

          {/* Proportional status segments on outer ring */}
          {totalActive > 0 && (
            <g transform="rotate(-90 130 130)">
              {/* Ongoing segment (Cyan) */}
              <circle
                cx="130"
                cy="130"
                r={ringRadius}
                fill="none"
                stroke="#57DDF5"
                strokeWidth="6"
                strokeDasharray={`${ongoingLen} ${circumference}`}
                strokeDashoffset={0}
              />
              {/* Submitted segment (Electric Violet) */}
              <circle
                cx="130"
                cy="130"
                r={ringRadius}
                fill="none"
                stroke="#9B7CFF"
                strokeWidth="6"
                strokeDasharray={`${submittedLen} ${circumference}`}
                strokeDashoffset={-ongoingLen}
              />
              {/* Completed segment (Command Green) */}
              <circle
                cx="130"
                cy="130"
                r={ringRadius}
                fill="none"
                stroke="#A6FF4D"
                strokeWidth="6"
                strokeDasharray={`${completedLen} ${circumference}`}
                strokeDashoffset={-(ongoingLen + submittedLen)}
              />
            </g>
          )}

          {/* Concentric range rings */}
          <circle
            cx="130"
            cy="130"
            r="96"
            fill="none"
            stroke="#929DB7"
            strokeOpacity="0.2"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
          <circle
            cx="130"
            cy="130"
            r="74"
            fill="none"
            stroke="#929DB7"
            strokeOpacity="0.22"
            strokeWidth="1"
          />
          <circle
            cx="130"
            cy="130"
            r="48"
            fill="none"
            stroke="#FFBE55"
            strokeOpacity="0.25"
            strokeWidth="1"
            strokeDasharray="2 4"
          />

          {/* Crosshair axes */}
          <line
            x1="130"
            y1="18"
            x2="130"
            y2="242"
            stroke="#929DB7"
            strokeOpacity="0.16"
            strokeWidth="1"
          />
          <line
            x1="18"
            y1="130"
            x2="242"
            y2="130"
            stroke="#929DB7"
            strokeOpacity="0.16"
            strokeWidth="1"
          />

          {/* Rotating radar sweep sector */}
          <g className="animate-radar-sweep" style={{ transformOrigin: '130px 130px' }}>
            <path
              d="M130,130 L130,20 A110,110 0 0,1 208,52 Z"
              fill="url(#sweepGrad)"
            />
            <line
              x1="130"
              y1="130"
              x2="130"
              y2="20"
              stroke="#A6FF4D"
              strokeOpacity="0.55"
              strokeWidth="1.2"
            />
          </g>

          {/* Center spacecraft hub */}
          <circle
            cx="130"
            cy="130"
            r="22"
            fill="#080B16"
            stroke="#9B7CFF"
            strokeOpacity="0.5"
            strokeWidth="1.2"
          />
          <text
            x="130"
            y="128"
            textAnchor="middle"
            className="font-mono text-[13px] font-bold fill-[#F3F5FC]"
          >
            {totalActive}
          </text>
          <text
            x="130"
            y="140"
            textAnchor="middle"
            className="font-mono text-[7px] fill-[#929DB7]"
          >
            MISSIONS
          </text>

          {/* Plotted real competition vector nodes */}
          {plottedBlips.map(({ comp, cx, cy, color }) => {
            const isHovered = hoveredId === comp.id;
            return (
              <g
                key={comp.id}
                className="cursor-pointer"
                onClick={() => onSelectCompetition(comp.id)}
                onMouseEnter={() => setHoveredId(comp.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 9 : 6}
                  fill={color}
                  fillOpacity="0.22"
                />
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 4.5 : 3.5}
                  fill={color}
                  stroke="#080B16"
                  strokeWidth="1"
                />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Interactive node telemetry readout bar */}
      <div className="min-h-[38px] px-3 py-2 rounded bg-[#101629] border border-[#929DB7]/15 flex items-center justify-between gap-2 text-xs">
        {hoveredBlip ? (
          <>
            <span className="font-medium text-[#F3F5FC] truncate">
              {hoveredBlip.comp.id} · {hoveredBlip.comp.name}
            </span>
            <span className="font-mono text-[11px] text-[#57DDF5] tabular-nums shrink-0">
              {hoveredBlip.dInfo.countdownText}
            </span>
          </>
        ) : (
          <>
            <span className="text-[#929DB7] truncate">
              Hover or select a radar node to inspect mission
            </span>
            <span className="font-mono text-[11px] text-[#929DB7] tabular-nums shrink-0">
              INNER RING: URGENT
            </span>
          </>
        )}
      </div>

      {/* Accessible Legend */}
      <div className="mt-3 pt-3 border-t border-[#929DB7]/15 grid grid-cols-3 gap-2 text-xs">
        <div className="flex flex-col">
          <span className="text-[#929DB7] text-[11px]">Ongoing</span>
          <span className="font-mono font-semibold text-[#57DDF5] tabular-nums">
            ◆ {ongoingCount}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[#929DB7] text-[11px]">Submitted</span>
          <span className="font-mono font-semibold text-[#9B7CFF] tabular-nums">
            ▲ {submittedCount}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[#929DB7] text-[11px]">Completed</span>
          <span className="font-mono font-semibold text-[#A6FF4D] tabular-nums">
            ✓ {completedCount}
          </span>
        </div>
      </div>
    </div>
  );
};
