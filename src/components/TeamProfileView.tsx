import React, { useState } from 'react';
import {
  Users,
  Edit3,
  ExternalLink,
  Save,
  Database,
  Copy,
  Check,
  ShieldCheck,
  AlertCircle,
  KeyRound,
} from 'lucide-react';
import { OFFICIAL_TEAM_MEMBERS, TEAM_NAME } from '../config/teamConfig';
import { StorageConfig, TeamMember } from '../types/mission';
import {
  changeServerPin,
  GOOGLE_APPS_SCRIPT_TEMPLATE,
} from '../services/storageService';
import { isValidHttpUrl } from '../utils/deadline';
import { StarCommandInsignia } from './StarCommandInsignia';

interface TeamProfileViewProps {
  teamMembers: TeamMember[];
  storageConfig: StorageConfig;
  onUpdateTeamMembers: (members: TeamMember[]) => Promise<void>;
  onUpdateStorageConfig: (config: StorageConfig) => void;
}

export const TeamProfileView: React.FC<TeamProfileViewProps> = ({
  teamMembers,
  storageConfig,
  onUpdateTeamMembers,
  onUpdateStorageConfig,
}) => {
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null);
  const [draftRole, setDraftRole] = useState('');
  const [draftFocus, setDraftFocus] = useState('');
  const [draftUrl, setDraftUrl] = useState('');
  const [memberError, setMemberError] = useState<string | null>(null);
  const [isSavingMember, setIsSavingMember] = useState(false);

  // Storage & Google Apps Script panel state
  const [providerDraft, setProviderDraft] = useState<
    'express_api' | 'apps_script'
  >(storageConfig.provider);
  const [urlDraft, setUrlDraft] = useState(storageConfig.appsScriptUrl);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [configSavedNotice, setConfigSavedNotice] = useState(false);
  const [copiedScript, setCopiedScript] = useState(false);
  const [showScriptModal, setShowScriptModal] = useState(false);

  // Server PIN Rotation State
  const [currentPin, setCurrentPin] = useState('');
  const [newPin, setNewPin] = useState('');
  const [confirmNewPin, setConfirmNewPin] = useState('');
  const [pinMsg, setPinMsg] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);
  const [isChangingPin, setIsChangingPin] = useState(false);

  const startEditMember = (member: TeamMember) => {
    setEditingMemberId(member.id);
    setDraftRole(member.role);
    setDraftFocus(member.focusArea);
    setDraftUrl(member.profileUrl);
    setMemberError(null);
  };

  const handleSaveMember = async (e: React.FormEvent, memberId: string) => {
    e.preventDefault();
    if (isSavingMember) return;
    setMemberError(null);

    if (draftUrl.trim() && !isValidHttpUrl(draftUrl.trim())) {
      setMemberError(
        'Optional profile link must be a valid URL starting with https:// or http://'
      );
      return;
    }

    setIsSavingMember(true);
    try {
      const updated = teamMembers.map((m) => {
        if (m.id !== memberId) return m;
        return {
          ...m,
          role: draftRole.trim(),
          focusArea: draftFocus.trim(),
          profileUrl: draftUrl.trim(),
        };
      });
      await onUpdateTeamMembers(updated);
      setEditingMemberId(null);
    } catch (err) {
      setMemberError(
        err instanceof Error ? err.message : 'Failed to save member details.'
      );
    } finally {
      setIsSavingMember(false);
    }
  };

  const handleSaveStorage = (e: React.FormEvent) => {
    e.preventDefault();
    setUrlError(null);
    setConfigSavedNotice(false);

    if (providerDraft === 'apps_script' && !isValidHttpUrl(urlDraft.trim())) {
      setUrlError(
        'Enter your deployed Google Apps Script Web App URL (https://script.google.com/macros/s/.../exec).'
      );
      return;
    }

    onUpdateStorageConfig({
      provider: providerDraft,
      appsScriptUrl: urlDraft.trim(),
      lastSyncedAt: new Date().toISOString(),
    });
    setConfigSavedNotice(true);
    setTimeout(() => setConfigSavedNotice(false), 3500);
  };

  const handlePinRotation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isChangingPin) return;
    setPinMsg(null);

    if (!currentPin.trim()) {
      setPinMsg({ type: 'error', text: 'Enter the current Team PIN.' });
      return;
    }
    if (newPin.trim().length < 4) {
      setPinMsg({
        type: 'error',
        text: 'New Team PIN must be at least 4 characters.',
      });
      return;
    }
    if (newPin.trim() !== confirmNewPin.trim()) {
      setPinMsg({
        type: 'error',
        text: 'New PIN and confirmation do not match.',
      });
      return;
    }

    setIsChangingPin(true);
    try {
      await changeServerPin(currentPin, newPin, storageConfig);
      setCurrentPin('');
      setNewPin('');
      setConfirmNewPin('');
      setPinMsg({
        type: 'success',
        text: 'Server Team PIN hash updated.',
      });
    } catch (err) {
      setPinMsg({
        type: 'error',
        text:
          err instanceof Error ? err.message : 'Failed to update Team PIN.',
      });
    } finally {
      setIsChangingPin(false);
    }
  };

  const handleCopyAppsScript = async () => {
    try {
      await navigator.clipboard.writeText(GOOGLE_APPS_SCRIPT_TEMPLATE);
      setCopiedScript(true);
      setTimeout(() => setCopiedScript(false), 2500);
    } catch {
      // ignore clipboard error
    }
  };

  return (
    <div className="space-y-8">
      {/* Official Team Identity Header */}
      <section className="bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-start sm:items-center gap-4">
          <StarCommandInsignia size="lg" />
          <div>
            <div className="font-mono text-xs text-[#A6FF4D] tracking-widest font-semibold">
              OFFICIAL FOUR-MEMBER COMPETITION CREW
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-wide text-[#F3F5FC]">
              {TEAM_NAME}
            </h1>
            <p className="font-mono text-xs text-[#57DDF5] mt-1">
              {OFFICIAL_TEAM_MEMBERS.map((m) => m.name).join(' · ')}
            </p>
          </div>
        </div>

        <div className="bg-[#101629] border border-[#929DB7]/20 rounded-md px-4 py-3 text-xs font-mono text-[#929DB7] shrink-0">
          <div>CREW ROSTER: 4 ACTIVE MEMBERS</div>
          <div className="text-[#A6FF4D] mt-0.5">
            ROLES & LINKS SYNCED WITH SERVER STORE
          </div>
        </div>
      </section>

      {/* Four Official Team-Member Profile Panels */}
      <section aria-label="Official KRYPTØNIX team member panels">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-bold tracking-wide text-[#F3F5FC] flex items-center gap-2">
            <Users className="w-5 h-5 text-[#9B7CFF]" />
            <span>{TEAM_NAME} Command Roster</span>
          </h2>
          <span className="text-xs text-[#929DB7]">
            Configure member roles and optional profile links
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {teamMembers.map((member) => {
            const isEditing = editingMemberId === member.id;
            const hasValidLink = isValidHttpUrl(member.profileUrl);

            return (
              <div
                key={member.id}
                className="bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-5 flex flex-col justify-between space-y-4 transition-colors hover:border-[#9B7CFF]/45"
              >
                {isEditing ? (
                  <form
                    onSubmit={(e) => handleSaveMember(e, member.id)}
                    className="space-y-3 text-xs"
                  >
                    <div className="flex items-center justify-between font-mono">
                      <span className="text-[#57DDF5] font-semibold">
                        {member.slotLabel} · {member.id}
                      </span>
                      <span className="text-[#A6FF4D]">CONFIGURE ROLE</span>
                    </div>

                    <div className="font-display text-lg font-bold text-[#F3F5FC]">
                      {member.name}
                    </div>

                    {memberError && (
                      <div className="p-2.5 rounded bg-[#FF5C70]/10 border border-[#FF5C70]/40 text-[#FF5C70] flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                        <span>{memberError}</span>
                      </div>
                    )}

                    <div>
                      <label
                        htmlFor={`role-${member.id}`}
                        className="block text-[#929DB7] mb-1"
                      >
                        Role / Assignment (Optional)
                      </label>
                      <input
                        id={`role-${member.id}`}
                        type="text"
                        value={draftRole}
                        onChange={(e) => setDraftRole(e.target.value)}
                        placeholder="Enter team role or responsibility"
                        className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded text-[#F3F5FC]"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor={`focus-${member.id}`}
                        className="block text-[#929DB7] mb-1"
                      >
                        Specialization / Domain (Optional)
                      </label>
                      <input
                        id={`focus-${member.id}`}
                        type="text"
                        value={draftFocus}
                        onChange={(e) => setDraftFocus(e.target.value)}
                        placeholder="Enter technical focus area"
                        className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded text-[#F3F5FC]"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor={`url-${member.id}`}
                        className="block text-[#929DB7] mb-1"
                      >
                        Optional Profile URL (GitHub, LinkedIn, Portfolio)
                      </label>
                      <input
                        id={`url-${member.id}`}
                        type="url"
                        value={draftUrl}
                        onChange={(e) => setDraftUrl(e.target.value)}
                        placeholder="https://github.com/..."
                        className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded font-mono text-[#F3F5FC]"
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setEditingMemberId(null)}
                        disabled={isSavingMember}
                        className="px-3 py-1.5 rounded bg-[#101629] text-[#929DB7] hover:text-[#F3F5FC] cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isSavingMember}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded bg-[#A6FF4D] text-[#080B16] font-display font-bold cursor-pointer disabled:opacity-50"
                      >
                        <Save className="w-3.5 h-3.5" />
                        <span>
                          {isSavingMember ? 'Saving...' : 'Save Configuration'}
                        </span>
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2 text-xs font-mono">
                        <span className="text-[#57DDF5] font-semibold">
                          {member.slotLabel}
                        </span>
                        <span className="text-[#929DB7]">{member.id}</span>
                      </div>

                      <h3 className="font-display text-xl font-bold tracking-wide text-[#F3F5FC]">
                        {member.name}
                      </h3>

                      <div className="text-sm font-medium text-[#9B7CFF]">
                        {member.role ? (
                          member.role
                        ) : (
                          <span className="text-[#929DB7] text-xs font-normal">
                            Role not assigned yet — click Configure Role to set
                          </span>
                        )}
                      </div>

                      {member.focusArea && (
                        <p className="text-xs text-[#929DB7] pt-0.5">
                          Domain: {member.focusArea}
                        </p>
                      )}
                    </div>

                    <div className="pt-3 border-t border-[#929DB7]/15 flex items-center justify-between gap-2 text-xs">
                      {hasValidLink ? (
                        <a
                          href={member.profileUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[#A6FF4D] hover:underline font-medium"
                        >
                          <span>Open Member Profile</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : (
                        <span className="text-[#929DB7]">
                          No external profile link set
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => startEditMember(member)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/25 text-[#F3F5FC] font-medium cursor-pointer"
                      >
                        <Edit3 className="w-3.5 h-3.5 text-[#57DDF5]" />
                        <span>Configure Role</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Server-Side PIN Rotation & Backend Data Store Configuration */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Rotate Server Team PIN */}
        <section className="lg:col-span-5 bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-6 space-y-4">
          <div className="pb-3 border-b border-[#929DB7]/20">
            <h2 className="font-display text-base font-bold tracking-wide text-[#F3F5FC] flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-[#A6FF4D]" />
              <span>Rotate Shared Team PIN</span>
            </h2>
            <p className="text-xs text-[#929DB7] mt-0.5">
              Updates the salted PIN hash stored on the backend server.
            </p>
          </div>

          <form onSubmit={handlePinRotation} className="space-y-3 text-xs">
            <div>
              <label
                htmlFor="current-pin-input"
                className="block text-[#929DB7] mb-1"
              >
                Current Team PIN
              </label>
              <input
                id="current-pin-input"
                type="password"
                value={currentPin}
                onChange={(e) => setCurrentPin(e.target.value)}
                className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded font-mono text-[#F3F5FC]"
              />
            </div>

            <div>
              <label
                htmlFor="new-pin-input"
                className="block text-[#929DB7] mb-1"
              >
                New Team PIN (min 4 chars)
              </label>
              <input
                id="new-pin-input"
                type="password"
                value={newPin}
                onChange={(e) => setNewPin(e.target.value)}
                className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded font-mono text-[#F3F5FC]"
              />
            </div>

            <div>
              <label
                htmlFor="confirm-new-pin-input"
                className="block text-[#929DB7] mb-1"
              >
                Confirm New Team PIN
              </label>
              <input
                id="confirm-new-pin-input"
                type="password"
                value={confirmNewPin}
                onChange={(e) => setConfirmNewPin(e.target.value)}
                className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded font-mono text-[#F3F5FC]"
              />
            </div>

            {pinMsg && (
              <div
                className={`p-2.5 rounded border ${
                  pinMsg.type === 'success'
                    ? 'bg-[#A6FF4D]/10 border-[#A6FF4D]/40 text-[#A6FF4D]'
                    : 'bg-[#FF5C70]/10 border-[#FF5C70]/40 text-[#FF5C70]'
                }`}
              >
                {pinMsg.text}
              </div>
            )}

            <button
              type="submit"
              disabled={isChangingPin}
              className="w-full py-2 px-4 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#A6FF4D]/40 text-[#A6FF4D] font-display font-bold cursor-pointer disabled:opacity-50"
            >
              {isChangingPin ? 'Updating Server Hash...' : 'Update Team PIN'}
            </button>
          </form>
        </section>

        {/* Production Backend & Google Sheets Apps Script Configuration */}
        <section className="lg:col-span-7 bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#929DB7]/20">
            <div>
              <h2 className="font-display text-base font-bold tracking-wide text-[#F3F5FC] flex items-center gap-2">
                <Database className="w-4 h-4 text-[#57DDF5]" />
                <span>Production Data Store & Google Sheets Uplink</span>
              </h2>
              <p className="text-xs text-[#929DB7] mt-0.5">
                Select between the Express Backend API Store or Google Sheets via Google Apps Script.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowScriptModal((prev) => !prev)}
              className="px-3 py-1.5 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#9B7CFF]/40 text-xs font-medium text-[#9B7CFF] cursor-pointer whitespace-nowrap self-start sm:self-auto"
            >
              {showScriptModal ? 'Hide Code.gs' : 'View Apps Script (Code.gs)'}
            </button>
          </div>

          <form onSubmit={handleSaveStorage} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setProviderDraft('express_api')}
                className={`p-3.5 rounded-md border text-left transition-colors cursor-pointer ${
                  providerDraft === 'express_api'
                    ? 'bg-[#57DDF5]/15 border-[#57DDF5] text-[#F3F5FC]'
                    : 'bg-[#101629] border-[#929DB7]/20 text-[#929DB7]'
                }`}
              >
                <div className="font-display font-bold text-sm text-[#F3F5FC]">
                  Star Command Express API
                </div>
                <p className="text-xs text-[#929DB7] mt-1">
                  Server-side scrypt PIN verification, HMAC session tokens, and atomic server persistence (`/api/*`).
                </p>
              </button>

              <button
                type="button"
                onClick={() => setProviderDraft('apps_script')}
                className={`p-3.5 rounded-md border text-left transition-colors cursor-pointer ${
                  providerDraft === 'apps_script'
                    ? 'bg-[#A6FF4D]/15 border-[#A6FF4D] text-[#F3F5FC]'
                    : 'bg-[#101629] border-[#929DB7]/20 text-[#929DB7]'
                }`}
              >
                <div className="font-display font-bold text-sm text-[#F3F5FC]">
                  Google Sheets + Apps Script
                </div>
                <p className="text-xs text-[#929DB7] mt-1">
                  Serverless Google Sheets persistence with SHA-256 PIN hashing in ScriptProperties and LockService concurrency.
                </p>
              </button>
            </div>

            {providerDraft === 'apps_script' && (
              <div className="space-y-1.5">
                <label
                  htmlFor="apps-script-endpoint"
                  className="block font-semibold text-[#F3F5FC]"
                >
                  Deployed Google Apps Script Web App URL (/exec)
                </label>
                <input
                  id="apps-script-endpoint"
                  type="url"
                  value={urlDraft}
                  onChange={(e) => setUrlDraft(e.target.value)}
                  placeholder="https://script.google.com/macros/s/AKfycb.../exec"
                  className="w-full px-3.5 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded-md font-mono text-xs text-[#F3F5FC]"
                />
                {urlError && <p className="text-[#FF5C70]">{urlError}</p>}
              </div>
            )}

            <div className="flex items-center justify-between gap-4 pt-1">
              <div className="flex items-start gap-2 text-[#929DB7]">
                <ShieldCheck className="w-4 h-4 text-[#A6FF4D] shrink-0 mt-0.5" />
                <span>
                  All write operations validate fields server-side and require an active session token.
                </span>
              </div>

              <button
                type="submit"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-[#A6FF4D] hover:bg-[#b8ff6e] text-[#080B16] font-display font-bold text-xs whitespace-nowrap shrink-0 cursor-pointer"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save Provider</span>
              </button>
            </div>

            {configSavedNotice && (
              <div className="p-2.5 rounded bg-[#A6FF4D]/15 border border-[#A6FF4D]/40 text-[#A6FF4D] font-medium">
                Production data store configuration saved.
              </div>
            )}
          </form>

          {showScriptModal && (
            <div className="pt-3 border-t border-[#929DB7]/20 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-semibold text-[#57DDF5]">
                  Production Google Apps Script (`Code.gs`)
                </span>
                <button
                  type="button"
                  onClick={handleCopyAppsScript}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/30 text-xs text-[#F3F5FC] cursor-pointer"
                >
                  {copiedScript ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-[#A6FF4D]" />
                      <span className="text-[#A6FF4D]">Copied Code.gs</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy Code.gs</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="p-3.5 rounded bg-[#080B16] border border-[#929DB7]/25 font-mono text-[11px] text-[#F3F5FC] overflow-x-auto max-h-[280px]">
                {GOOGLE_APPS_SCRIPT_TEMPLATE}
              </pre>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
