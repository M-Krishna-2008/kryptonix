import React, { useCallback, useEffect, useState } from 'react';
import {
  Eye,
  EyeOff,
  Lock,
  ShieldCheck,
  Database,
  ArrowRight,
  Settings,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import {
  DEFAULT_GOOGLE_APPS_SCRIPT_URL,
  OFFICIAL_TEAM_MEMBERS,
  TEAM_NAME,
} from '../config/teamConfig';
import { StorageConfig } from '../types/mission';
import {
  checkAuthStatus,
  loginWithTeamPin,
  setupInitialServerPin,
} from '../services/storageService';
import { isValidHttpUrl } from '../utils/deadline';
import { StarCommandInsignia } from './StarCommandInsignia';

interface BootSequenceAndLoginProps {
  storageConfig: StorageConfig;
  onUpdateStorageConfig: (next: StorageConfig) => void;
  onAuthenticated: () => void;
}

export const BootSequenceAndLogin: React.FC<BootSequenceAndLoginProps> = ({
  storageConfig,
  onUpdateStorageConfig,
  onAuthenticated,
}) => {
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [showPin, setShowPin] = useState(false);

  const [isCheckingServer, setIsCheckingServer] = useState(true);
  const [serverUnreachableError, setServerUnreachableError] = useState<
    string | null
  >(null);
  const [pinConfiguredOnServer, setPinConfiguredOnServer] = useState(true);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);

  const [bootPhase, setBootPhase] = useState<'login' | 'booting'>('login');
  const [bootStep, setBootStep] = useState(0);

  // Uplink settings panel
  const [showUplinkSetup, setShowUplinkSetup] = useState(false);
  const [draftProvider, setDraftProvider] = useState<
    'express_api' | 'apps_script'
  >(storageConfig.provider);
  const [draftUrl, setDraftUrl] = useState(storageConfig.appsScriptUrl);
  const [configError, setConfigError] = useState<string | null>(null);

  const probeBackendStatus = useCallback(async () => {
    setIsCheckingServer(true);
    setServerUnreachableError(null);
    setErrorMsg(null);
    try {
      const status = await checkAuthStatus(storageConfig);
      setPinConfiguredOnServer(status.pinConfigured);
      if (status.authenticated) {
        onAuthenticated();
      }
    } catch (err) {
      setServerUnreachableError(
        err instanceof Error
          ? err.message
          : 'Unable to connect to the KRYPTØNIX backend data store.'
      );
    } finally {
      setIsCheckingServer(false);
    }
  }, [storageConfig, onAuthenticated]);

  useEffect(() => {
    probeBackendStatus();
  }, [probeBackendStatus]);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const timer = setInterval(() => {
      setCooldownSeconds((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldownSeconds]);

  useEffect(() => {
    if (bootPhase !== 'booting') return;

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion) {
      onAuthenticated();
      return;
    }

    const t1 = setTimeout(() => setBootStep(1), 320);
    const t2 = setTimeout(() => setBootStep(2), 680);
    const t3 = setTimeout(() => setBootStep(3), 1040);
    const t4 = setTimeout(() => {
      onAuthenticated();
    }, 1400);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, [bootPhase, onAuthenticated]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || cooldownSeconds > 0 || isCheckingServer) return;
    setErrorMsg(null);

    const trimmedPin = pin.trim();
    if (!trimmedPin || trimmedPin.length < 4) {
      setErrorMsg('Team PIN must be at least 4 characters.');
      return;
    }

    // First-time server PIN initialization flow
    if (!pinConfiguredOnServer) {
      if (trimmedPin !== confirmPin.trim()) {
        setErrorMsg('PIN and Confirm PIN do not match.');
        return;
      }
      setIsSubmitting(true);
      try {
        await setupInitialServerPin(trimmedPin, storageConfig);
        setPinConfiguredOnServer(true);
        setBootPhase('booting');
      } catch (err) {
        setErrorMsg(
          err instanceof Error
            ? err.message
            : 'Failed to initialize Team PIN on server.'
        );
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    // Standard server-verified login flow
    setIsSubmitting(true);
    try {
      const res = await loginWithTeamPin(trimmedPin, storageConfig);
      if (res.ok) {
        setBootPhase('booting');
      } else {
        if (res.retryAfterSeconds && res.retryAfterSeconds > 0) {
          setCooldownSeconds(res.retryAfterSeconds);
        }
        setErrorMsg(res.error || 'Invalid Team PIN. Access denied.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveUplinkConfig = (e: React.FormEvent) => {
    e.preventDefault();
    setConfigError(null);
    if (draftProvider === 'apps_script') {
      if (!isValidHttpUrl(draftUrl)) {
        setConfigError(
          'Enter a valid Google Apps Script Web App URL (https://script.google.com/macros/s/.../exec).'
        );
        return;
      }
    }
    onUpdateStorageConfig({
      provider: draftProvider,
      appsScriptUrl: draftUrl.trim(),
      lastSyncedAt: storageConfig.lastSyncedAt,
    });
    setShowUplinkSetup(false);
  };

  if (bootPhase === 'booting') {
    const steps = [
      'Server-side PIN hash verification succeeded...',
      storageConfig.provider === 'apps_script'
        ? 'Mounting authenticated Google Sheets Apps Script session...'
        : 'Mounting authenticated KRYPTØNIX persistent mission store...',
      'Synchronizing orbital deadline telemetry & crew roster...',
      'Command deck ready. Welcome to Star Command.',
    ];

    return (
      <div className="min-h-screen star-command-bg flex flex-col items-center justify-center p-6 text-[#F3F5FC]">
        <div className="w-full max-w-lg bg-[#151D32] border border-[#9B7CFF]/40 rounded-lg p-8 shadow-2xl">
          <div className="flex items-center justify-between gap-4 pb-5 border-b border-[#929DB7]/20">
            <div className="flex items-center gap-3">
              <StarCommandInsignia size="md" />
              <div>
                <h1 className="font-display text-lg font-bold tracking-wider text-[#F3F5FC]">
                  {TEAM_NAME} STAR COMMAND
                </h1>
                <p className="font-mono text-xs text-[#A6FF4D]">
                  SERVER AUTHENTICATED · INITIALIZING DECK
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onAuthenticated}
              className="px-3 py-1.5 text-xs font-mono font-medium text-[#F3F5FC] bg-[#101629] hover:bg-[#1E2942] border border-[#929DB7]/30 rounded transition-colors whitespace-nowrap shrink-0 cursor-pointer"
            >
              Skip Boot Sequence
            </button>
          </div>

          <div className="py-6 space-y-3 font-mono text-xs">
            {steps.map((text, idx) => {
              const active = bootStep >= idx;
              const done = bootStep > idx;
              return (
                <div
                  key={text}
                  className={`flex items-center gap-3 transition-opacity duration-200 ${
                    active ? 'opacity-100' : 'opacity-25'
                  }`}
                >
                  <span
                    className={
                      done
                        ? 'text-[#A6FF4D]'
                        : active
                        ? 'text-[#57DDF5]'
                        : 'text-[#929DB7]'
                    }
                  >
                    {done ? '✓' : active ? '◆' : '·'}
                  </span>
                  <span className="text-[#F3F5FC]">{text}</span>
                </div>
              );
            })}
          </div>

          <div className="w-full bg-[#080B16] h-1.5 rounded overflow-hidden">
            <div
              className="bg-[#A6FF4D] h-full transition-all duration-300"
              style={{ width: `${Math.min(100, (bootStep + 1) * 25)}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen star-command-bg flex flex-col justify-between p-4 sm:p-8 text-[#F3F5FC]">
      {/* Top Bar */}
      <header className="max-w-6xl w-full mx-auto flex items-center justify-between gap-4 py-2">
        <div className="flex items-center gap-3">
          <StarCommandInsignia size="md" />
          <span className="font-display text-lg font-bold tracking-wider text-[#F3F5FC] whitespace-nowrap">
            {TEAM_NAME}
          </span>
        </div>
        {!DEFAULT_GOOGLE_APPS_SCRIPT_URL && (
          <button
            type="button"
            onClick={() => setShowUplinkSetup((prev) => !prev)}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-[#F3F5FC] bg-[#151D32] hover:bg-[#1E2942] border border-[#929DB7]/25 rounded-md transition-colors whitespace-nowrap shrink-0 cursor-pointer"
          >
            <Settings className="w-3.5 h-3.5 text-[#57DDF5]" />
            <span>
              Backend:{' '}
              {storageConfig.provider === 'apps_script'
                ? 'Google Sheets Apps Script'
                : 'Star Command API Server'}
            </span>
          </button>
        )}
      </header>

      {/* Main Command Terminal Card */}
      <main className="my-auto max-w-md w-full mx-auto py-8">
        <div className="bg-[#151D32] border border-[#929DB7]/25 rounded-lg p-6 sm:p-8 shadow-2xl">
          <div className="flex flex-col items-center text-center mb-6">
            <StarCommandInsignia size="lg" className="mb-4" />
            <p className="font-mono text-xs tracking-widest text-[#A6FF4D] mb-1">
              STAR COMMAND OPERATIONS CENTRE
            </p>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-wide text-[#F3F5FC]">
              {TEAM_NAME} ACCESS TERMINAL
            </h1>
            <p className="text-sm text-[#929DB7] mt-1.5">
              {pinConfiguredOnServer
                ? 'Enter your server-verified team PIN to unlock shared competition records.'
                : 'First-Time Server Initialization: Set the shared KRYPTØNIX Team PIN.'}
            </p>
          </div>

          {/* Security Architecture Status Box */}
          <div className="mb-6 p-3.5 rounded-md bg-[#101629] border border-[#929DB7]/20 text-xs">
            <div className="flex items-start gap-2.5">
              <ShieldCheck className="w-4 h-4 text-[#A6FF4D] shrink-0 mt-0.5" />
              <div className="text-[#929DB7] leading-relaxed">
                <strong className="text-[#F3F5FC] font-semibold">
                  Server-Side Hash Authentication:
                </strong>{' '}
                Your PIN is verified on the backend against a salted cryptographic hash and issues an expiring session token. Plaintext PINs are never stored.
              </div>
            </div>
          </div>

          {isCheckingServer && (
            <div className="mb-4 p-3 rounded-md bg-[#101629] border border-[#57DDF5]/30 flex items-center gap-2.5 font-mono text-xs text-[#57DDF5]">
              <RefreshCw className="w-4 h-4 animate-spin shrink-0" />
              <span>Verifying connection to KRYPTØNIX data store...</span>
            </div>
          )}

          {serverUnreachableError && (
            <div
              role="alert"
              className="mb-4 p-3.5 rounded-md bg-[#FF5C70]/10 border border-[#FF5C70]/40 text-xs space-y-2.5"
            >
              <div className="flex items-start gap-2 text-[#FF5C70]">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold">
                    Data Store Connection Notice
                  </div>
                  <p className="mt-0.5 text-[#F3F5FC]/90">
                    {serverUnreachableError}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={probeBackendStatus}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#57DDF5] text-[#080B16] font-semibold cursor-pointer"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Retry</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowUplinkSetup(true)}
                  className="px-3 py-1.5 rounded bg-[#101629] border border-[#929DB7]/30 text-[#F3F5FC] cursor-pointer"
                >
                  Configure Endpoint
                </button>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label
                htmlFor="team-pin-input"
                className="block text-xs font-medium text-[#F3F5FC] mb-1.5"
              >
                {pinConfiguredOnServer
                  ? 'Team Security PIN'
                  : 'Create New Team Security PIN (min 4 chars)'}
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#929DB7] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  id="team-pin-input"
                  type={showPin ? 'text' : 'password'}
                  autoComplete={
                    pinConfiguredOnServer ? 'current-password' : 'new-password'
                  }
                  value={pin}
                  onChange={(e) => {
                    setPin(e.target.value);
                    if (errorMsg) setErrorMsg(null);
                  }}
                  disabled={isSubmitting || cooldownSeconds > 0}
                  placeholder={
                    pinConfiguredOnServer
                      ? 'Enter shared team PIN'
                      : 'Enter new shared team PIN'
                  }
                  className="w-full pl-10 pr-11 py-2.5 bg-[#080B16] border border-[#929DB7]/30 rounded-md font-mono text-sm text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:border-[#57DDF5] focus:ring-1 focus:ring-[#57DDF5] disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPin((prev) => !prev)}
                  aria-label={showPin ? 'Hide PIN' : 'Show PIN'}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 text-[#929DB7] hover:text-[#F3F5FC] rounded cursor-pointer"
                >
                  {showPin ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {!pinConfiguredOnServer && (
              <div>
                <label
                  htmlFor="team-pin-confirm"
                  className="block text-xs font-medium text-[#F3F5FC] mb-1.5"
                >
                  Confirm New Team Security PIN
                </label>
                <input
                  id="team-pin-confirm"
                  type={showPin ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirmPin}
                  onChange={(e) => {
                    setConfirmPin(e.target.value);
                    if (errorMsg) setErrorMsg(null);
                  }}
                  disabled={isSubmitting}
                  placeholder="Re-enter new team PIN"
                  className="w-full px-3.5 py-2.5 bg-[#080B16] border border-[#929DB7]/30 rounded-md font-mono text-sm text-[#F3F5FC] placeholder-[#929DB7]/50 focus:outline-none focus:border-[#57DDF5] focus:ring-1 focus:ring-[#57DDF5]"
                />
              </div>
            )}

            {errorMsg && (
              <div
                role="alert"
                className="p-3 rounded-md bg-[#FF5C70]/10 border border-[#FF5C70]/40 text-xs text-[#FF5C70] flex items-start gap-2"
              >
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting || cooldownSeconds > 0}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 bg-[#A6FF4D] hover:bg-[#b8ff6e] text-[#080B16] font-display font-bold text-sm tracking-wide rounded-md transition-colors disabled:opacity-50 cursor-pointer whitespace-nowrap"
            >
              <span>
                {cooldownSeconds > 0
                  ? `Terminal Locked (${cooldownSeconds}s)`
                  : isSubmitting
                  ? pinConfiguredOnServer
                    ? 'Verifying PIN...'
                    : 'Initializing Server PIN...'
                  : pinConfiguredOnServer
                  ? 'Unlock Command Centre'
                  : 'Initialize PIN & Unlock'}
              </span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Expandable Backend / Google Apps Script Endpoint Selector */}
          {showUplinkSetup && (
            <form
              onSubmit={handleSaveUplinkConfig}
              className="mt-6 pt-5 border-t border-[#929DB7]/20 space-y-3 text-xs"
            >
              <div className="flex items-center gap-2 font-display font-semibold text-[#F3F5FC]">
                <Database className="w-4 h-4 text-[#9B7CFF]" />
                <span>Select Production Data Store Endpoint</span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setDraftProvider('express_api')}
                  className={`py-2 px-3 rounded border text-left font-medium transition-colors cursor-pointer ${
                    draftProvider === 'express_api'
                      ? 'bg-[#57DDF5]/15 border-[#57DDF5] text-[#F3F5FC]'
                      : 'bg-[#101629] border-[#929DB7]/20 text-[#929DB7]'
                  }`}
                >
                  <div className="text-xs font-semibold">Backend API Server</div>
                  <div className="text-[11px] opacity-80">Express REST Store</div>
                </button>
                <button
                  type="button"
                  onClick={() => setDraftProvider('apps_script')}
                  className={`py-2 px-3 rounded border text-left font-medium transition-colors cursor-pointer ${
                    draftProvider === 'apps_script'
                      ? 'bg-[#A6FF4D]/15 border-[#A6FF4D] text-[#F3F5FC]'
                      : 'bg-[#101629] border-[#929DB7]/20 text-[#929DB7]'
                  }`}
                >
                  <div className="text-xs font-semibold">Google Sheets</div>
                  <div className="text-[11px] opacity-80">Apps Script Web App</div>
                </button>
              </div>

              {draftProvider === 'apps_script' && (
                <div>
                  <label
                    htmlFor="apps-script-url-login"
                    className="block text-[#929DB7] mb-1"
                  >
                    Google Apps Script Web App URL (/exec)
                  </label>
                  <input
                    id="apps-script-url-login"
                    type="url"
                    value={draftUrl}
                    onChange={(e) => setDraftUrl(e.target.value)}
                    placeholder="https://script.google.com/macros/s/.../exec"
                    className="w-full px-3 py-2 bg-[#080B16] border border-[#929DB7]/30 rounded font-mono text-xs text-[#F3F5FC]"
                  />
                </div>
              )}

              {configError && (
                <p className="text-[#FF5C70] text-xs">{configError}</p>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowUplinkSetup(false)}
                  className="px-3 py-1.5 rounded bg-[#101629] text-[#929DB7] hover:text-[#F3F5FC] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#57DDF5] text-[#080B16] font-semibold cursor-pointer"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Save Endpoint</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </main>

      <footer className="max-w-6xl w-full mx-auto text-center py-2 text-xs text-[#929DB7] space-y-1">
        <div className="font-mono text-[11px] text-[#F3F5FC]/80">
          {OFFICIAL_TEAM_MEMBERS.map((m) => m.name).join(' · ')}
        </div>
        <div>{TEAM_NAME} — Star Command Operations Centre</div>
      </footer>
    </div>
  );
};
