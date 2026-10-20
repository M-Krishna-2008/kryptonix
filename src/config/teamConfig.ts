import { TeamMember } from '../types/mission';

export const TEAM_NAME = 'KRYPTØNIX';

export const OFFICIAL_TEAM_MEMBERS: readonly Omit<
  TeamMember,
  'role' | 'focusArea' | 'profileUrl'
>[] = [
  {
    id: 'KRYP-M01',
    slotLabel: 'OPERATOR 01',
    name: 'M KRISHNA',
  },
  {
    id: 'KRYP-M02',
    slotLabel: 'OPERATOR 02',
    name: 'V JEYSHREE',
  },
  {
    id: 'KRYP-M03',
    slotLabel: 'OPERATOR 03',
    name: 'SUBHA SHREE R',
  },
  {
    id: 'KRYP-M04',
    slotLabel: 'OPERATOR 04',
    name: 'LAKSHMANAN G',
  },
] as const;

export function getDefaultTeamRoster(): TeamMember[] {
  return OFFICIAL_TEAM_MEMBERS.map((member) => ({
    id: member.id,
    slotLabel: member.slotLabel,
    name: member.name,
    role: '',
    focusArea: '',
    profileUrl: '',
  }));
}

/**
 * Ensures the team roster always contains the 4 official KRYPTØNIX members
 * with their exact uppercase names while preserving any saved editable roles/links.
 */
export function normalizeTeamRoster(stored?: Partial<TeamMember>[]): TeamMember[] {
  const byId = new Map<string, Partial<TeamMember>>();
  const byName = new Map<string, Partial<TeamMember>>();

  if (Array.isArray(stored)) {
    stored.forEach((item) => {
      if (item && typeof item.id === 'string') byId.set(item.id, item);
      if (item && typeof item.name === 'string') {
        byName.set(item.name.trim().toUpperCase(), item);
      }
    });
  }

  return OFFICIAL_TEAM_MEMBERS.map((official) => {
    const match =
      byId.get(official.id) || byName.get(official.name);
    return {
      id: official.id,
      slotLabel: official.slotLabel,
      name: official.name, // Enforce exact official spelling
      role: typeof match?.role === 'string' ? match.role.trim() : '',
      focusArea:
        typeof match?.focusArea === 'string' ? match.focusArea.trim() : '',
      profileUrl:
        typeof match?.profileUrl === 'string' ? match.profileUrl.trim() : '',
    };
  });
}
