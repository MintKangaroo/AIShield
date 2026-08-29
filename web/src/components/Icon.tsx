import type { ReactNode } from "react";

export type IconName =
  | "activity"
  | "archive"
  | "arrow"
  | "beaker"
  | "book"
  | "check"
  | "chevron"
  | "clock"
  | "close"
  | "database"
  | "download"
  | "fingerprint"
  | "gauge"
  | "grid"
  | "layers"
  | "play"
  | "plus"
  | "refresh"
  | "server"
  | "shield"
  | "spark"
  | "terminal"
  | "transfer";

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    activity: <path d="M3 12h4l2.2-6 4.2 12 2.1-6H21" />,
    archive: (
      <>
        <path d="M4 7h16v13H4zM3 3h18v4H3z" />
        <path d="M9 11h6" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    beaker: (
      <>
        <path d="M9 3h6m-5 0v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3" />
        <path d="M7.5 15h9" />
      </>
    ),
    book: (
      <>
        <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v18H6.5A2.5 2.5 0 0 0 4 22V4.5Z" />
        <path d="M8 7h8M8 11h6" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5.5l3.5 2" />
      </>
    ),
    close: <path d="m6 6 12 12M18 6 6 18" />,
    database: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" />
      </>
    ),
    download: <path d="M12 3v12m-5-5 5 5 5-5M5 21h14" />,
    fingerprint: (
      <>
        <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 5-1.5 8.5-3 11M9 21c1.5-3 2-6.2 2-10a1 1 0 0 1 2 0c0 3.3-.3 6-1.5 9" />
        <path d="M4 17c.7-2.2.8-4.4.8-7a7.2 7.2 0 0 1 14.4 0c0 2.8-.2 5.3-1 7.8" />
      </>
    ),
    gauge: (
      <>
        <path d="M4 18a8 8 0 1 1 16 0" />
        <path d="m12 14 4-4" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </>
    ),
    layers: <path d="m12 3 9 5-9 5-9-5 9-5Zm-9 10 9 5 9-5M3 18l9 5 9-5" />,
    play: <path d="m8 5 11 7-11 7V5Z" />,
    plus: <path d="M12 5v14M5 12h14" />,
    refresh: (
      <path d="M20 6v5h-5M4 18v-5h5M6.1 8A7 7 0 0 1 18.5 6.5L20 11M4 13l1.5 4.5A7 7 0 0 0 18 16" />
    ),
    server: (
      <>
        <rect x="3" y="4" width="18" height="6" rx="2" />
        <rect x="3" y="14" width="18" height="6" rx="2" />
        <path d="M7 7h.01M7 17h.01" />
      </>
    ),
    shield: <path d="M12 3 20 6v5c0 5.2-3.3 8.5-8 10-4.7-1.5-8-4.8-8-10V6l8-3Zm-3 9 2 2 4-5" />,
    spark: (
      <path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Zm6 13 .7 2.3L21 19l-2.3.7L18 22l-.7-2.3L15 19l2.3-.7L18 16Z" />
    ),
    terminal: <path d="m4 6 5 5-5 5m7 0h8" />,
    transfer: <path d="M4 8h13m-4-4 4 4-4 4M20 16H7m4 4-4-4 4-4" />,
  };

  return (
    <svg
      aria-hidden="true"
      className="icon"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
    >
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7">
        {paths[name]}
      </g>
    </svg>
  );
}
