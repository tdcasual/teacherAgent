import { useCallback, useEffect, useRef } from 'react';

export interface ZoneDetector<Z extends string> {
  zone: Z;
  selector: string;
  /** Only match when this returns true (e.g. panel is open) */
  when?: () => boolean;
}

export interface WheelScrollZoneConfig<Z extends string> {
  appRef: React.RefObject<HTMLElement | null>;
  defaultZone: Z;
  /** Map zone → scrollable DOM element (or null to skip) */
  resolveTarget: (zone: Z) => HTMLElement | null;
  /** Ordered list: first match wins on pointerdown */
  detectors: ZoneDetector<Z>[];
  /** Conditions that should reset zone to default (e.g. panel closed) */
  resetWhen?: Array<{ zone: Z; condition: boolean }>;
  mobileBreakpoint?: number;
}

export interface WheelScrollZoneReturn<Z extends string> {
  zoneRef: React.RefObject<Z>;
  setZone: (zone: Z) => void;
}

function useResponsiveMobile(breakpoint: number) {
  const ref = useRef(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia(`(max-width: ${breakpoint}px)`);
    ref.current = mql.matches;
    const onChange = (e: MediaQueryListEvent) => {
      ref.current = e.matches;
    };
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [breakpoint]);
  return ref;
}

export function useWheelScrollZone<Z extends string>(
  config: WheelScrollZoneConfig<Z>,
): WheelScrollZoneReturn<Z> {
  const { appRef, defaultZone, mobileBreakpoint = 900 } = config;
  const zoneRef = useRef<Z>(defaultZone);
  const isMobile = useResponsiveMobile(mobileBreakpoint);

  // Store latest config in refs so effects don't need to re-register listeners
  const configRef = useRef(config);
  configRef.current = config;

  const setZone = useCallback((zone: Z) => {
    zoneRef.current = zone;
  }, []);

  // Reset zone when panels close
  useEffect(() => {
    const { resetWhen } = configRef.current;
    if (!resetWhen) return;
    for (const { zone, condition } of resetWhen) {
      if (zoneRef.current === zone && condition) {
        setZone(defaultZone);
        break;
      }
    }
  });

  // Pointer-down zone detection (registered once)
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const onPointerDown = (event: PointerEvent) => {
      if (isMobile.current) return;
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const root = appRef.current;
      if (!root || !root.contains(target)) return;
      for (const det of configRef.current.detectors) {
        if (det.when && !det.when()) continue;
        if (target.closest(det.selector)) {
          setZone(det.zone);
          return;
        }
      }
    };
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') setZone(configRef.current.defaultZone);
    };
    document.addEventListener('pointerdown', onPointerDown, true);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true);
      document.removeEventListener('keydown', onKeyDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appRef, setZone]);

  // Wheel event redirection (registered once)
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const onWheel = (event: WheelEvent) => {
      if (isMobile.current) return;
      if (event.defaultPrevented || event.ctrlKey) return;
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const root = appRef.current;
      if (!root || !root.contains(target)) return;
      if (target.closest('textarea, input, select, [contenteditable="true"]')) return;

      const { resetWhen, defaultZone: dz, resolveTarget } = configRef.current;
      let zone = zoneRef.current;
      if (resetWhen) {
        for (const { zone: z, condition } of resetWhen) {
          if (zone === z && condition) {
            zone = dz;
            break;
          }
        }
      }

      event.preventDefault();
      const el = resolveTarget(zone);
      if (el) {
        if (event.deltaY) el.scrollTop += event.deltaY;
        if (event.deltaX) el.scrollLeft += event.deltaX;
      }
    };
    document.addEventListener('wheel', onWheel, { passive: false, capture: true });
    return () => document.removeEventListener('wheel', onWheel, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appRef]);

  return { zoneRef, setZone };
}
